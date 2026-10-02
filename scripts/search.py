"""Online search: one query -> lanes -> fusion -> up to 100 rows, printed and written as CSV.

    python scripts/search.py kis --text "a firefighter carries a child out of a house" --out runs/kis-1.csv
    python scripts/search.py kis --text "a market at night" --ocr "bến thành" --out runs/kis-2.csv  # needs fusion.rrf_k
    python scripts/search.py qa --text "..." --answer "5" --out runs/qa-1.csv
    python scripts/search.py trake --event "..." --event "..." --event "..." --out runs/trake-1.csv
    python scripts/search.py --query-file query-p1-1-kis.txt --out-dir submission
    python scripts/search.py kis --text "..." --submit 1          # send row 1 to DRES

Each box goes to its own lane: --text to the pictures, --ocr to text on screen, --asr to
speech, --objects to object labels. TRAKE searches its events with the visual lane only.
See docs/online.md, docs/trake.md, docs/submission.md.
"""
from __future__ import annotations

import argparse
import getpass
import re
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import MissingSetting, Settings  # noqa: E402
from src.layout import DataLayout  # noqa: E402
from src.submission.answers import Answer, KisAnswer, QaAnswer, TrakeAnswer, write_csv  # noqa: E402
from src.submission.dres import DresError  # noqa: E402

TASK_IN_NAME = re.compile(r"-(kis|qa|trake)$", re.IGNORECASE)
EVENT_LINE = re.compile(r"^\s*(?:E|Cảnh\s*)\d+\s*[:.)\-–]?\s*(\S.*)$", re.IGNORECASE)
KEYWORD_BOXES = ("ocr", "asr", "objects")


def read_query_file(path: Path) -> tuple[str | None, str, list[str]]:
    """(task from the file name, whole text, TRAKE events from the lines that start with E1, E2 ...)."""
    text = unicodedata.normalize("NFC", path.read_text(encoding="utf-8-sig")).strip()
    task = TASK_IN_NAME.search(path.stem)
    events = [match.group(1).strip() for line in text.splitlines() if (match := EVENT_LINE.match(line))]
    return (task.group(1).lower() if task else None), text, events


class System:
    """Loads only what a query needs, once."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.layout = DataLayout(args.data)
        self.index_settings = Settings.load(args.index_config)
        self.settings = Settings.load(args.config)
        self.device = args.device or self.settings.get("device", "cuda")
        self._visual = None

    def visual_lane(self):
        if self._visual is None:
            from src.embeddings import load_encoder
            from src.retrieval.lanes import VisualLane
            from src.retrieval.milvus_index import MilvusIndex, resolve_uri

            name = self.settings.require("visual.encoder")
            index = MilvusIndex(resolve_uri(self.index_settings.require("milvus.uri"), self.layout.root), name).open()
            translate = None
            if self.settings.get("translation.enabled"):
                from src.retrieval.translation import Translator

                translator = Translator(self.settings.require("translation.model"), self.device,
                                        int(self.settings.require("translation.max_length")))

                def translate(text: str) -> str:
                    english = translator(text)
                    print(f"visual text in English: {english}", flush=True)
                    return english
            self._visual = VisualLane(load_encoder(name, self.index_settings, self.device), index, translate)
        return self._visual

    def keyword_lane(self, lane: str):
        from src.retrieval.keyword_index import KeywordIndex
        from src.retrieval.lanes import KeywordLane

        path = self.layout.keyword_index(lane)
        if not path.exists():
            raise SystemExit(f"no {lane} index at {path}: run build_index.py {lane} and then keywords")
        return KeywordLane(KeywordIndex.load(path))

    def search(self, boxes: dict[str, str]):
        from src.fusion.rank_fusion import ReciprocalRankFusion
        from src.fusion.shaping import ResultShaper, VideoSpread
        from src.retrieval.engine import SearchEngine

        k = self.settings.get("fusion.rrf_k")
        if len(boxes) > 1 and k is None:  # before any model is loaded
            raise MissingSetting(f"{self.settings.source}: set `fusion.rrf_k` to combine lanes "
                                 "(the RRF paper uses 60)")
        lanes = {lane: self.visual_lane() if lane == "visual" else self.keyword_lane(lane) for lane in boxes}
        spread = None
        if self.settings.get("spread.enabled"):
            spread = VideoSpread(int(self.settings.require("spread.keep_top")),
                                 int(self.settings.require("spread.per_video")))
        shaper = ResultShaper(int(self.settings.require("rows")), spread)
        engine = SearchEngine(lanes, ReciprocalRankFusion(k) if k is not None else None, shaper,
                              int(self.settings.require("depth")))
        return engine.search(boxes)

    def trake(self, events: list[str]):
        from src.retrieval.trake import ChainRules, TrakeSearch

        rules = ChainRules(self.settings.get("trake.order", "strict"), self.settings.get("trake.min_gap_ms"),
                           self.settings.get("trake.max_gap_ms"))
        search = TrakeSearch(self.visual_lane(), rules, int(self.settings.require("depth")),
                             int(self.settings.require("rows")), bool(self.settings.get("trake.spread", False)))
        return search.search(events)


def answers_for(task: str, system: Any, boxes: dict[str, str], events: list[str],
                answer: str | None) -> list[Answer]:
    if task == "trake":
        return [TrakeAnswer(chain.video_id, tuple(frame.frame_index for frame in chain.frames))
                for chain in system.trake(events)]
    frames = system.search(boxes)
    if task == "qa" and answer:
        return [QaAnswer(frame.video_id, frame.frame_index, frame.time_ms, answer) for frame in frames]
    return [KisAnswer(frame.video_id, frame.frame_index, frame.time_ms) for frame in frames]


def show(answers: list[Answer], base: int, limit: int = 10) -> None:
    for rank, answer in enumerate(answers[:limit], start=1):
        time = f"  {answer.time_ms / 1000:8.1f}s" if hasattr(answer, "time_ms") else ""
        print(f"{rank:3d}  {', '.join(answer.csv_row(base))}{time}")
    if len(answers) > limit:
        print(f"... {len(answers)} rows")


def choose(prompt: str, count: int) -> int:
    """A number from 1 to count, typed by the person; asked again until it is one."""
    while True:
        typed = input(prompt).strip()
        if typed.isdigit() and 1 <= int(typed) <= count:
            return int(typed)
        print(f"type a number from 1 to {count}")


def submit(answer: Answer, row: int, system: Any, base: int) -> None:
    from src.submission.dres import DresClient, SubmissionLog

    body = answer.dres(base)  # first: an answer DRES cannot take (a dash in a Q&A answer) is refused before any login
    address = system.settings.require("submission.dres.base_url", "the DRES address the organisers give you")
    client = DresClient(address)
    client.login(input("DRES username: "), getpass.getpass("DRES password: "))
    active = [item for item in client.evaluations() if str(item.get("status", "")).upper() == "ACTIVE"]
    if not active:
        raise SystemExit("no evaluation is running")
    for number, item in enumerate(active, start=1):
        print(f"{number}. {item.get('name')}")
    evaluation = active[0] if len(active) == 1 else active[choose("evaluation number: ", len(active)) - 1]
    task = str(client.current_task(evaluation["id"]).get("name", ""))
    log = SubmissionLog(system.layout.submissions_log())
    state = log.status(evaluation["id"], task, body)
    if state == SubmissionLog.SENDING:
        raise SystemExit("this answer was sent for this task before and no reply came back; the server may "
                         "have judged it: check DRES before sending anything else")
    if log.sent(evaluation["id"], task, body):
        raise SystemExit(f"this answer was already sent for this task ({state}); a repeat would only cost an attempt")
    print(f"row {row}, task {task!r}: {body}")
    if input("send? [y/N] ").strip().lower() != "y":
        return
    log.sending(evaluation["id"], task, body)
    try:
        verdict = client.submit(evaluation["id"], body)
    except DresError as error:
        if error.status is not None:  # the server answered: it refused the request, it did not judge it
            log.failed(evaluation["id"], task, body, error.status)
        else:
            print("No usable reply came back. The answer is kept as SENDING and will not be sent again by "
                  "this script: look at DRES to see whether it was judged.", file=sys.stderr)
        raise
    log.record(evaluation["id"], task, body, verdict)
    print(f"{verdict.verdict or 'no verdict'}: {verdict.description}")


def main(argv: list[str] | None = None, system_factory: Callable[[argparse.Namespace], Any] = System) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", nargs="?", choices=["kis", "qa", "trake"])
    parser.add_argument("--text", help="what the pictures show (visual lane)")
    parser.add_argument("--ocr", help="words written on screen")
    parser.add_argument("--asr", help="words that are said")
    parser.add_argument("--objects", help="object names, e.g. 'person car'")
    parser.add_argument("--event", action="append", default=[], help="TRAKE: one event, in order; repeatable")
    parser.add_argument("--query-file", type=Path, help="an organisers' query file, e.g. query-p1-1-kis.txt")
    parser.add_argument("--answer", help="Q&A: the answer, written on every row")
    parser.add_argument("--out", type=Path, help="CSV file to write")
    parser.add_argument("--out-dir", type=Path, help="with --query-file: write <query file name>.csv here")
    parser.add_argument("--submit", type=int, metavar="ROW", help="send this row (1-based) to DRES")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "search.yaml")
    parser.add_argument("--index-config", type=Path, default=ROOT / "configs" / "index.yaml")
    parser.add_argument("--device", help="overrides `device` in configs/search.yaml")
    args = parser.parse_args(argv)

    task, text, events, out = args.task, args.text, list(args.event), args.out
    if args.query_file:
        named, text, found = read_query_file(args.query_file)
        task, events = task or named, events or found
        if args.out_dir:
            out = args.out_dir / f"{args.query_file.stem}.csv"
    elif args.out_dir:
        parser.error("--out-dir goes with --query-file; use --out for a single query")
    if task is None:
        parser.error("give the task (kis, qa, trake) or a query file whose name ends in -kis/-qa/-trake")
    typed = {"visual": text, "ocr": args.ocr, "asr": args.asr, "objects": args.objects}
    boxes = {lane: value.strip() for lane, value in typed.items() if value and value.strip()}
    if task == "trake":
        if any(getattr(args, lane) for lane in KEYWORD_BOXES) or args.text:
            parser.error("TRAKE searches its events with the visual lane only: give them with --event, "
                         "without --text, --ocr, --asr or --objects")
        if len(events) < 2:
            parser.error("TRAKE needs the events one by one: --event ... --event ... (or E1/E2 lines in the file)")
    elif not boxes:
        parser.error("type something into at least one box: --text, --ocr, --asr or --objects")
    if task == "qa" and args.submit is not None and not args.answer:
        parser.error("a Q&A submission needs --answer")

    system = system_factory(args)
    base = int(system.settings.require("submission.frame_id_base"))
    if args.submit is not None:  # before any model is loaded: no address, no point searching
        system.settings.require("submission.dres.base_url", "the DRES address the organisers give you")
    answers = answers_for(task, system, boxes, events, args.answer)
    show(answers, base)
    if task == "qa" and not args.answer:
        print("Q&A: add --answer to write the file (the answer goes on every row)")
    elif out:
        write_csv(out, answers, base)
        print(f"wrote {len(answers)} rows to {out}")
    if args.submit is not None:
        if not 1 <= args.submit <= len(answers):
            parser.error(f"--submit takes a row from 1 to {len(answers)}")
        submit(answers[args.submit - 1], args.submit, system, base)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, DresError, FileNotFoundError) as error:  # a setting to fill in, a value out of range,
        # an answer DRES cannot take, a file that is not there
        sys.exit(f"error: {error}")
