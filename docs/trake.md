# TRAKE: chains of events

A TRAKE query describes events E1 … En that happen in one video, in order. The answer is the video
and one frame per event. A row of a wrong video scores zero; in the right video it scores the share
of events whose frame falls inside that event's answer range, which is "usually under 10 frames"
(the organisers' information document for the round).

```bash
python scripts/search.py trake --event "cyclists riding on a road" \
                               --event "a tractor on a field" \
                               --event "people watching a race" --out runs/trake-1.csv
python scripts/search.py --query-file query-p2-21-trake.txt --out-dir submission
```

TRAKE searches its events with the visual box only; `--text`, `--ocr`, `--asr` and `--objects` do
not apply, and at least two events are needed.

## Two stages

1. **Find the videos.** Each event is searched over the whole collection (`depth` frames per
   event). A video scores the sum, over the events, of its best frame for that event. The best
   `rows` videos are candidates.
2. **Align inside each candidate.** All the indexed keyframes of the video are read back from Milvus
   with their vectors and scored against every event. Dynamic programming then finds the best chain:
   one keyframe per event, in time order, with the highest total score. It finds one chain for every
   keyframe that can start one.

## Why the chain is searched as a whole

Take the best frame of each event on its own, and a later event can land before an earlier one. On a
dense index of three videos, with 60 random three-event queries, the best frames taken one by one
were not in time order in 55 of them. The chain that does keep the order had a total only 0.025
lower on average (0.127 at most): the wrong order scores almost as much as the right one, and only
the order constraint tells them apart. It can only be applied to a chain.

The chain's score is the **sum** of its events' scores, not the mean. With a mean, a chain can gain
by dropping its weakest event; with a sum it cannot. Every keyframe of a candidate video is scored,
so every event always has a frame and every chain is complete.

## Rules (`configs/search.yaml`, `trake:`)

| Key | Meaning | Default |
|---|---|---|
| `order` | `strict`: each event after the previous one. `loose`: the same frame may serve two events | `strict` |
| `min_gap_ms`, `max_gap_ms` | bounds on the time between consecutive events | open |
| `spread` | order the rows by video turns: the best chain of every video, then every second best ... | off |

`order` and the gaps are checked when the command starts: `error: order must be 'strict' or
'loose'`, and `error: min_gap_ms must not be larger than max_gap_ms`. With the same event twice,
`strict` gave two frames 1.28 s apart (5661 and 5693 at 25 fps) and `loose` gave 5661 twice.

**Read the time words in the query and set the gaps.** The query says how close the events are
("liên tiếp", "ngay sau đó", "một lúc sau"), and the code cannot know what that means in seconds
for your videos. For four events on the test index, with the gaps open the best chain ran from 97 s
to 224 s of the video and the median of the 100 rows spanned 160 s. With `max_gap_ms: 10000` the
best chain was `[118.4, 125.5, 127.4, 128.7]` s and the median span 14 s; with 3000, 5 s. No published
value exists, and these two are examples: choose from your own queries. A `min_gap_ms` that does not
bind changes nothing (5000 gave the same chain).

**Spread over videos.** A wrong video loses the whole row, however well its frames line up. With
`spread: true`, the first rows cover as many candidate videos as possible before any video gets a
second chain.

## What the 100 rows are, and are not

Stage 2 returns one chain for every starting keyframe, so the rows of a video differ mainly in their
first frame and **share their tails**. On the dense test index, three events, 100 rows:

| | videos | distinct first frames | distinct tails (frames after the first) |
|---|---|---|---|
| `spread: false` | 1 | 100 | 1 |
| `spread: true` | 3 | 99 | 11 |

(With four events the tails were 1 and 11, with five 1 and 17, with two 2 and 9.) The example above
shows it: row after row ends in the same two frames, 3185 and 3658. So the list answers "where does
the first event happen" with 100 options and the later events with very few. `spread` brings in
other videos, which is what protects against a wrong video, but inside one video the later events
stay the same. If the last events are where your answer is wrong, look at the frames around them
by hand, or rerun with the later events described differently, rather than reading further down the
list. Making the rows diverse in their tails is not done here.

## Output

`video_id,f1,…,fn`, one chain per row, at most 100 rows, no header; the frame numbers as in
[offline/README.md](offline/README.md#frame-numbers):

```text
L23_V005,2428,3185,3658
L23_V005,2959,3185,3658
```

## Cost

The query is embedded once per event, stage 1 is one search per event, and stage 2 reads back and
scores each candidate video. On the dense test index (334 keyframes) a whole query took 300 to 370 ms
for two to five events, and the command 15 s from start to finish, most of it loading the model. Stage 2 cost
15 ms for 500 keyframes and three events, 94 ms for 3,000, 166 ms for 3,000 and five events, and
346 ms for 7,500 and four events, per video, and it runs over as many videos as there are rows. A
query on a full collection, with up to 100 candidate videos, can therefore take seconds to tens of
seconds (arithmetic from those per-video times, not a run).

## Lessons

- **Split the events yourself.** The organisers number them (E1, E2 ... or Cảnh 1 ...), and
  `--query-file` splits on those markers; a person still has to read the query to check the answer.
- **"The first time" is a constraint.** A query that asks for the *first* moment an action happens
  wants the earliest occurrence in the video, not the best-looking one. Look at the earlier
  candidates in the chosen video before you submit.
- **Confirm the video before you submit.** The video decides everything, so check it with evidence
  that does not come from pixels: a rare phrase from the query, searched with `--ocr` or `--asr`,
  should find the same video.
- **Dense keyframes matter most here.** With one keyframe per shot, a short action inside a long shot
  has no frame near it. A range of W frames is sure to hold a keyframe only when
  `2 × (frame_gap + search_radius) ≤ W` ([offline/01-shots-and-keyframes.md](offline/01-shots-and-keyframes.md#how-dense)).

## Troubleshooting

The messages are as printed in tests that caused each one.

| Symptom | Cause and fix |
|---|---|
| `search.py: error: TRAKE needs the events one by one: --event ... --event ... (or E1/E2 lines in the file)` | give two or more `--event`, or a file whose lines start with E1, E2 ... |
| `search.py: error: TRAKE searches its events with the visual lane only: give them with --event, ...` | `--text`, `--ocr`, `--asr` or `--objects` was given |
| `error: min_gap_ms must not be larger than max_gap_ms` | the two bounds in `configs/search.yaml` contradict |
| `error: order must be 'strict' or 'loose'` | `trake.order` is something else |
| chains spread over the whole video | set `max_gap_ms` from the query's time words |
| every row in one video | `spread: true` |
