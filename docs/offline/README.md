# Offline: from videos to indexes

Run the steps in this order. Each one skips the videos it has already done, so a command can be
run again after an interruption.

| # | Command | Environment | Guide |
|---|---|---|---|
| 1 | `python scripts/preprocess.py --videos VIDEOS` | main | [01-shots-and-keyframes](01-shots-and-keyframes.md) |
| 2 | `python scripts/build_index.py visual` | main | [02-visual-index](02-visual-index.md) |
| 3 | `python scripts/build_index.py ocr` | ocr | [03-ocr](03-ocr.md) |
| 4 | `python scripts/build_index.py asr --videos VIDEOS` | main | [04-asr](04-asr.md) |
| 5 | `python scripts/build_index.py objects` (optional) | objects | [below](#objects-optional) |
| 6 | `python scripts/build_index.py keywords` | any | [03-ocr](03-ocr.md#keyword-index), [04-asr](04-asr.md#keyword-index) |

Steps 2 to 5 only read the output of step 1, so they can run in any order, or at the same time
on different GPUs (not step 2 and `search.py` on one Milvus Lite file: [setup.md](../setup.md#milvus-lite-the-default)).
Step 6 rebuilds the keyword index of every lane that has evidence, from all videos; run it again
whenever OCR, speech or objects change. Run the commands from anywhere: paths are taken from the
repository, not from the current folder. A step that fails on one video says so, goes on with the
others, and exits with status 1 and the list of the videos that failed. `build_index.py` takes:

| Option | Meaning |
|---|---|
| `--data` | the data folder (default `data`) |
| `--config` | another settings file |
| `--video ID` | only this video; repeatable (`keywords` always uses every video) |
| `--device` | where the step's model runs, e.g. `cuda:1` or `cpu`; overrides the config |
| `--force` | redo videos even when their output is current |

**When a step redoes a video.** Preprocessing decides which keyframes exist and which are
indexed. The visual, OCR and object steps compare what they hold for a video (rows in Milvus,
lines in the evidence file) with the video's indexed keyframes, and redo the video when the two
differ, for example after `preprocess.py --force` or `--reselect`. A video that stopped halfway
no longer matches, so it is done again. Speech depends on the video file only and is kept.
`keywords` warns about evidence older than its keyframe map.

## Data layout

```text
data/
  videos.csv, README.md        the video list, part of the repository (see ../../data/README.md)
  shots/<video>.jsonl          shot ranges
  keyframes/<video>.jsonl      the keyframe map (written last: its presence means the video is done)
  frames/<video>/<video>_<frame index, 6 digits>.jpg
  ocr/<video>.jsonl            lines read on each indexed keyframe
  asr/<video>.jsonl            speech segments
  objects/<video>.jsonl        objects on each indexed keyframe (optional)
  index/milvus.db              Milvus Lite, one collection per encoder
  index/keywords-ocr.json      BM25 over OCR text, one document per shot
  index/keywords-asr.json      BM25 over speech
  index/keywords-objects.json  BM25 over object labels
  submissions.jsonl            every answer sent to DRES (see ../submission.md)
```

Everything except the video list is written by the scripts and ignored by git. The video id is
the file name without its extension (`L21_V001.mp4` becomes `L21_V001`).

## Frame numbers

`frame_index` counts frames in the order the decoder returns them (presentation order), **the
first frame being 0**: the same counting as PyAV's decoder, as TransNetV2's predictions, and as
FFmpeg's `select=eq(n\,N)`. For a video at a constant frame rate, frame `n` is at `n * 1000 / fps`
milliseconds; `time_ms` is read from the frame's own timestamp, which also holds when the rate
varies.

The number written into a submission is `frame_index + submission.frame_id_base`
(`configs/search.yaml`, default 0). If the rules of your round count frames from 1, set it to 1.
It is one setting, applied in one place (`src/submission/answers.py`).

To look at a frame by its index:

```bash
ffmpeg -i L21_V001.mp4 -vf 'select=eq(n\,122)' -vsync 0 -frames:v 1 frame_122.png
```

(`-vsync 0` is FFmpeg 4.4; newer versions call it `-fps_mode passthrough`.) The frame it writes
is the one PyAV decodes at index 122: the two were identical, pixel for pixel, on the frames
tested.

**The organisers' keyframe maps.** The maps released for the 2025 collection have the columns
`n,pts_time,fps,frame_idx`, and the first row of every file is `1,0.0,<fps>,0`, so `frame_idx`
counts from 0 as here. They are not consistent with themselves: for the 25 fps videos, where
times are exact multiples of 0.04 s, 7,277 of 149,599 rows (4.9%, in 770 of the 781 videos at that rate) have
`pts_time` equal to `(frame_idx + 1) / fps` instead of `frame_idx / fps`. Which column is right
was not determined. This system uses neither file; it measures its own times from the videos.

## The keyframe map

One JSON line per keyframe, in time order. This is the record every search result is traced back
through: from a vector, a text line or a speech segment, to a keyframe, to a frame number and a
millisecond. This is a line of the file written for a 65-second video:

```json
{"video_id": "L30_V040", "keyframe_id": "L30_V040_000122", "shot_id": 1, "frame_index": 122,
 "time_ms": 4880, "pts": 62464, "time_base": "1/12800", "time_source": "pts",
 "image": "frames/L30_V040/L30_V040_000122.jpg",
 "sharpness": 271.89, "brightness": 241.6, "entropy": 1.4573, "dhash": "004d169a9e964d08",
 "rejected": null, "group": 1, "indexed": true}
```

| Field | Meaning |
|---|---|
| `keyframe_id` | `<video_id>_<frame_index>`, 6 digits; also the picture's file name |
| `shot_id` | the shot it belongs to, from 0 |
| `frame_index` | position in presentation order, from 0 (see above) |
| `time_ms` | presentation time: `pts × time_base`, in milliseconds |
| `pts`, `time_base` | the frame's own timestamp, as the container stores it |
| `time_source` | `pts`, or `index` when the stream carried no timestamp and `frame_index / fps` was used |
| `image` | the picture, relative to the data folder |
| `sharpness`, `brightness`, `entropy` | measured on every keyframe ([01-shots-and-keyframes](01-shots-and-keyframes.md)) |
| `dhash` | 64-bit difference hash, hex, for near-duplicate grouping |
| `rejected` | why the frame stays out of the index (`blur`, `dark`, `bright`, `flat`), or `null` |
| `group` | near-duplicate group; `null` for a rejected frame |
| `indexed` | whether the frame is embedded, read by OCR and searched |

Rejected and grouped-away keyframes keep their picture and their line in the map, so every frame
can still be looked at and submitted.

## Shots

```json
{"video_id": "L30_V040", "shot_id": 1, "start_frame": 75, "end_frame": 169, "start_ms": 3000, "end_ms": 6800}
```

`start_frame` and `end_frame` are both inclusive. `start_ms` is the time of the first frame,
`end_ms` the time of the first frame of the next shot (for the last shot, the end of the video).
Shots tile the video: every frame belongs to exactly one.

## Objects (optional)

Off by default. The object lane needs Ultralytics (AGPL-3.0), in its own environment
([setup.md](../setup.md#objects-optional)).

1. In `configs/index.yaml`, set `objects.enabled: true` and list the object names to look for in
   `objects.classes` (the text prompts, e.g. `[person, car, motorcycle, flag]`).
2. `python scripts/build_index.py objects` writes `objects/<video>.jsonl`: for each indexed
   keyframe, `{"keyframe_id", "objects": [{"label", "score", "box"}]}`, with the box as fractions
   of the picture's size.
3. `python scripts/build_index.py keywords` then builds `keywords-objects.json`. A shot's document
   repeats a label as many times as it appears on the keyframe where it appears most, so three
   people in one frame count three.

`conf`, `iou` and `imgsz` are left to Ultralytics (0.25, 0.7 and 640 when predicting in version
8.4). Pictures go to YOLOE one at a time: given a list, Ultralytics runs all of them as one batch,
which a whole video does not fit in. At these thresholds one object can get two boxes and the
counts run high ([models.md](../models.md)). The step ran end to end on two videos, one landscape
and one portrait.
