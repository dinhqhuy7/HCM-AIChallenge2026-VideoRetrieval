"""A small client for the DRES client API v2 (DRES is where the live rounds are judged).

Endpoints and shapes follow the client specification, ``doc/oas-client.json`` of
github.com/dres-dev/DRES:

  POST /api/v2/login                                       {username, password} -> ApiUser.sessionId
  GET  /api/v2/client/evaluation/list?session=             -> [ApiClientEvaluationInfo]
  GET  /api/v2/client/evaluation/currentTask/{id}?session= -> ApiClientTaskTemplateInfo
  POST /api/v2/submit/{evaluationId}?session=              ApiClientSubmission -> SuccessfulSubmissionsStatus
                                                           (200 or 202; errors 400, 401, 404, 412)

Rules this client keeps, because each mistake costs an attempt:
- one answer per request;
- the same answer is never sent twice for the same task: a local log records it before it is
  sent, so even a request that never got a reply is not repeated;
- the verdict (CORRECT, WRONG, INDETERMINATE, UNDECIDABLE) is read out, not raw JSON.
The password is never a command-line argument; scripts/search.py asks for it.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# A server behind a proxy may refuse Python's default User-Agent (Cloudflare's error 1010)
# before DRES sees the request.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) video-retrieval-client"


class DresError(RuntimeError):
    """``status`` is the HTTP status when the server answered, None when it could not be
    reached or its answer could not be read."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    verdict: str
    description: str


class DresClient:
    def __init__(self, base_url: str, opener: Callable[..., Any] = urllib.request.urlopen,
                 timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = opener
        self.timeout = timeout
        self.session = ""

    def login(self, username: str, password: str) -> None:
        user = self.call("POST", "/api/v2/login", body={"username": username, "password": password})
        self.session = str(user.get("sessionId") or "")
        if not self.session:
            raise DresError("login answered without a sessionId")

    def evaluations(self) -> list[dict[str, Any]]:
        return list(self.call("GET", "/api/v2/client/evaluation/list", session=True) or [])

    def current_task(self, evaluation_id: str) -> dict[str, Any]:
        path = "/api/v2/client/evaluation/currentTask/" + urllib.parse.quote(evaluation_id, safe="")
        return self.call("GET", path, session=True) or {}

    def submit(self, evaluation_id: str, answer: dict[str, Any]) -> Verdict:
        path = "/api/v2/submit/" + urllib.parse.quote(evaluation_id, safe="")
        reply = self.call("POST", path, session=True, body={"answerSets": [{"answers": [answer]}]})
        return Verdict(bool(reply.get("status")), str(reply.get("submission") or ""),
                       str(reply.get("description") or ""))

    def call(self, method: str, path: str, session: bool = False, body: dict[str, Any] | None = None) -> Any:
        url = self.base_url + path
        if session:
            if not self.session:
                raise DresError("log in first")
            url += "?" + urllib.parse.urlencode({"session": self.session})
        request = urllib.request.Request(
            url, method=method, data=None if body is None else json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with self.opener(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:  # the server answered, and refused
            detail = error.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("description", detail)
            except (ValueError, AttributeError):
                pass
            raise DresError(f"DRES {error.code}: {detail}", error.code) from error
        except OSError as error:  # no answer at all: a timeout, a refused connection ...
            raise DresError(f"no reply from DRES: {error}") from error
        try:
            return json.loads(text) if text.strip() else {}
        except ValueError as error:
            raise DresError(f"DRES answered with something that is not JSON: {text[:80]!r}") from error


class SubmissionLog:
    """Every answer, one JSON line when it is about to be sent and one with what came back.

    An answer is written down *before* the request, and on disk. When the reply never
    arrives (a timeout, a dropped connection), the server may still have judged it, so its
    state stays ``SENDING`` and the answer is not sent again. Only an HTTP error, which is the
    server refusing the request, leaves the answer free to be sent again.
    """

    SENDING = "SENDING"

    def __init__(self, path: Path) -> None:
        self.path = path

    def entries(self) -> list[dict[str, Any]]:
        """The lines that can be read; one cut off by a crash is skipped, not fatal."""
        if not self.path.exists():
            return []
        found = []
        for line in self.path.read_bytes().split(b"\n"):  # bytes: one entry per line, whatever is inside it
            try:
                found.append(json.loads(line.decode("utf-8")))
            except ValueError:  # includes a line cut inside a letter
                continue
        return found

    def status(self, evaluation_id: str, task: str, answer: dict[str, Any]) -> str | None:
        """The latest state of this answer for this task, or None if it was never sent."""
        key, latest = json.dumps(answer, sort_keys=True, ensure_ascii=False), None
        for entry in self.entries():
            if entry["evaluation"] == evaluation_id and entry["task"] == task and entry["answer"] == key:
                latest = entry["verdict"]
        return latest

    def sent(self, evaluation_id: str, task: str, answer: dict[str, Any]) -> bool:
        state = self.status(evaluation_id, task, answer)
        return state is not None and not state.startswith("ERROR")

    def sending(self, evaluation_id: str, task: str, answer: dict[str, Any]) -> None:
        self.append(evaluation_id, task, answer, self.SENDING)

    def record(self, evaluation_id: str, task: str, answer: dict[str, Any], verdict: Verdict) -> None:
        self.append(evaluation_id, task, answer, verdict.verdict or "NO VERDICT")

    def failed(self, evaluation_id: str, task: str, answer: dict[str, Any], status: int) -> None:
        self.append(evaluation_id, task, answer, f"ERROR {status}")

    def append(self, evaluation_id: str, task: str, answer: dict[str, Any], state: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"evaluation": evaluation_id, "task": task,
                 "answer": json.dumps(answer, sort_keys=True, ensure_ascii=False), "verdict": state}
        with self.path.open("ab") as handle:  # bytes: a crash can cut a line inside an accented letter
            if handle.tell() and self.path.read_bytes()[-1:] != b"\n":
                handle.write(b"\n")  # start this entry on a line of its own
            handle.write((json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())  # SENDING must outlive a crash, or the answer could be sent twice
