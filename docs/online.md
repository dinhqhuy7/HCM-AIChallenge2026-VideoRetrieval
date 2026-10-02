# Online search

One query, typed into up to four boxes, becomes at most 100 answer rows.

```bash
python scripts/search.py kis --text "hai người phụ nữ dán thùng carton"
python scripts/search.py kis --text "a night market" --ocr "bến thành" --out runs/kis-7.csv   # two boxes: needs fusion.rrf_k
python scripts/search.py qa --text "a cat in a room" --answer "cat" --out runs/qa-3.csv
python scripts/search.py trake --event "..." --event "..." --event "..." --out runs/trake-1.csv
python scripts/search.py --query-file query-p1-1-kis.txt --out-dir submission
```

TRAKE has its own page ([trake.md](trake.md)); sending an answer to DRES is in
[submission.md](submission.md). Each command loads the models it needs and exits: with SigLIP 2
a search took 15 s from start to finish (18 s with translation), and a search in the OCR box alone
1 s. Inside a running process a visual search took 18 ms and an OCR search 0.1 ms on an index of 50
shots; on one full video of 41 shots, 30 ms and 6 ms.

## The four boxes

| Box | Lane | Searches | Type into it |
|---|---|---|---|
| `--text` | visual | keyframe vectors in Milvus | what the picture shows |
| `--ocr` | ocr | text read on screen, BM25 | words written on screen: a caption, a sign, a number |
| `--asr` | asr | speech, BM25 | words someone says |
| `--objects` | objects | detected labels, BM25 | object names from `objects.classes` |

A query is split by the person reading it; nothing is split automatically. The split is the most
useful thing a person adds. Leave a box empty when the query says nothing for it: a lane that is
not needed only adds noise to the fusion.

Words written on screen belong in `--ocr`. The visual box is not blind to lettering, but it is much
weaker at it. On the three test videos, 22 distinct strings read from the screen (clocks, distance
counters, a logo name) were typed once into each box, and the keyframe that shows the string came
first in the OCR box for 18 of them and within the first five for 20; in the visual box, first for 4
and within five for 11, among 50 shots. A large word on a plain card (`Herbalife`) was found by
the visual box; numbers and clocks mostly were not. The `--objects` box needs the optional object
lane ([offline/README.md](offline/README.md#objects-optional)) and was not part of these tests.

`--query-file` reads a query file in the organisers' naming. The task comes from the file name
(`query-p1-1-kis.txt` is KIS, a name ending in `-qa` or `-trake` the other two), the whole text goes
into `--text`, and for TRAKE the lines starting with `E1`, `E2` ... (or `Cảnh 1`, `Cảnh 2` ...)
become the events. With `--out-dir` the rows go to `<file name>.csv` in that folder.

## Translation

With `translation.enabled: true` in `configs/search.yaml`, the `--text` box is translated from
Vietnamese to English with envit5 (`VietAI/envit5-translation`) before it is embedded. The English
text is printed, so you can see what was actually searched:

```text
visual text in English: man on a motorcycle on the street
```

for "người đàn ông đi xe máy trên đường phố". Only the visual box is translated: OCR and speech are
matched in Vietnamese. It costs about 0.2 to 0.5 s a query. The model reads the input with its
`vi: ` prefix, which the code adds (without it the same query came back as nonsense), and the
English is cut at `translation.max_length` tokens: a query of 4,539 characters came back as 2,415,
ending mid-sentence. Turn it on for PE-Core, whose model card names no language and which read
Vietnamese poorly in a test ([models.md](models.md#does-the-language-of-the-query-matter)). SigLIP 2
is multilingual: compare both ways on your own queries. On the test index the translation above changed
the second result.

## Why shots

Every lane returns **shots**, each represented by its best frame:

- the visual lane collapses its frame hits by shot, widening the search until it has `depth`
  distinct shots (at most 16,384 frames, Milvus's limit on one search); on 200,000 frames of 10 per
  shot, 100 shots took 4 searches and 38 ms. Milvus can group by a field in the search itself and
  that was six times faster, but on 50,000 frames it lost accuracy (recall of the top 10 against the
  exact answer 0.9, against 1.0 here), so it is not used;
- the keyword lanes index one document per shot.

Fusion then counts one vote per shot and lane. Ranked as frames, fifty keyframes of one headline
would outvote fifty different shots, and the list would repeat one moment instead of offering new
ones.

## Fusion

Two or more boxes are combined by **Reciprocal Rank Fusion** (Cormack, Clarke and Büttcher, SIGIR
2009):

    score(shot) = Σ over lanes  1 / (k + rank of the shot in that lane)

Only ranks are used, so a cosine similarity and a BM25 score never have to be put on one scale. The
shot that comes first in both lanes comes first: on the test index `--text "a title card with a
logo" --ocr herbalife` put the card first, where the visual box alone had put it fifth. A shot a lane
does not return adds nothing from that lane. Each fused shot keeps the frame from the lane that
ranked it highest.

`fusion.rrf_k` has no default here. The paper fixed k = 60 in a pilot run and found the choice "not
critical" (its table: MAP 0.2072 at k = 0, 0.2145 at 60, 0.2098 at 500). Set it before you fill two
boxes; with one box there is nothing to fuse. Without it:

```text
error: configs/search.yaml: set `fusion.rrf_k` to combine lanes (the RRF paper uses 60)
```

and the command stops before any model is loaded.

## Result shaping

The organisers' information document for the round scores a query as the mean of R@1, R@5, R@20,
R@50 and R@100, R@k being the best score among the first k rows. So the order of the rows is the
score, and:

1. **One row per shot.** A second frame of the same shot answers the same moment again.
2. **Spare frames only after the shots run out.** A second frame of a shot is worth less than a new
   shot, but more than an empty row: it can still fall inside the answer range when the shot
   straddles its edge. On the dense test index (99 keyframes in 26 shots) the first 26 rows were 26
   different shots and the other 73 their remaining frames.
3. **Spread over videos (optional).** When a video is wrong, every row in it is lost. With
   `spread.enabled`, the first `keep_top` rows stay as ranked, then the rest are taken `per_video`
   rows from each video in turn. There is no published value for either number, so the setting is
   off. With 3 and 1 on the test index, the first 12 rows came from 6, 3 and 3 rows of the three
   videos instead of 8, 3 and 1; only the order changes, no row is added or dropped.
4. **Cut at `rows`** (100, the organisers' maximum).

A box that matches few shots gives few rows: `--ocr herbalife` gave 1 row, `--asr mèo` 10, a word
that is nowhere gave an empty file (`wrote 0 rows`). Add a `--text` box to fill the list: a
fused list holds every shot any of its lanes returned.

## Output

The first ten rows are printed, with the time of each frame. With `--out` (or `--out-dir` with a
query file) all rows are written as a CSV without a header ([submission.md](submission.md)):

```text
L24_V040,1130
L30_V040,37
```

for KIS, `video,frame,answer` for Q&A (`L30_V040,446,mèo`), and `video,frame1,frame2,...` for TRAKE.
A Q&A query needs `--answer`: the answer goes on every row, and without it the rows are shown and
no file is written.

## Settings (`configs/search.yaml`)

| Key | Meaning | Default |
|---|---|---|
| `device` | where the text encoder and the translator run | `cuda` |
| `visual.encoder` | which collection to search | `siglip2` |
| `translation.enabled`, `.model`, `.max_length` | translate the visual box | off, envit5, 512 (the model card's example) |
| `depth` | shots each lane returns (TRAKE: frames per event) | 100, as many as a query may send |
| `fusion.rrf_k` | RRF constant | none: set it to fuse (the paper: 60) |
| `rows` | rows per query | 100 (organisers) |
| `spread.*` | spread the tail over videos | off |
| `trake.*` | order, gaps and spread of TRAKE chains | [trake.md](trake.md) |
| `submission.*` | frame numbering and the DRES address | [submission.md](submission.md) |

## Tips

- Describe what is **visible** in `--text`: people, clothes, colours, places, actions. A story told
  in the query ("after the meeting, the minister ...") is not in any picture.
- Watch the length. SigLIP 2 reads 64 tokens and PE-Core bigG 72; the rest is cut. Put the
  distinctive detail first.
- Numbers, names and signs go into `--ocr`, typed with or without marks. The recogniser drops some
  Vietnamese letters, so a word can be missing one ([offline/03-ocr.md](offline/03-ocr.md#lessons)).
- Check the top rows by eye before you trust a list. The frames are in `data/frames/`.

## Troubleshooting

The messages are as printed in tests that caused each one.

| Symptom | Cause and fix |
|---|---|
| ``error: <config>: set `fusion.rrf_k` to combine lanes (the RRF paper uses 60)`` | two or more boxes need `fusion.rrf_k` |
| `no ocr index at .../keywords-ocr.json: run build_index.py ocr and then keywords` | build that lane first |
| `error: Milvus has no collection 'pe_core': run build_index.py visual first` | `visual.encoder` names a collection that was not built; add it to `visual.encoders` and run `build_index.py visual` |
| fewer than 100 rows | a keyword box returns only the shots that contain the words, and a query returns at most as many rows as the index has keyframes; add a `--text` box |
| `Q&A: add --answer to write the file (the answer goes on every row)` | a Q&A file needs the answer |
| `search.py: error: type something into at least one box: --text, --ocr, --asr or --objects` | all boxes empty |
| `search.py: error: give the task (kis, qa, trake) or a query file whose name ends in -kis/-qa/-trake` | no task |
| `search.py: error: TRAKE searches its events with the visual lane only: give them with --event, ...` | `--text` and the other boxes do not apply to TRAKE |
| `search.py: error: --out-dir goes with --query-file; use --out for a single query` | `--out-dir` without a query file |
