# 1. Shots and keyframes

**Goal.** Cut every video into shots, pick the keyframes that will be searched, and write the
keyframe map that ties each picture to its frame number and time. Formats:
[README](README.md#the-keyframe-map).

## Run

```bash
python scripts/preprocess.py --videos /path/to/videos
python scripts/preprocess.py --videos /path/to/videos --video L21_V001 --force   # redo one video
python scripts/preprocess.py --reselect     # apply new quality or grouping settings, no decoding
```

`--videos` is searched recursively for `.mp4` files; the file name without `.mp4` is the video id.
`--device cuda:1` picks the device for TransNetV2 (`shots.device` is `auto`: CUDA when there is
one). `--video` is repeatable. `--force` redoes videos already done; the new pictures and
keyframe map replace the old ones only when the whole video has succeeded. `--reselect` applies the
current `quality` and `grouping` settings again from the measurements already in the keyframe maps;
the later steps then redo the videos whose indexed keyframes changed
([README](README.md#offline-from-videos-to-indexes)). A video that fails is reported, the others
go on, and the exit status is 1.

## What happens

1. **Shots.** TransNetV2 scores every frame for "a transition happens here", on a 48×27 copy of
   the video that the `ffmpeg` command-line tool decodes. A frame whose score is above
   `shots.threshold` (0.5, the default of the library) ends a shot.
2. **Covering the video.** `predictions_to_scenes` leaves out the frames of a transition: of a run
   of frames above the threshold, the first ends the previous scene and the others belong to no
   scene. A frame outside every shot can never be returned, so each gap is split at its midpoint
   and the first and last shots are stretched to the ends of the video (`cover()` in
   `src/preprocess/shots.py`). On eight videos (176,286 frames) four had gaps: 17 gaps holding
   19 frames in all, none longer than two frames. The amount is small; the tiling is what matters.
3. **Keyframes.** `keyframes.policy` chooses them:
   - `middle` (default): the middle frame of each shot. Nothing to choose.
   - `dense`: a shot of L frames gets `max(1, L // frame_gap)` slots, `frame_gap` frames apart and
     centred in the shot; each slot takes the sharpest frame within `search_radius` frames of its
     position. You set both numbers.
4. **Decoding and time.** PyAV decodes each video once, in order. A keyframe's time is its own
   `pts × time_base`, and the picture is saved as a JPEG at Pillow's default quality (75).
5. **Measurements.** Sharpness (variance of the Laplacian), brightness (mean grey level) and
   entropy (of the grey-level histogram) are recorded for every keyframe, with a 64-bit dHash.
6. **Frame quality (off by default).** With `quality.enabled`, a keyframe past a threshold is
   marked `rejected` (`blur`, `dark`, `bright`, `flat`) and stays out of the index.
7. **Near-duplicates (off by default).** With `grouping.enabled`, consecutive keyframes of a shot
   whose dHash differ in at most `max_distance` bits form a group. Only the sharpest frame of each
   group is indexed.
8. **Frame-count check.** The number of frames PyAV decoded must equal the number TransNetV2
   scored. Otherwise shot boundaries and frame numbers would refer to different frames, and the
   video fails instead of producing wrong answers. For a video in
   [data/videos.csv](../../data/README.md), the count is also compared with the organisers' copy,
   and a difference is printed as a warning. On the organisers' copies of all 873 videos the
   packet timestamps are evenly spaced (one step size in each file), the first is 0, and there are
   as many packets as `frames` says, so `ffmpeg` has no frame to repeat or drop and neither the
   mismatch nor the first-frame warning below is expected on them.

On the 65-second test video (1,628 frames, 18 shots) the whole step took 4 s on a GPU and 13 s on
CPU, with the same shots and keyframes both ways; a 21-minute video took 77 s. The picture files
are 60 to 90 KB each, at 1280×720 and at 720×1280.

## Choosing the values that have no default

The TransNetV2 threshold has a published default. The keyframe gap and the quality and grouping
thresholds do not: they depend on your videos, your disk and your index size.

### How dense

TRAKE answer ranges are "usually under 10 frames" (organisers). With one keyframe per shot, a
short action inside a long shot has no keyframe near it at all. With `dense`, neighbouring
keyframes are at most `frame_gap + 2 × search_radius` frames apart inside a shot and
`2 × frame_gap − 1 + 2 × search_radius` across a cut, because the slots are centred in each shot.
A range of W frames is therefore sure to hold a keyframe when
`2 × (frame_gap + search_radius) ≤ W`. Frames before the first keyframe of a video, or after the
last, can number up to `frame_gap − 1 + search_radius`. These bounds were reached exactly, and
never exceeded, on the real shot lists of all 873 videos, and no two slots shared a frame.

What a setting costs on those 873 videos (130.7 hours, 12,258,989 frames, 97,811 shots). The
settings are examples to size a choice, not recommendations:

| `frame_gap`, `search_radius` | keyframes | per 1,000 frames | neighbours at most this far apart: inside a shot, across a cut |
|---|---|---|---|
| `middle` policy | 97,811 | 8 | one keyframe per shot |
| 50, 24 | 224,307 | 18 | 98, 147 |
| 25, 12 | 447,903 | 37 | 49, 73 |
| 10, 4 | 1,182,838 | 97 | 18, 27 |
| 5, 2 | 2,413,493 | 197 | 9, 13 |
| 1, 0 | 12,258,989 | 1,000 | 1, 1 |

The cost is pictures on disk, vectors in Milvus and OCR time, all in proportion to the number of
keyframes. A larger `search_radius` also costs decoding time: every frame of every window is
converted and measured, about 18 ms each here, so a window as wide as the gap measures nearly
every frame. With `frame_gap: 25, search_radius: 12` the 21-minute video took 697 s instead of
77 s.

### Quality thresholds

Run once with `quality.enabled: false`, then look at the measured values in the keyframe map. The
scale, on three videos (362 `middle` keyframes, two landscape and one portrait, Vietnamese
television and online video): sharpness median 397 (5th to 95th percentile 66 to 890), brightness median 113 (35 to
183), entropy median 7.4 (5.3 to 7.7). This is the scale, not a threshold: sharpness grows with
resolution and with detail.

Then open the pictures at the extremes. These are what was there:

- **Darkest** (brightness 0 to 14): one all-black frame, two night scenes (firefighters; a fire on a
  hillside) and a dark frame with only a caption box.
- **Blurriest** (sharpness 0 to 20): the same black frame, then three soft frames of a lion dance, close
  up and moving.
- **Lowest entropy** (0 to 1.9): the black frame, and title cards and logos on a plain white
  background, which are also the brightest frames (233 to 249).

So a `dark` threshold removes night footage along with the black frames, and a `flat` or `bright`
one removes the cards that carry text for OCR. A night scene is evidence. Frames are never
deleted, so trying a threshold is cheap: `preprocess.py --reselect` applies it in seconds, and the
index steps redo only the videos whose indexed keyframes changed.

### Grouping distance

A dense run on the same three videos (1,467 keyframes) shows how the number behaves. Consecutive
keyframes of a shot differ by a median of 4 bits (90th percentile 24, largest 45; 165 of 1,105
pairs are identical):

| `max_distance` | keyframes left indexed |
|---|---|
| 0 | 1,302 |
| 2 | 1,017 |
| 4 | 852 |
| 8 | 700 |
| 16 | 560 |

The pairs, by eye: at 0 bits the same picture, though a scrolling ticker at the bottom moves; at 4
and 8 the same scene with small movements; at 16 two pictures of one shot that clearly differ (a
crowd has moved, a red banner appears in one). So a large distance merges frames that differ in
what they show, and a text that appears on only one of them is no longer read. Open a few groups
(same `group` value) before you trust a distance. `--reselect` applies a new one the same way.

## Output

`shots/<video>.jsonl`, `keyframes/<video>.jsonl` and `frames/<video>/*.jpg`. The keyframe map is
written last: a video without one is not done, and the next run redoes it. A video that fails
leaves its earlier output as it was.

## Check

```bash
python - <<'EOF'
import json
shots = [json.loads(l) for l in open("data/shots/L21_V001.jsonl")]
assert shots[0]["start_frame"] == 0
assert all(a["end_frame"] + 1 == b["start_frame"] for a, b in zip(shots, shots[1:]))   # no gap, no overlap
keyframes = [json.loads(l) for l in open("data/keyframes/L21_V001.jsonl")]
print(len(shots), "shots,", len(keyframes), "keyframes,", sum(k["indexed"] for k in keyframes), "indexed")
EOF
```

Then open a few pictures and compare each with the video at its frame index
([README](README.md#frame-numbers) has the `ffmpeg` command); the saved picture is a JPEG, so it
matches closely, not bit for bit.

## Lessons

- **A shot list that does not cover the video loses answers silently.** Nothing fails; the missing
  frames are simply never found. Check every video, not a sample.
- **Time from PTS.** `frame_index / fps` is only right for constant-frame-rate video, and it is
  the time that is submitted to DRES for KIS and Q&A. On a 30-second test video with 41 frames
  cut out, frame 100 is at 5,640 ms by its timestamp, 4,231 ms by index over the average rate
  and 4,000 ms by index over 25 fps.
- **Keep what you filter.** Quality and grouping only decide what goes into the index. The picture
  and its line in the keyframe map stay, so any frame can still be inspected, stepped to and
  submitted.
- **Look before you filter.** The darkest, blurriest and flattest frames are not all bad ones
  (see above).
- **The frame-count check does not see damaged pictures.** A copy with 4,000 bytes overwritten in
  the middle of the file decoded without an error, to the same frame count as `ffprobe`, and
  passed. If a download may have been cut short, compare file sizes or checksums with the source.
- **Mark a video done only when all of it is written.** Resuming then never has to guess which
  half-written file is complete.

## Troubleshooting

The messages are as printed on test videos made for each case.

| Symptom | Cause and fix |
|---|---|
| `FAILED FrameCountMismatch: <video>: PyAV decoded 709 frames, TransNetV2 saw 750` | TransNetV2 gets its frames from the `ffmpeg` tool, which repeats frames to fill a gap in the timestamps; PyAV does not. The test video had 41 frames cut out of it: `ffmpeg` gave 750 frames (41 of them repeats), and 709 with `-vsync passthrough`. A video with irregular timestamps (variable frame rate) can do this. The video is skipped, the others continue, and its earlier output is left as it was. Look at the file with `ffprobe` |
| `WARNING <video>: this copy has 500 frames, the organisers' copy has 1628 (25 fps); its frame numbers will not match their answers` | your file is not the organisers' copy (another download or encoding, or cut short). Use their copy, or one whose `fps` and `frames` match [data/videos.csv](../../data/README.md) |
| `WARNING <video>: the first frame is at 1500 ms, not 0; all its times are counted from the stream's own zero` | the stream starts at a non-zero timestamp. Times written to the keyframe map, and sent to DRES, are counted from that zero, which a player may not show. Check how the organisers count time for such a file |
| `"time_source": "index"` in the keyframe map | the stream carried no timestamps (a raw H.264 file renamed `.mp4` was the test), so each time is `frame_index / fps`. No warning is printed |
| `FAILED Error: ffmpeg error (see stderr output for detail)` | `ffmpeg` cannot read the file: it is damaged, or not a video (a file of random bytes was the test). Check it with `ffprobe` |
| `FAILED FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'` | TransNetV2 decodes with the `ffmpeg` command-line tool: install it ([setup.md](../setup.md)) |
| `` FAILED ModuleNotFoundError: For `predict_video` function `ffmpeg` needs to be installed ... `` | the Python wrapper is missing: `pip install ffmpeg-python` |
| `` error: <config>: set `keyframes.dense.frame_gap` -- no published default; ... `` | `policy: dense` needs both `frame_gap` and `search_radius` |
| `error: dense keyframes need frame_gap >= 1 and 2 * search_radius < frame_gap, ...` | two slots would share a frame; lower the radius |
| `error: <config>:quality: quality is enabled but no threshold is set` | set at least one threshold, or turn quality off |
| `` error: <config>: set `grouping.max_distance` -- no published default; ... `` | grouping needs a distance |
| slow | on CPU the 65-second test video took 13 s, about three times the GPU's, on a machine with 40 cores; `dense` with a wide window costs decoding time (see above) |
