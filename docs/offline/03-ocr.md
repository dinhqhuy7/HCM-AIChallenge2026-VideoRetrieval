# 3. Text on screen (OCR)

**Goal.** Read the text shown on every indexed keyframe, and make it searchable per shot.
Captions, tickers, signs, plates and dates are exact strings; an image embedding cannot promise
to match them, so they get a lane of their own.

## Run

In the OCR environment ([setup.md](../setup.md#ocr)):

```bash
python scripts/build_index.py ocr                   # --device gpu:1 (or cuda:1) for another card
python scripts/build_index.py keywords              # any environment; see "Keyword index"
```

`--video ID` (repeatable) limits the step to some videos, `--force` redoes videos that are
current, `--device cpu` runs without a GPU. A video that fails is reported, the others go on, and
the exit status is 1.

The models are downloaded into PaddleX's cache the first time they are used, from `~/.paddlex`
by default or from `PADDLE_PDX_CACHE_HOME`. Three are needed: `PP-OCRv6_medium_det` (62 MB),
`PP-OCRv6_medium_rec` (77 MB) and, because `use_textline_orientation` is left on (below),
`PP-LCNet_x1_0_textline_ori` (7 MB). On a machine without network, copy their folders into
`<cache>/official_models/`.

## What happens

1. PaddleOCR 3's general OCR pipeline is created with `PP-OCRv6_medium_det` and
   `PP-OCRv6_medium_rec`. Document orientation and unwarping, which are for photographed pages,
   are off, as in the example on the `PP-OCRv6_medium_rec` model card. Text-line orientation is
   left to PaddleX, which turns it on ([below](#text-line-orientation)).
2. Every other pipeline option in `configs/index.yaml` is `null`, which means it is not passed,
   so PaddleX uses its own value. In PaddleX 3.7.2 (printed from a real run): pictures are
   brought up to a short side of at least 64, detection threshold 0.3, box threshold 0.6, unclip
   ratio 1.5, no filter on the recognition score (0.0). The unclip ratio of 2.0 that appears
   in some PaddleOCR documentation is only a fallback in the code.
3. For each indexed keyframe, every line is written with its text, recognition score and box. The
   box is given as fractions of that picture's own size, because not every video has the same
   shape (some are portrait). Pictures go through one at a time: PaddleOCR's `predict` keeps every
   result, each holding its picture, and 300 keyframes cost 795 MB more that way.
4. A video is read again when its indexed keyframes are no longer the ones its OCR file covers
   ([README](README.md#offline-from-videos-to-indexes)): after `preprocess.py --reselect`, a test
   with 50 keyframes cut to 46 redid exactly the two videos that had changed.

On an RTX 2080 Ti, 57 keyframes of 1280×720 took 7 s, about 8 a second. On the CPU of a machine
with 40 cores, 59 s. Loading the models took 5 to 7 s in earlier runs. At 8 a second, the 97,811
keyframes of the `middle` policy on the 873 videos would take about 3.4 hours (arithmetic, not a
run).

### Text-line orientation

PaddleX runs a small classifier that decides whether each line is upside down, and turns it. It
is on unless you set `use_textline_orientation: false`, and the model card example also has it on.
On 99 dense keyframes of two videos (one portrait, one landscape), 18 keyframes were read
differently with it on and off. In the three I opened it was wrong with the classifier on: a pole
number 10 on a portrait frame came out `DI`, a 6 came out `9`, and the second line of a caption,
"Mái ấm của những chú mèo hoang", came out as upside-down garbage (`pOUOneg`) where with it off it
was read. It is a small sample, and signs held upside down do exist, so the default stays the
library's; set it to `false` and compare on your own keyframes.

## Keyword index

`build_index.py keywords` turns the lines into **one document per shot**:

- The same line read on many keyframes of a shot counts **once**, in its best-scoring reading. A
  caption held for two seconds is read on every keyframe. Counted each time, it would make one
  shot vote many times for one headline. On the 57 dense keyframes of one video, 196 readings
  became 105 lines.
- **Different** lines all stay: a logo, a clock, a headline and a subtitle are four pieces of
  evidence.
- Words are compared **without Vietnamese marks** and in lower case, on both the document and the
  query side: `Bến Thành` becomes `ben thanh`, `Đà Nẵng` becomes `da nang`. Digits stay, and
  punctuation splits words: `79H-6072` becomes `79h` and `6072`, `tv.tuoitre.vn` becomes `tv`,
  `tuoitre` and `vn`.
- BM25 ranks the shots, with `k1 = 1.2` and `b = 0.75`, the Lucene and Elasticsearch defaults.
- A hit points at the keyframe where the query's words were read, not just at the shot.

`keywords` rebuilds the index of every lane that has evidence, so run it again whenever OCR,
speech or objects change. If the OCR evidence is for other keyframes than the indexed ones, it says
so: `ocr: WARNING 2 videos have evidence for other keyframes than the indexed ones (L24_V040
L30_V040); run build_index.py ocr first`.

## Output

`ocr/<video>.jsonl`, one line per indexed keyframe. This is the keyframe of a title card
(`L30_V040_000122`, five of its lines):

```json
{"keyframe_id": "L30_V040_000122", "lines": [{"text": "Herbalife", "score": 1.0, "box": [0.4437, 0.2694, 0.5523, 0.3222]}, {"text": "thương hiu", "score": 0.99, "box": [0.4453, 0.4125, 0.6352, 0.4806]}, {"text": "quán ly", "score": 0.8878, "box": [0.443, 0.4708, 0.5625, 0.5472]}, {"text": "#", "score": 0.9773, "box": [0.332, 0.4917, 0.393, 0.6333]}, {"text": "cân nng", "score": 0.9948, "box": [0.4437, 0.5319, 0.593, 0.6014]}]}
```

and `index/keywords-ocr.json`. The card says "thương hiệu quản lý cân nặng": the recogniser wrote
`hiu`, `ly` and `nng` (see Lessons).

## Check

```bash
python scripts/search.py kis --ocr "a word you can see on a frame"
```

Open the frames it returns: the words should be visible on them. On the three test videos,
`--ocr herbalife` returned that title card first, and `--ocr tv.tuoitre.vn` the keyframe with
that address first.

## Lessons

- **Check what the recogniser can write before you trust it.** The dictionary of
  `PP-OCRv6_medium_rec` has 18,708 entries, 83% of them single Chinese characters, and holds 23 of
  the 67 accented Vietnamese lower-case letters (counting `đ`, `ă`, `â`, `ê`, `ô`, `ơ`, `ư`, which are
  all there). Of the five marks, none of the 12 letters with a hỏi or a nặng is in it, 4 of 12 with
  a ngã, 6 of 12 with a sắc, 6 of 12 with a huyền, and of the letters that carry a second mark only
  `ồ`. The missing letters are **dropped**: another title card (`L30_V040_000229`) reads "Clip bn
  đc d thi cuc thi:" for "Clip bạn đọc dự thi cuộc thi:". The dictionary is under `character_dict` in
  the model's `inference.yml`; count the letters of your language in it.
- **The marks it does have come and go.** On 57 keyframes of one video the same line was read
  `quan ly` on some and `quán ly` on others, and a caption as `lưng` and as `lung`; the scores were
  close (0.876 to 0.919, and 0.968 to 0.981). The model's confidence does not show it.
- **Hence: match without marks, on both sides.** A query typed with marks would otherwise miss text
  that lost them. This does not bring back a dropped letter: `thương hiệu` still found the card
  above, but through `thuong` and the other words, not through `hieu`. A word that was written
  without one of its letters never matches itself, and neither does a query that is exactly that
  word.
- **Do not strip digits or symbols.** A "clean the text" step removes exactly the characters that
  identify one frame: plates, prices, dates, product codes.
- **A score does not separate right from wrong.** The numbers above are why. Setting
  `text_rec_score_thresh` drops lines, and a dropped line may be the only evidence for a frame; the
  default keeps all.
- **Length normalisation works against text-heavy shots.** A shot document is every distinct line
  the shot read, so a bulletin full of tickers is much longer than a quiet shot, and BM25's `b`
  lowers the score of long documents. If text-rich shots rank too low on your queries, that is the
  parameter to look at.

## Troubleshooting

The messages are as printed in tests that caused each one.

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'paddleocr'` | the step ran in the main environment; run it in the OCR environment |
| `ImportError: libcuda.so.1: cannot open shared object file` | `paddlepaddle-gpu` needs the NVIDIA driver even to run on the CPU; on a machine without one install the CPU build ([setup.md](../setup.md#ocr)) |
| `Encounter exception when download model from bos. No model source is available! Please check network or use local model files!` (after errors for `git.aistudio.baidu.com`, `modelscope.cn` and `paddle-model-ecology.bj.bcebos.com`) | no network and the model is not in the cache. The line `Creating model: ('PP-LCNet_x1_0_textline_ori', None, None)` just above names it: copy its folder into `<cache>/official_models/`, or turn the step off with `use_textline_orientation: false`. `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` only skips a connection test; it does not stop these downloads |
| `error: No engine bindings registered for model 'PP-OCRv6_nope_rec'.` | a model name in the `ocr` section of `configs/index.yaml` is misspelt |
| `no ocr index at .../keywords-ocr.json: run build_index.py ocr and then keywords` (from `search.py`) | run `keywords` after `ocr` |
| `ocr: WARNING N videos have evidence for other keyframes than the indexed ones (...); run build_index.py ocr first` (from `keywords`) | the keyframes changed since OCR ran; run `build_index.py ocr`, then `keywords` again |
