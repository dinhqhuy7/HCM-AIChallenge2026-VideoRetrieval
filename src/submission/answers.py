"""The three answer shapes, each built in one place for both the CSV file and DRES.

CSV rows (no header, at most 100 per query), as in the organisers' rules:
  KIS    <video_id>,<frame_id>
  Q&A    <video_id>,<frame_id>,<answer>
  TRAKE  <video_id>,<frame_id_1>,...,<frame_id_n>

DRES answers (client API v2) carry a time in milliseconds for KIS and Q&A, but frame numbers
for TRAKE. A frame number where a time belongs is a wrong answer that looks entirely
reasonable, which is why the shapes live here and are tested.

``frame_id_base`` turns the decoder's frame index (first frame = 0) into the number the
answer key uses; see configs/search.yaml.
"""
from __future__ import annotations

import csv
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.retrieval.text import tidy

MAX_ROWS = 100


def check(video_id: str, *numbers: int) -> None:
    if not video_id or not video_id.strip():
        raise ValueError("an answer needs a video id")
    if any(number < 0 for number in numbers):
        raise ValueError("frame indexes and times cannot be negative")


class Answer(ABC):
    video_id: str

    @abstractmethod
    def csv_row(self, frame_id_base: int) -> list[str]:
        """One row of the submission file."""

    @abstractmethod
    def dres(self, frame_id_base: int) -> dict[str, Any]:
        """One ApiClientAnswer for POST /api/v2/submit/{evaluationId}."""


@dataclass(frozen=True)
class KisAnswer(Answer):
    video_id: str
    frame_index: int
    time_ms: int

    def __post_init__(self) -> None:
        check(self.video_id, self.frame_index, self.time_ms)

    def csv_row(self, frame_id_base: int) -> list[str]:
        return [self.video_id, str(self.frame_index + frame_id_base)]

    def dres(self, frame_id_base: int) -> dict[str, Any]:
        return {"mediaItemName": self.video_id, "start": self.time_ms, "end": self.time_ms}


@dataclass(frozen=True)
class QaAnswer(Answer):
    video_id: str
    frame_index: int
    time_ms: int
    answer: str

    def __post_init__(self) -> None:
        check(self.video_id, self.frame_index, self.time_ms)
        object.__setattr__(self, "answer", tidy(self.answer))
        if not self.answer:
            raise ValueError("a Q&A row needs an answer")

    def csv_row(self, frame_id_base: int) -> list[str]:
        return [self.video_id, str(self.frame_index + frame_id_base), self.answer]

    def dres(self, frame_id_base: int) -> dict[str, Any]:
        # The text template joins its parts with "-", so a dash inside the answer would be read
        # as the start of the next part.
        if "-" in self.answer:
            raise ValueError("a Q&A answer sent to DRES cannot contain '-'")
        return {"text": f"QA-{self.answer}-{self.video_id}-{self.time_ms}"}


@dataclass(frozen=True)
class TrakeAnswer(Answer):
    video_id: str
    frame_indexes: tuple[int, ...]

    def __post_init__(self) -> None:
        check(self.video_id, *self.frame_indexes)
        if len(self.frame_indexes) < 2 or any(b < a for a, b in zip(self.frame_indexes, self.frame_indexes[1:])):
            raise ValueError("a TRAKE chain needs two or more frames in time order")

    def csv_row(self, frame_id_base: int) -> list[str]:
        return [self.video_id, *(str(index + frame_id_base) for index in self.frame_indexes)]

    def dres(self, frame_id_base: int) -> dict[str, Any]:
        frames = ",".join(str(index + frame_id_base) for index in self.frame_indexes)
        return {"text": f"TR-{self.video_id}-{frames}"}


def write_csv(path: Path, answers: list[Answer], frame_id_base: int) -> None:
    """The submission file: the old file or the new one, never half of one."""
    if len(answers) > MAX_ROWS:
        raise ValueError(f"{len(answers)} rows; the organisers accept at most {MAX_ROWS}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(answer.csv_row(frame_id_base) for answer in answers)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
