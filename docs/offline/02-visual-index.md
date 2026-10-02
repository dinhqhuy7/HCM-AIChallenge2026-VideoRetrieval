# 2. Visual index

**Goal.** Put one vector per indexed keyframe into Milvus, for every encoder you want to
search.

## Run

```bash
python scripts/build_index.py visual                  # every encoder in visual.encoders
python scripts/build_index.py visual --device cuda:1  # on another GPU
python scripts/build_index.py visual --video L21_V001 --force   # redo one video
```

`visual.encoders` in `configs/index.yaml` lists the encoders: `[siglip2]` by default,
`[siglip2, pe_core]` to build both. Each gets its own Milvus collection, named after it, and the
search picks one with `visual.encoder` in `configs/search.yaml`. Build both from the same
keyframes if you want to compare them.

| Encoder | Model (`configs/index.yaml`) | Vector | Text it reads | Library |
|---|---|---|---|---|
| `siglip2` | `google/siglip2-so400m-patch14-384` | 1152 | 64 tokens, lower-cased | transformers |
| `pe_core` | `hf-hub:timm/PE-Core-bigG-14-448` | 1280 | 72 tokens | OpenCLIP |

Another OpenCLIP model can be named in `visual.pe_core.model`, for example
`hf-hub:timm/PE-Core-L-14-336` (1024 numbers, 32 tokens of text). It goes into the same
`pe_core` collection name, so when you change the model use a fresh index file (`milvus.uri`) or
drop the old collection. A model with another vector size is refused (last row of the table
below).

## What happens

1. The encoder is loaded once, in fp16 on a GPU (fp32 on CPU).
   - SigLIP 2 through transformers, as in its model card.
   - PE-Core through OpenCLIP, halved *before* it is moved to the GPU (see Lessons).
2. For every video whose rows are missing or out of date (point 5), the pictures of its indexed
   keyframes are embedded in batches of `visual.batch_size`.
3. Vectors are L2-normalised, and the collection uses the metric `COSINE`: a search returns the
   cosine similarity, higher is better. The scores of a search were equal to the dot products of
   the stored vectors, to four decimals, for both encoders.
4. A video's old rows are deleted, then its new rows go in, with `keyframe_id`, `video_id`,
   `shot_id`, `frame_index` and `time_ms`, and the video is flushed to disk.
5. A rerun compares the keyframes the collection holds for each video with the video's indexed
   keyframes, and redoes the video when they differ: after `preprocess.py --force` or
   `--reselect`, or when an earlier run stopped halfway (a test left a video with 8 of its 24
   rows; the next run redid it). `--force` redoes videos anyway.
6. The collection is created with `index_type: AUTOINDEX`: Milvus chooses the index and its
   parameters. No index parameter is set in this repository.

A failed video, an out-of-memory error for example, is reported, the others go on, and the exit
status is 1. Its rows were deleted first, so the next run does it again.

## Choosing `visual.batch_size`

The number of pictures per forward pass has no published default; the config says 16. It changes
memory, hardly speed, and the last digits of the vectors: in fp16, the same keyframes embedded in
batches of 1 and of 16 gave cosines of at least 0.999996 between the two vectors of each picture
(32 keyframes, SigLIP 2), and that was enough to change the order of the results in two of four
text queries. Keep one batch size for a whole index if you compare runs.

Measured on one RTX 2080 Ti (11 GiB, shared with other jobs), on 128 pictures of 1280×720 read
from JPEG files; the speed includes reading and preparing the pictures on the CPU and the memory
includes the weights:

| Encoder | weights | load | pictures per second at batch 1, 16 | peak memory at batch 1, 16, 64 |
|---|---|---|---|---|
| SigLIP 2 | 2.15 GiB | 10 s | 25.8, 29.4 | 2.17, 2.48, 3.45 GiB |
| PE-Core L-14-336 | 1.26 GiB | 23 s | 33.9, 50.9 | 1.27, 1.46, 2.08 GiB |
| PE-Core bigG-14-448 | 4.52 GiB | 55 s | 8.5, did not fit | 4.56 GiB; batch 8: 4.87 GiB; batch 16 did not fit |

The speed stops rising at a small batch, so a smaller batch costs little. Of the 5.7 GiB left on
the card, bigG used 4.87 at batch 8 and did not fit batch 16. At 29 pictures a second, SigLIP 2 would take about an hour
for the 97,811 keyframes of the `middle` policy on the 873 videos (arithmetic, not a run).
Vectors take 4 bytes a number: 4,608 bytes for SigLIP 2, 5,120 for bigG, before Milvus's own
overhead.

## Output

`data/index/milvus.db` with Milvus Lite, or the collections on your standalone server. Both are
set by `milvus.uri` ([setup.md](../setup.md#milvus)).

## Check

```bash
python - <<'EOF'
from pymilvus import MilvusClient
client = MilvusClient("data/index/milvus.db")
for name in client.list_collections():
    client.load_collection(name)
    print(name, client.query(name, filter="", output_fields=["count(*)"])[0]["count(*)"])
EOF
python scripts/search.py kis --text "something you know is in one of your videos"
```

The first command counts the vectors in each collection. It should equal the number of
`indexed: true` lines in the keyframe maps (50 and 46 on the test videos, before and after a
`--reselect`). The second should put frames of that scene near the top. Do not run the two at the
same time on a Milvus Lite file ([setup.md](../setup.md#milvus-lite-the-default)).

## Lessons

- **Pick the encoder by measuring, on your own queries.** The two encoders disagree on what they
  are good at. SigLIP 2 is multilingual; the PE-Core model tested reads English much better than
  Vietnamese and does better with the query translated (`translation.enabled` in
  `configs/search.yaml`; numbers in [models.md](../models.md#does-the-language-of-the-query-matter)).
- **Watch the text length.** A longer description is cut at the model's limit, and the cut part is
  often the detail that mattered. Translation shortens it; so does typing only what the picture
  shows.
- **Halve before moving.** Loading PE-Core L in fp32 onto the card and halving it there peaked at
  2.51 GiB; halving first, 1.25 GiB. The bigG weights are about 9.7 GB in fp32, more than most cards
  hold, and 4.52 GiB after halving.
- **One model at a time.** Each step loads one model and frees it before the next.

## Troubleshooting

The messages are as printed in tests that caused each one. The first five come before any video
is processed, so they show as a Python traceback; the message is its last line.

| Symptom | Cause and fix |
|---|---|
| `invalid index type: HNSW, local mode only support FLAT IVF_FLAT AUTOINDEX` | Milvus Lite; keep `AUTOINDEX`, or use Milvus standalone. The half-made collection is dropped |
| `Open .../milvus.db failed, the file has been opened by another program`, then `Open local milvus failed` | another program (`search.py`, a notebook) has the Milvus Lite file open. Close it first; do not just retry ([setup.md](../setup.md#milvus-lite-the-default)) |
| `RuntimeError: Model config for PE-Core-bigG-14-448 not found.` | the name needs the `hf-hub:` prefix |
| `FileNotFoundError: Failed to download file (open_clip_pytorch_model.bin) for timm/PE-Core-...` | OpenCLIP cannot find the model in the Hugging Face cache and cannot download it (no network, or a wrong name). Download it first ([setup.md](../setup.md#models)) |
| `ModuleNotFoundError: No module named 'open_clip'` | PE-Core needs `open_clip_torch`, `timm` and `ftfy` ([requirements.txt](../../requirements.txt)) |
| `torch.OutOfMemoryError: CUDA out of memory. Tried to allocate ...` | the weights do not fit (then it stops at once) or a batch does not: `[n/m] <video>: FAILED OutOfMemoryError: ...`, and the other videos fail the same way. Lower `visual.batch_size`, free the card, or use a larger one |
| `error: collection 'pe_core' holds vectors of 1280 numbers, but this model gives 1024: the model changed. ...` | you changed the model of an encoder whose collection exists. Use another `milvus.uri`, or drop the collection and build it again. Milvus Lite does not check each vector: 5 vectors of 1024 numbers went into a collection of 1280 without an error before this check |
| `Using a slow image processor as use_fast is unset ...` | an information message from transformers; the processor saved with the model is used |
| `[SERVER][BlockLock][milvus] Process exit` at the end of a run; `failed to get mvccTs from milvus server, use client-side ts instead` while it checks which videos are done | messages of Milvus Lite and pymilvus; the runs they appeared in were correct |
| `error: Milvus has no collection 'pe_core': run build_index.py visual first` (from `search.py`) | `visual.encoder` in `configs/search.yaml` names a collection that was not built; add it to `visual.encoders` in `configs/index.yaml` and run this step |
