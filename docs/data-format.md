# Data format

`StaticProvider` reads plain files, so any system can publish a demo like this
one by writing them. Paths are relative to the site root.

```text
data/queries.json              sample queries
data/videos.json               one entry per video
data/results/<query id>.json   recorded ranking of one query
data/videos/<video id>.json    frames and words of one video
data/keywords/index.json       which keyword files exist
data/keywords/<xyz>.json       words starting with the letters xyz
img/<video id>/<frame>.webp    a single frame
sprites/<video id>/<row>.webp  pictures of 10 scenes side by side
```

## Frames

A frame is written as the tuple `[videoId, frameIdx, seconds, tile]`.
`frameIdx` is the frame number in the source video, as the competition counts
it. When `tile` is `null` the picture is `img/<videoId>/<frameIdx>.webp`;
otherwise it is cell `tile % 10` of the strip `sprites/<videoId>/<tile div 10>.webp`,
counted from the left, every cell 16:9. Small strips mean a page that shows a
few scenes of many videos loads a few kilobytes per scene, not whole videos.

## Files

`queries.json` — an array, in display order:

```json
[{ "id": "r2-p2-8", "round": 2, "task": "trake", "text": "<query as written by the organisers>",
   "stages": ["<event 1>", "<event 2>"] }]
```

`task` is `kis`, `qa` or `trake`; only `trake` has `stages`, one per event in
order. `text` and `stages` keep the organisers' own Vietnamese wording.

`videos.json` — `{ "<videoId>": { "title": "", "youtube": "<YouTube id>", "embed": true } }`.
`embed` is false when the owner blocks playback on other sites.

`results/<id>.json` — `{ "frames": [tuple, …] }` best first; for TRAKE
`{ "stages": [[tuple, …], …], "chains": [[tuple, …], …] }`, one list per stage
and one tuple per stage in each chain.

`videos/<videoId>.json`:

```text
{ "frames":   [[frameIdx, seconds, tile, [similar tuple, …]], …],
  "onScreen": [{ "time": 12.0, "until": 15.2, "text": "words read on screen in this scene" }],
  "speech":   [{ "time": 14.5, "text": "words spoken from here" }] }
```

`frames` lists every frame of the video that has a picture, in time order.
`onScreen` has one entry per scene: `time` and `until` are its first and last
frame, both included.

`keywords/index.json` — the keyword files present, e.g. `["bao", "lu"]`: a word
lives in the file named by its first three letters (a two-letter word by both).
`keywords/<xyz>.json` — `{ "<word>": [tuple, …] }`. Words are folded exactly
as `src/core/vietnamese-text.js` folds typed text: lower case, accents and
the stroke of the Vietnamese d removed, split on anything but `a-z0-9`. Words
shorter than two letters are not indexed. Test your folding against
`tests/fixtures/normalize.json`.

## Checking your files

`tests/fixtures/site/` is a complete three-video example in this format, and
`node --test` exercises the provider against it.
