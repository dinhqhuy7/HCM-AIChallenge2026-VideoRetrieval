# 4. Speech (ASR)

**Goal.** Transcribe what is said in every video, with times, and make it searchable per shot.

## Run

```bash
python scripts/build_index.py asr --videos /path/to/videos      # --device cuda:1 for another card
python scripts/build_index.py keywords
```

`--videos` is needed because speech is read from the video files themselves: the folder is
searched recursively and the file name without `.mp4` is the video id. Speech does not depend on
the keyframes, so `preprocess.py --reselect` does not make it stale. `--video ID` (repeatable)
limits the step, `--force` redoes videos that are done, and a video that fails is reported, the
others go on, and the exit status is 1.

The model is `large-v3`. faster-whisper downloads it from `Systran/faster-whisper-large-v3` into
the Hugging Face cache (3.1 GB), or `asr.model` can be a local folder that holds it.

## What happens

1. faster-whisper loads the model with its own `device` and `compute_type` defaults. It takes the
   card number separately (`device_index`), so `cuda:1` is split for it.
2. `transcribe()` runs with `language: vi` and `vad_filter: true`. Every other option keeps
   faster-whisper's default: beam size 5, temperature fallback from 0.0 to 1.0,
   `condition_on_previous_text=True`, and so on. Any other `transcribe()` option can be added under
   `asr:` in `configs/index.yaml`; it is passed on as it is.
3. Segments containing a phrase from `asr.drop_phrases` are dropped. The list is empty by default;
   see Lessons.
4. Each segment is written with its start and end in milliseconds, on the same clock as the
   keyframes. faster-whisper counts from the first sample of the audio track, so the track's own
   start is added; on a test copy whose audio started 2 s late every segment moved by 2,000 ms. All
   873 contest videos start audio and video at 0.000 s, and their audio ends between 0.003 s before
   and 0.093 s after the video. A file with no audio track gives no segments and no error.

### Cost

On one RTX 2080 Ti shared with other jobs, a 243-second video (63 segments), with `vad_filter: true`:

| `compute_type` | GPU memory | time | characters of text |
|---|---|---|---|
| `null` (the default; `float16`: the same) | 4.27 GiB | 22.8 s (21.6 s) | 2,911 |
| `int8_float16` | 2.76 GiB | 28.8 s | 2,899 |
| `int8` | 2.73 GiB | 27.0 s | 2,899 |

Loading took 8 to 11 s. `int8` takes about a third less memory, not half, and a few words come out
differently (`Trong Thếp Vĩnh Long` and `Châu Thế Vĩnh Long` for the same name). `float16` is refused
on a CPU (`ValueError: Requested float16 compute type, but the target device or backend do not
support efficient float16 computation.`); on 40 CPU cores `int8` took 33 s for 30 s of audio, and the
default 70 s (`float32` explicitly, 77 s). At about ten times real time on the GPU, the 130.7 hours of
the 873 videos would take about 13 hours (arithmetic, not a run).

## Keyword index

`build_index.py keywords` joins speech to shots:

- **A segment is attached, whole, to every shot its time span touches.** Speech does not stop at
  shot boundaries. Cutting it there splits a phrase in two ("Châu Âu" into "Châu" and "Âu"), and a
  search for the phrase finds neither half. On the 873 videos (115,817 segments), 44.9% of the
  segments span a cut and a segment touches 1.62 shots on average; the median segment is 2.6 s and
  the median shot 2.7 s. A shot gets a median of 2 segments (90th percentile 3, largest 608). The
  first segment of one test video lasts 18.6 s and lands on seven shots.
- `asr.shot_padding_ms` widens each segment on both sides before the join, since the voice often
  runs ahead of the picture it belongs to. It is 0 by default: no published value exists. Measure how
  far speech and picture drift apart on your videos, then decide.
- Inside a shot, the hit points at the indexed keyframe nearest to the moment the segment starts.
- BM25 with the same settings and the same mark-free matching as OCR
  ([03-ocr](03-ocr.md#keyword-index)).

## Output

`asr/<video>.jsonl`, one segment per line. The first lines of a test video:

```json
{"start_ms": 540, "end_ms": 19140, "text": "Được thành lập từ tháng 4 năm 2019 bởi một cặp đôi 9X,"}
{"start_ms": 19520, "end_ms": 23420, "text": "vườn mèo lang thang đã trở thành mái âm chung của những chú mèo bị bỏ rơi và bạo hành."}
{"start_ms": 24160, "end_ms": 28380, "text": "Trạm cứu hộ này đã giải cứu mèo ở hầu hết các quận, huyện trên địa bàn TP.HCM,"}
```

(In English: "Founded in April 2019 by a couple, born in the 1990s, ..." / "... has become a home for abandoned and abused cats." / "This rescue station has rescued cats in most districts of Ho Chi Minh City,").

The keyword index is `index/keywords-asr.json`.

## Check

```bash
python scripts/search.py kis --asr "a phrase you can hear"
```

Play the video around a returned time and listen. On the test video, `--asr "trạm cứu hộ"` ("rescue
station") returned first the keyframe at 26.1 s, inside the segment above (24.2 to 28.4 s).

## Lessons

- **With its default settings, Whisper invented speech.** On the first 4 minutes of a contest news
  video, `vad_filter` off (the library default) gave 8 segments, every one the same fluent line,
  "Hãy subscribe cho kênh ..." ("please subscribe to the channel ..."), where the real speech
  starts at 4.55 s. With `vad_filter: true` (Silero VAD, as in the faster-whisper README: only
  silences over 2 s are skipped) the same minutes gave 55 segments of the actual broadcast.
- **VAD is not a guarantee.** On a 30-second piece cut from the start of a commentary video, `float16`
  and `float32` wrote that one subscribe line and nothing else, even with `vad_filter: true`;
  `int8` and `int8_float16` wrote the 7 segments of speech, and the whole video with `float16`
  was right too. Whether Whisper falls into it depends on small numerical differences and on where
  the audio is cut. A video that is only music still gets a line, `NANI` with `language: vi`
  and `NANİ?` with `language: null`.
- **The invented lines look perfect.** They are fluent and read with high confidence, so no
  confidence threshold catches them. Read a sample of transcripts before you index a whole
  collection. Lines that are still invented go into `drop_phrases` (`["subscribe cho kênh"]` left
  the 30-second piece with no segment, which is what it should have had).
- **One bad window can spill into the next.** `condition_on_previous_text: true` (the default)
  feeds each window's text to the next one. faster-whisper's documentation says turning it off
  "the model becomes less prone to getting stuck in a failure loop", at some cost to consistency
  between windows. With `vad_filter` off and it set to `false`, the 4 minutes above gave 40 segments, all
  different, instead of 8 copies; the first window was still invented, the rest was speech.
- **Words are misheard, and marks come and go.** In the test, "vòng đua" was written "vòng đùa", "mái
  ấm" "mái âm", and a team name written two ways in two precisions. Speech works best as supporting evidence,
  not as the only lane of a query.
- **`language: null` works on speech**, and the test video gave 11 segments again, but it guesses
  from the first 30 seconds, which may be music; the videos are Vietnamese, so `vi` is fixed.

## Troubleshooting

The messages are as printed in tests that caused each one.

| Symptom | Cause and fix |
|---|---|
| the same sentence repeated across many segments | Whisper stuck on an invented line: keep `vad_filter: true`, set `condition_on_previous_text: false`, and put the line in `drop_phrases` |
| `[n/m] <video>: FAILED TypeError: WhisperModel.transcribe() got an unexpected keyword argument 'beam_sizes'` | a key under `asr:` that is not a faster-whisper option; every video fails the same way. Check its spelling |
| `error: asr needs --videos, the folder with the video files` | give the folder with the `.mp4` files |
| `no video file under <folder> for: <ids>` | the folder has no `<id>.mp4` for those ids |
| `Cannot find an appropriate cached snapshot folder for the specified revision on the local disk and outgoing traffic has been disabled ...` | the model is not in the cache and there is no network (`HF_HUB_OFFLINE=1`). Download it once, or set `asr.model` to a local folder |
| `ValueError: Requested float16 compute type, but the target device or backend do not support ...` | `compute_type: float16` on a CPU; use `int8` or leave it `null` |
| `0 segments` for a video | no audio track, or no speech. Not an error |
| out of GPU memory | `compute_type: int8_float16` took 1.5 GiB less than the default (table above) |
