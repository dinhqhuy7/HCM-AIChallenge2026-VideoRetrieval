# Submission

Two ways answers leave the system: CSV files for a qualifying round, and single answers sent to a
DRES server in a live round. Both are built from the same three answer classes in
`src/submission/answers.py`. One class per task produces both the CSV row and the DRES answer, so
the two formats cannot drift apart.

## CSV files

One file per query, named after the query file (`query-p1-1-kis.txt` → `query-p1-1-kis.csv`), no
header, at most 100 rows, best first:

| Task | Row | Example |
|---|---|---|
| KIS | `video_id,frame_id` | `L23_V005,2428` |
| Q&A | `video_id,frame_id,answer` | `L23_V005,2428,hai người` |
| TRAKE | `video_id,frame_id_1,...,frame_id_n` | `L23_V005,2428,3185,3658` |

```bash
for query in queries/query-*-kis.txt queries/query-*-trake.txt; do
    python scripts/search.py --query-file "$query" --out-dir submission
done
```

Q&A files also need `--answer`, written on every row. The answer is normalised to Unicode NFC with
single spaces: `"  hai   người "` is written `hai người`, so the same answer typed on two keyboards
is one string.

`video_id` is the video file name without its extension. `frame_id` is the frame index plus
`submission.frame_id_base`. The organisers' keyframe maps count `frame_idx` from 0, so the default
is 0; if the rules of your round count frames from 1, set it to 1 (index 2428 becomes 2429). See
[offline/README.md](offline/README.md#frame-numbers).

The writer refuses what a file may not hold: more than 100 rows (`101 rows; the organisers accept at
most 100`), a TRAKE chain with fewer than two frames or frames out of order (`a TRAKE chain needs
two or more frames in time order`), a Q&A row without an answer, a missing video id, a negative
frame. The file is written to a temporary name and moved into place, so it is the old file or the
new one, never half of one.

## DRES

A live round is judged on DRES, the Distributed Retrieval Evaluation Server (Sauter, Gasser,
Schuldt, Bernstein and Rossetto, "Performance Evaluation in Multimedia Retrieval", ACM Transactions
on Multimedia Computing, Communications and Applications, 2024,
[doi:10.1145/3678881](https://doi.org/10.1145/3678881)). The client in `src/submission/dres.py` uses
the client API v2 as the specification describes it, `doc/oas-client.json` in
[dres-dev/DRES](https://github.com/dres-dev/DRES):

| Call | Sends | Gets |
|---|---|---|
| `POST /api/v2/login` | `{username, password}` | `ApiUser`: `id`, `username`, `role`, `sessionId` |
| `GET /api/v2/client/evaluation/list?session=…` | | the evaluations (`id`, `name`, `type`, `status` ...); the one running is `ACTIVE` |
| `GET /api/v2/client/evaluation/currentTask/{evaluationId}?session=…` | | the task running now (`name`, `taskGroup`, `taskType`, `duration`) |
| `POST /api/v2/submit/{evaluationId}?session=…` | `{"answerSets": [{"answers": [ApiClientAnswer]}]}` | `{status, submission, description}`; `submission` is the verdict |

The verdict is one of `CORRECT`, `WRONG`, `INDETERMINATE` or `UNDECIDABLE`. The specification lets
a submit answer 200 (verdict available), 202 (accepted, verdict pending) or an error 400, 401, 404 or
412. The session token travels in the URL (`?session=…`), so do not paste request URLs into an issue
or a chat.

### The three answer shapes

| Task | `ApiClientAnswer` |
|---|---|
| KIS | `{"mediaItemName": "<video_id>", "start": <ms>, "end": <ms>}` |
| Q&A | `{"text": "QA-<answer>-<video_id>-<ms>"}` |
| TRAKE | `{"text": "TR-<video_id>-<frame_id_1>,<frame_id_2>,..."}` |

For `L23_V005`, frame 2428 at 97,120 ms, and the chain 2428, 3185, 3658:

```text
{"mediaItemName": "L23_V005", "start": 97120, "end": 97120}
{"text": "QA-hai người-L23_V005-97120"}
{"text": "TR-L23_V005-2428,3185,3658"}
```

`start` and `end` are int64 **milliseconds** in the specification: the frame's presentation time,
which `submission.frame_id_base` does not change. TRAKE carries **frame numbers**, not times, and
those do move with the base. A frame number where a millisecond belongs is a wrong answer that looks
entirely reasonable. The `QA-` and `TR-` text templates are **the organisers'**, not DRES's: the
specification only gives `text` as an optional string. They follow the instructions given for this
challenge; take them from your own round's rules, and change them in `answers.py` if yours differ.
Because the Q&A template joins its parts with `-`, an answer containing `-` is refused, and
before anything is typed: `error: a Q&A answer sent to DRES cannot contain '-'`.

### Sending one answer

```bash
python scripts/search.py kis --text "..." --submit 1
```

Set `submission.dres.base_url` in `configs/search.yaml` to the address the organisers give you.
Without it the command stops before it searches: ``error: <config>: set `submission.dres.base_url` --
the DRES address the organisers give you``. Then:

1. The search runs and prints its rows. Row 1 (or the row you name) is the answer.
2. You type the DRES username; the password is read with `getpass`. It is never a command-line
   argument, where the shell history and the process list would keep it. Typing it into a pipe
   works but is echoed (`Warning: Password input may be echoed.`): use a terminal.
3. The running evaluation is found (you choose if several are running), with its current task.
4. The answer is shown, and nothing is sent until you type `y`:

   ```text
   row 1, task 'kis-01': {'mediaItemName': 'L30_V040', 'start': 26080, 'end': 26080}
   send? [y/N]
   ```

5. The verdict is printed (`WRONG: Submission incorrect`) and the answer recorded in
   `data/submissions.jsonl`.

### What the client refuses, and how it ends

Everything below was run against a stand-in server that answers like the specification.

| Situation | What you see | State afterwards |
|---|---|---|
| a second send of the same answer for the same task | `this answer was already sent for this task (WRONG); a repeat would only cost an attempt` | nothing is sent |
| you type `n` at `send?` | nothing | nothing is sent or logged |
| no evaluation is `ACTIVE` | `no evaluation is running` | nothing is sent |
| wrong user or password | `error: DRES 401: <the server's description>` | nothing is sent |
| the server refuses the request (412) | `error: DRES 412: <description>` | the log says `ERROR 412`; the answer **may be sent again** |
| the verdict is pending (202) | `INDETERMINATE: <description>` | recorded |
| no reply arrives (connection dropped, timeout after 20 s) | `No usable reply came back. The answer is kept as SENDING and will not be sent again by this script: look at DRES to see whether it was judged.`, then `error: no reply from DRES: ...` | the log says `SENDING` |
| the same answer after a lost reply | `this answer was sent for this task before and no reply came back; the server may have judged it: check DRES before sending anything else` | nothing is sent |

An answer is written to the log, and to disk, **before** the request. If the reply never comes the
server may still have judged it, so `SENDING` is not cleared by sending again: look at the DRES
scoreboard first. Only an HTTP error, where the server answered that it refused the request, frees
the answer. The log holds the evaluation, the task, the answer and the state, one line each time
the state changes:

```text
{"evaluation": "eval-1", "task": "kis-01", "answer": "{\"text\": \"QA-hai người-L30_V040-26080\"}", "verdict": "SENDING"}
{"evaluation": "eval-1", "task": "kis-01", "answer": "{\"text\": \"QA-hai người-L30_V040-26080\"}", "verdict": "WRONG"}
```

Neither the password nor the session token appeared in the log, the CSV files or any output in
these runs. A crash can leave a last line without its newline, or cut inside an accented letter;
the log is read and written as bytes, so the next entry starts on a line of its own and an
unreadable line is skipped.

The rules the client keeps: **one answer per request** (no batches), **no repeats** (checked
locally, before it costs an attempt) and **the verdict read out**, not raw JSON.

## Lessons

- **Every row counts in a qualifier.** The order of the rows is the score and an empty row cannot
  score ([online.md](online.md#result-shaping)). Fill the list to 100 when there are candidates.
- **In a live round, send less, and later.** Find the video, confirm it with other evidence
  (on-screen text, speech), step through the frames around the moment, then send one answer.
- **Build each answer shape in one place, and test it.** The three shapes differ in ways that are
  easy to get wrong and hard to notice: milliseconds against frame numbers, a dash inside an
  answer, two spellings of the same Vietnamese word.
- **A proxy can refuse the client before DRES sees it.** A server behind a proxy once answered 403
  (Cloudflare error 1010) to Python's default User-Agent, so the client sends its own
  (`USER_AGENT` in `dres.py`). This was not reproduced for this page: the stand-in server only
  confirmed the header is sent.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `error: DRES 401: ...` | wrong username or password, or the session expired: run again to log in |
| `error: DRES 403: ...` with Cloudflare error 1010 in the body | a proxy in front of the server refuses the User-Agent; see the last lesson |
| `no evaluation is running` | nothing is `ACTIVE` yet; wait for the round to start |
| `this answer was already sent for this task (...)` | by design; pick another row |
| `this answer was sent for this task before and no reply came back ...` | the state is `SENDING`; check the DRES scoreboard, do not resubmit by hand without looking |
| `error: a Q&A answer sent to DRES cannot contain '-'` | rewrite the answer without the dash |
| ``error: ...: set `submission.dres.base_url` ...`` | fill in the address in `configs/search.yaml` |
| `GetPassWarning: Can not control echo on the terminal` / `Warning: Password input may be echoed.` | the password was read from a pipe, not a terminal; run it in a terminal |
