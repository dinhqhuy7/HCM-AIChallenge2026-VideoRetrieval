"""scripts/search.py with a stand-in system (no model is loaded) and a stand-in DRES client."""
import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("yaml", "numpy", "PIL"))


def load_script():
    spec = importlib.util.spec_from_file_location("search_script", ROOT / "scripts" / "search.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAVE_LIBRARIES, "needs PyYAML, numpy and Pillow")
class SearchScriptTest(unittest.TestCase):
    def setUp(self):
        from src.config import Settings
        from src.layout import DataLayout

        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.script = load_script()
        self.settings = {"submission": {"frame_id_base": 1, "dres": {"base_url": "http://dres.test"}}}
        self.system = SimpleNamespace(layout=DataLayout(self.folder / "data"), searched=[], trakes=[])
        self.system.settings = Settings(self.settings, "search.yaml")
        self.system.search = self.search
        self.system.trake = self.trake

    def search(self, boxes):
        from src.retrieval.hits import Frame

        self.system.searched.append(boxes)
        return [Frame("L21_V001", 7, "L21_V001_000100", 100, 4000), Frame("L21_V002", 3, "L21_V002_000020", 20, 800)]

    def trake(self, events):
        from src.retrieval.hits import Frame
        from src.retrieval.trake import Chain

        self.system.trakes.append(events)
        frames = tuple(Frame("L21_V001", n, f"L21_V001_{index:06d}", index, index * 40)
                       for n, index in enumerate((100, 250, 400)))
        return [Chain("L21_V001", frames, 1.5)]

    def run_main(self, *argv, answers=()):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch("builtins.input", side_effect=list(answers)):
            try:
                code = self.script.main(list(argv), system_factory=lambda args: self.system)
            except SystemExit as stop:
                code = stop.code
        return code, out.getvalue(), err.getvalue()

    # reading a query file
    def test_a_query_file_gives_the_task_the_text_and_the_events(self):
        path = self.folder / "query-p1-2-trake.txt"
        path.write_text("\ufeffE1: một người đi xe máy\nCảnh 2. một cánh đồng\nghi chú\n", encoding="utf-8")
        task, text, events = self.script.read_query_file(path)
        self.assertEqual((task, events), ("trake", ["một người đi xe máy", "một cánh đồng"]))
        self.assertTrue(text.startswith("E1:"))  # the byte order mark is gone
        plain = self.folder / "query.txt"
        plain.write_text("x", encoding="utf-8")
        self.assertIsNone(self.script.read_query_file(plain)[0])  # no task in the name

    # the answers and the file
    def test_kis_writes_frames_counted_from_the_configured_base(self):
        out = self.folder / "runs" / "kis.csv"
        code, printed, _ = self.run_main("kis", "--text", "chợ đêm", "--ocr", "  ", "--out", str(out))
        self.assertEqual(code, 0)
        self.assertEqual(self.system.searched, [{"visual": "chợ đêm"}])  # the empty box is not a box
        self.assertEqual(out.read_text(encoding="utf-8"), "L21_V001,101\nL21_V002,21\n")
        self.assertRegex(printed, r"1  L21_V001, 101 +4\.0s\n +2  L21_V002, 21 +0\.8s")
        self.assertIn(f"wrote 2 rows to {out}", printed)

    def test_qa_puts_the_answer_on_every_row_and_needs_it_to_write(self):
        out = self.folder / "qa.csv"
        self.run_main("qa", "--text", "mấy người?", "--answer", "năm", "--out", str(out))
        self.assertEqual(out.read_text(encoding="utf-8"), "L21_V001,101,năm\nL21_V002,21,năm\n")
        again = self.folder / "qa2.csv"
        _, printed, _ = self.run_main("qa", "--text", "mấy người?", "--out", str(again))
        self.assertIn("add --answer", printed)
        self.assertFalse(again.exists())

    def test_trake_takes_its_events_and_writes_one_chain_a_row(self):
        out = self.folder / "trake.csv"
        self.run_main("trake", "--event", "một", "--event", "hai", "--event", "ba", "--out", str(out))
        self.assertEqual(self.system.trakes, [["một", "hai", "ba"]])
        self.assertEqual(out.read_text(encoding="utf-8"), "L21_V001,101,251,401\n")

    def test_a_query_file_names_the_task_and_the_csv(self):
        path = self.folder / "query-p1-1-kis.txt"
        path.write_text("một chiếc máy bay trên đường băng\n", encoding="utf-8")
        self.run_main("--query-file", str(path), "--out-dir", str(self.folder / "submission"))
        self.assertEqual(self.system.searched, [{"visual": "một chiếc máy bay trên đường băng"}])
        self.assertTrue((self.folder / "submission" / "query-p1-1-kis.csv").exists())

    # what is refused before anything is searched
    def test_wrong_arguments_stop_with_a_message_and_search_nothing(self):
        for argv, message in (
                ((), "give the task"),
                (("kis",), "type something into at least one box"),
                (("trake", "--event", "một"), "TRAKE needs the events one by one"),
                (("trake", "--text", "x", "--event", "a", "--event", "b"), "visual lane only"),
                (("kis", "--text", "x", "--out-dir", "somewhere"), "--out-dir goes with --query-file"),
                (("qa", "--text", "x", "--submit", "1"), "needs --answer")):
            code, _, err = self.run_main(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn(message, err)
        self.assertEqual((self.system.searched, self.system.trakes), ([], []))

    def test_submitting_without_an_address_fails_before_the_search(self):
        from src.config import MissingSetting, Settings

        self.system.settings = Settings({"submission": {"frame_id_base": 0}}, "search.yaml")
        with self.assertRaisesRegex(MissingSetting, "the DRES address the organisers give you"):
            self.run_main("kis", "--text", "x", "--submit", "1")
        self.assertEqual(self.system.searched, [])

    def test_a_row_that_does_not_exist_cannot_be_submitted(self):
        code, _, err = self.run_main("kis", "--text", "x", "--submit", "5")
        self.assertEqual(code, 2)
        self.assertIn("--submit takes a row from 1 to 2", err)

    # submitting
    def fake_client(self, submit):
        client = mock.MagicMock()
        client.evaluations.return_value = [{"id": "e1", "name": "round 1", "status": "ACTIVE"},
                                           {"id": "e0", "name": "old", "status": "TERMINATED"}]
        client.current_task.return_value = {"name": "task 3"}
        client.submit.side_effect = submit
        return client

    def submit(self, client, answers=("team", "y"), password="s3cret!"):
        with mock.patch("src.submission.dres.DresClient", return_value=client), \
                mock.patch("getpass.getpass", return_value=password):
            return self.run_main("kis", "--text", "x", "--submit", "1", answers=answers)

    def test_one_row_is_sent_once_and_the_password_goes_nowhere(self):
        from src.submission.dres import Verdict

        client = self.fake_client(lambda evaluation, body: Verdict(True, "WRONG", "judged"))
        code, printed, err = self.submit(client)
        self.assertEqual(code, 0)
        client.login.assert_called_once_with("team", "s3cret!")
        client.submit.assert_called_once_with("e1", {"mediaItemName": "L21_V001", "start": 4000, "end": 4000})
        self.assertIn("WRONG: judged", printed)
        log = self.system.layout.submissions_log().read_text(encoding="utf-8")
        for place in (printed, err, log):
            self.assertNotIn("s3cret", place)
        code, _, err = self.submit(client)  # the same answer again
        self.assertIn("already sent", str(code))
        client.submit.assert_called_once()

    def test_an_answer_dres_cannot_take_is_refused_before_any_login(self):
        client = self.fake_client(lambda evaluation, body: None)
        with mock.patch("src.submission.dres.DresClient", return_value=client), \
                mock.patch("getpass.getpass") as ask, self.assertRaisesRegex(ValueError, "cannot contain '-'"):
            self.run_main("qa", "--text", "x", "--answer", "ba-bốn", "--submit", "1", answers=("team", "y"))
        client.login.assert_not_called()
        ask.assert_not_called()

    def test_declining_sends_nothing_and_logs_nothing(self):
        client = self.fake_client(lambda evaluation, body: None)
        self.submit(client, answers=("team", "n"))
        client.submit.assert_not_called()
        self.assertFalse(self.system.layout.submissions_log().exists())

    def test_a_refusal_frees_the_answer_and_a_missing_reply_does_not(self):
        from src.submission.dres import DresError

        refuse = self.fake_client(mock.Mock(side_effect=DresError("DRES 412: limit", 412)))
        with self.assertRaisesRegex(DresError, "412"):
            self.submit(refuse)
        again = self.fake_client(lambda evaluation, body: None)
        again.submit.side_effect = None
        again.submit.return_value = SimpleNamespace(verdict="CORRECT", description="")
        self.assertEqual(self.submit(again)[0], 0)  # sent after the refusal
        silent = self.fake_client(mock.Mock(side_effect=DresError("no reply from DRES", None)))
        self.system.layout.submissions_log().unlink()
        with self.assertRaises(DresError):
            code, _, err = self.submit(silent)
        retry = self.fake_client(lambda evaluation, body: None)
        code, _, _ = self.submit(retry)
        self.assertIn("no reply came back", str(code))  # the answer is still SENDING
        retry.submit.assert_not_called()


@unittest.skipUnless(HAVE_LIBRARIES, "needs PyYAML, numpy and Pillow")
class RealSystemTest(unittest.TestCase):
    def test_combining_boxes_without_rrf_k_fails_before_a_model_is_loaded(self):
        from src.config import MissingSetting

        script = load_script()
        args = SimpleNamespace(data=Path("nowhere"), config=ROOT / "configs" / "search.yaml",
                               index_config=ROOT / "configs" / "index.yaml", device=None)
        system = script.System(args)
        with self.assertRaisesRegex(MissingSetting, "set `fusion.rrf_k`"):
            system.search({"visual": "a", "ocr": "b"})
        self.assertIsNone(system._visual)

    def run_script(self, *argv):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "search.py"), *argv], capture_output=True,
                              text=True, timeout=120)

    def test_as_a_command_a_bad_call_is_a_message_not_a_traceback(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIn("give the task", result.stderr)
        result = self.run_script("kis", "--text", "x", "--config", "no-such-file.yaml")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("error:"), result.stderr[-200:])
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
