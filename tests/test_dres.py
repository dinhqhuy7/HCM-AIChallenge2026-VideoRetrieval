"""DresClient against a stand-in server on this machine, and SubmissionLog on a temporary file."""
import json
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.submission.dres import DresClient, DresError, SubmissionLog, Verdict  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    seen: list = []
    replies: dict = {}

    def log_message(self, *args):
        pass

    def respond(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        url = urlparse(self.path)
        self.seen.append({"method": self.command, "path": url.path, "query": parse_qs(url.query), "body": body,
                          "headers": dict(self.headers)})
        key = (self.command, url.path.split("/")[-1])
        status, payload = self.replies.get(key, self.replies.get("default", (200, {})))
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = respond


class DresClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("localhost", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://localhost:{cls.server.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.seen, Handler.replies = [], {}
        self.client = DresClient(self.url, timeout=5)

    def login(self):
        Handler.replies[("POST", "login")] = (200, {"id": "u1", "username": "team", "role": "PARTICIPANT",
                                                    "sessionId": "tok en/1"})
        self.client.login("team", "s3cret!")

    def test_login_sends_the_credentials_once_and_keeps_the_session(self):
        self.login()
        self.assertEqual(Handler.seen[0]["body"], {"username": "team", "password": "s3cret!"})
        self.assertEqual(Handler.seen[0]["path"], "/api/v2/login")
        self.assertEqual(Handler.seen[0]["headers"]["Content-Type"], "application/json")
        self.assertIn("Mozilla", Handler.seen[0]["headers"]["User-Agent"])
        self.assertEqual(self.client.session, "tok en/1")

    def test_a_refused_login_does_not_repeat_the_password_in_the_error(self):
        Handler.replies[("POST", "login")] = (401, {"status": False, "description": "Invalid credentials"})
        with self.assertRaises(DresError) as caught:
            self.client.login("team", "s3cret!")
        self.assertEqual((caught.exception.status, str(caught.exception)), (401, "DRES 401: Invalid credentials"))
        self.assertNotIn("s3cret", str(caught.exception))
        Handler.replies[("POST", "login")] = (200, {"id": "u1"})
        with self.assertRaisesRegex(DresError, "without a sessionId"):
            self.client.login("team", "x")

    def test_calls_need_a_session_and_carry_it_as_a_query_parameter(self):
        with self.assertRaisesRegex(DresError, "log in first"):
            self.client.evaluations()
        self.login()
        Handler.replies[("GET", "list")] = (200, [{"id": "e1", "name": "round 1", "status": "ACTIVE"}])
        Handler.replies[("GET", "e%2F1")] = (200, {"name": "task 3", "taskGroup": "kis", "taskType": "KIS"})
        self.assertEqual(self.client.evaluations()[0]["id"], "e1")
        self.assertEqual(self.client.current_task("e/1")["name"], "task 3")
        listing, task = Handler.seen[1], Handler.seen[2]
        self.assertEqual((listing["path"], listing["query"]), ("/api/v2/client/evaluation/list",
                                                               {"session": ["tok en/1"]}))
        self.assertEqual(task["path"], "/api/v2/client/evaluation/currentTask/e%2F1")  # the slash is escaped

    def test_one_answer_goes_in_one_answer_set_and_both_success_codes_are_read(self):
        self.login()
        answer = {"mediaItemName": "L21_V001", "start": 60000, "end": 60000}
        for code, verdict, accepted in ((200, "CORRECT", True), (202, "WRONG", True), (200, "INDETERMINATE", True),
                                        (200, "UNDECIDABLE", True)):
            Handler.replies[("POST", "e1")] = (code, {"status": accepted, "submission": verdict, "description": "ok"})
            self.assertEqual(self.client.submit("e1", answer), Verdict(accepted, verdict, "ok"))
        sent = Handler.seen[-1]
        self.assertEqual(sent["path"], "/api/v2/submit/e1")
        self.assertEqual(sent["body"], {"answerSets": [{"answers": [answer]}]})
        self.assertEqual(sent["query"], {"session": ["tok en/1"]})

    def test_a_refusal_carries_its_status_and_a_reply_that_is_not_json_does_not_crash(self):
        self.login()
        Handler.replies[("POST", "e1")] = (412, {"status": False, "description": "Submission limit reached"})
        with self.assertRaises(DresError) as caught:
            self.client.submit("e1", {"text": "TR-V-1,2"})
        self.assertEqual((caught.exception.status, str(caught.exception)), (412, "DRES 412: Submission limit reached"))
        Handler.replies[("POST", "e1")] = (200, b"<html>gateway</html>")
        with self.assertRaises(DresError) as caught:
            self.client.submit("e1", {"text": "TR-V-1,2"})
        self.assertIsNone(caught.exception.status)  # unknown: the server may have judged it
        self.assertIn("not JSON", str(caught.exception))

    def test_no_server_means_no_status(self):
        with socket.socket() as probe:
            probe.bind(("localhost", 0))
            port = probe.getsockname()[1]
        with self.assertRaises(DresError) as caught:
            DresClient(f"http://localhost:{port}", timeout=2).login("team", "x")
        self.assertIsNone(caught.exception.status)
        self.assertIn("no reply from DRES", str(caught.exception))


class SubmissionLogTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "logs" / "submissions.jsonl"
        self.log = SubmissionLog(self.path)
        self.answer = {"text": "QA-hai người-L21_V001-60000"}

    def test_an_answer_is_sending_before_the_reply_and_never_sent_again_after_it(self):
        self.assertIsNone(self.log.status("e1", "task 3", self.answer))
        self.assertFalse(self.log.sent("e1", "task 3", self.answer))
        self.log.sending("e1", "task 3", self.answer)
        self.assertEqual(self.log.status("e1", "task 3", self.answer), "SENDING")
        self.assertTrue(self.log.sent("e1", "task 3", self.answer))  # no reply yet, so it is not sent again
        self.log.record("e1", "task 3", self.answer, Verdict(True, "WRONG", ""))
        self.assertEqual(self.log.status("e1", "task 3", self.answer), "WRONG")

    def test_only_a_refusal_frees_the_answer_and_it_is_per_task_and_per_answer(self):
        self.log.sending("e1", "task 3", self.answer)
        self.log.failed("e1", "task 3", self.answer, 412)
        self.assertEqual(self.log.status("e1", "task 3", self.answer), "ERROR 412")
        self.assertFalse(self.log.sent("e1", "task 3", self.answer))
        self.log.sending("e1", "task 3", self.answer)
        self.assertTrue(self.log.sent("e1", "task 3", self.answer))
        self.assertFalse(self.log.sent("e1", "task 4", self.answer))
        self.assertFalse(self.log.sent("e2", "task 3", self.answer))
        self.assertFalse(self.log.sent("e1", "task 3", {"text": "other"}))

    def test_it_survives_a_restart_and_a_line_cut_off_by_a_crash(self):
        self.log.sending("e1", "task 3", self.answer)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write('{"evaluation": "e1", "task": "task 3", "ans')  # the process died mid-write
        again = SubmissionLog(self.path)
        self.assertEqual(again.status("e1", "task 3", self.answer), "SENDING")
        again.record("e1", "task 3", self.answer, Verdict(True, "CORRECT", ""))
        self.assertEqual(SubmissionLog(self.path).status("e1", "task 3", self.answer), "CORRECT")
        self.assertIn("hai người", self.path.read_text(encoding="utf-8"))  # accents kept, not escaped

    def test_an_answer_with_a_unicode_line_separator_stays_one_entry(self):
        answer = {"text": "QA-hai\u2028người\x85ba-V-1"}  # str.splitlines() would cut at both
        self.log.sending("e1", "task 3", answer)
        self.log.record("e1", "task 3", answer, Verdict(True, "CORRECT", ""))
        self.assertEqual(self.log.status("e1", "task 3", answer), "CORRECT")
        self.assertEqual(len(self.log.entries()), 2)

    def test_a_line_cut_inside_an_accented_letter_is_survived_too(self):
        self.log.sending("e1", "task 3", self.answer)
        with self.path.open("ab") as handle:
            handle.write('{"answer": "người"}'.encode("utf-8")[:-4])  # ends in half of "ờ"
        self.log.record("e1", "task 3", self.answer, Verdict(True, "WRONG", ""))
        self.assertEqual(SubmissionLog(self.path).status("e1", "task 3", self.answer), "WRONG")


if __name__ == "__main__":
    unittest.main()
