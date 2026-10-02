# Setup

## What you need

- **Linux** with Python 3.11. macOS runs Milvus Lite but has no CUDA. On Windows, use WSL2:
  Milvus Lite has no Windows build.
- **FFmpeg**, the command-line tool: TransNetV2 decodes video through it
  (`sudo apt install ffmpeg`; `ffprobe` comes with it).
- **An NVIDIA GPU** for embeddings, OCR and speech. Every step loads one model at a time. The
  end-to-end runs of this repository used cards with 5 to 6 GB free. Measured peaks, in fp16:
  SigLIP 2 2.5 GiB at `visual.batch_size: 16`, the translator 1.05 GB, YOLOE 0.25 GB, PE-Core
  bigG 4.5 GiB while loading. The faster-whisper README gives 4525 MB for large-v2 in fp16 (13
  minutes of audio, beam 5). PE-Core bigG needs a bigger card than SigLIP 2.
- **Disk** for the models, about 9 GB without PE-Core bigG and about 18 GB with it
  ([models.md](models.md)), and for the keyframe pictures, which grow with the keyframe density
  you choose.

## Three environments

| Environment | Install | Runs |
|---|---|---|
| main | `requirements.txt` | `preprocess.py`, `build_index.py visual / asr / keywords`, `search.py` |
| ocr | `requirements-ocr.txt` | `build_index.py ocr` (and `keywords`) |
| objects (optional) | `requirements-objects.txt` | `build_index.py objects` |

Why three: Paddle and PyTorch each ship their own CUDA libraries, and in one environment they
clash. Ultralytics is AGPL-3.0; in its own environment it stays out of everything else. The steps
share nothing but the files under `data/`, so each runs in whichever environment it needs.

### Main

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
```

Install PyTorch first, for your CUDA version (<https://pytorch.org/get-started/locally/>).
`open_clip_torch` depends on torch: if torch is not there yet, pip installs the newest build,
which may not match your driver.

Python 3.11 puts its own old setuptools (65.5.0) in a new venv; `requirements.txt` asks for
`setuptools>69,<82`, which pymilvus 2.5.4 needs (it imports `pkg_resources`, removed in
setuptools 82.0.0), and pip upgrades it.

### OCR

```bash
python3.11 -m venv .venv-ocr && . .venv-ocr/bin/activate
python -m pip install paddlepaddle-gpu==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
pip install -r requirements-ocr.txt
python -c "import paddle; print(paddle.__version__)"      # 3.2.0
```

Use `.../stable/cu118/` for CUDA 11.8, or `paddlepaddle==3.2.0` from `.../stable/cpu/` for the
CPU. The GPU build needs an NVIDIA driver (`libcuda.so.1`) **even to run on the CPU**, so a
machine without one takes the CPU build. From the PaddlePaddle install guide, the GPU builds need
a driver of at least 550.54.14 for CUDA 12.6, or at least 450.80.02 for CUDA 11.8.

### Objects (optional)

```bash
python3.11 -m venv .venv-objects && . .venv-objects/bin/activate
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements-objects.txt
```

`clip-anytorch` is in the file on purpose: YOLOE's text encoder imports `clip`, and without that
wheel Ultralytics installs `git+https://github.com/ultralytics/CLIP.git` the first time
`set_classes()` runs. Run `build_index.py objects` from the folder that holds `yoloe-26l-seg.pt` and
`mobileclip2_b.ts` (or let Ultralytics download them, about 254 MB for the second), and set
`YOLO_OFFLINE=True` to forbid any download. Ultralytics keeps a settings file: if its default
folder is not writable it warns and falls back to a temporary folder; point `YOLO_CONFIG_DIR` at a
writable folder to silence that.

### What was tested

On 2026-10-02, `requirements.txt` and `requirements-objects.txt` were each installed into a fresh
virtual environment from PyPI, on a machine that already had PyTorch 2.6.0 (CUDA 12.4) installed:

- main: pip added only `open_clip_torch` 2.32.0, `timm` 1.0.29, `ftfy` 6.2.3 and `setuptools`
  81.0.0; `pip check` was clean; the test suite passed (`python -m unittest discover -s tests`, no
  GPU needed) and so did the real PE-Core test;
- objects: pip resolved Ultralytics' unpinned dependencies to newer versions than the ones the
  development ran with (matplotlib 3.11.2, polars 1.44.2, ...); the real YOLOE tests passed with
  no network.

`requirements-ocr.txt` was installed from a local copy of the wheels, not from the PaddlePaddle
index, and the PyTorch line was not re-run. Versions are the ones these files were run with: a
newer release of a package that is not pinned may behave differently.

## Models

Every model downloads by itself on first use. On a machine without network, download them ahead
into the Hugging Face cache, then work offline:

```bash
hf download google/siglip2-so400m-patch14-384
hf download timm/PE-Core-bigG-14-448
hf download VietAI/envit5-translation
hf download Systran/faster-whisper-large-v3
export HF_HUB_OFFLINE=1
```

`HF_HUB_CACHE` (and the older `HUGGINGFACE_HUB_CACHE`) names the cache folder and wins over
`HF_HOME`; if your environment sets one of them, `HF_HOME` is ignored. A cache laid out by hand
needs the commit hash as the snapshot folder name (`snapshots/<40 hex characters>/`) and the same
hash in `refs/main`.

The PaddleOCR models download into PaddleX's cache (`PADDLE_PDX_CACHE_HOME`, default `~/.paddlex`)
the first time the OCR step runs: the detection and recognition models, and the text-line
orientation model (`PP-LCNet_x1_0_textline_ori`, which the default pipeline uses). PaddleX checks
online where each model comes from unless `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True`. The full
list of models, with sizes and licences, is in [models.md](models.md).

## Milvus

### Milvus Lite (the default)

Nothing to install: `pymilvus` 2.5 brings Milvus Lite (`milvus-lite` 2.4.12 here) on Linux and
macOS, and `configs/index.yaml` points at a file, `data/index/milvus.db`. It suits a test on a few
videos. What is known about its limits, from the Milvus documentation and from the tests:

- index types FLAT, IVF_FLAT and AUTOINDEX only; creating an HNSW index fails with
  `invalid index type: HNSW, local mode only support FLAT IVF_FLAT AUTOINDEX`;
- **one process at a time** per file: while `search.py` has `milvus.db` open, `build_index.py
  visual` cannot open it, and the other way round. The refused process prints
  `Open ... failed, the file has been opened by another program`. Do not retry while the first
  is still running: in `milvus-lite` 2.4.12 a refused open deletes the lock file
  (`.milvus.db.lock`), after which a second process gets in;
- a plain query is cut at 16,383 rows without an error (the code reads a video with an iterator
  for that reason), and a search asks for at most 16,384;
- Linux and macOS only, and "only suitable for small scale vector search use cases".

### Milvus standalone (for the full collection)

Use the official Docker Compose file of the version tested here (2.5.4):

```bash
mkdir milvus && cd milvus
wget https://github.com/milvus-io/milvus/releases/download/v2.5.4/milvus-standalone-docker-compose.yml -O docker-compose.yml
docker compose up -d        # starts milvus-standalone, milvus-etcd, milvus-minio (sudo if your Docker needs it)
docker compose ps           # all three should be Up (healthy)
```

Then set `milvus.uri: http://localhost:19530` in `configs/index.yaml`. Keep
`index_type: AUTOINDEX` to let Milvus choose, or set `HNSW`, which standalone accepts. With
standalone, several processes can read the collection at once.

The file starts `quay.io/coreos/etcd:v3.5.16`, `minio/minio:RELEASE.2023-03-20T20-16-18Z` and
`milvusdb/milvus:v2.5.4`. The tests of this repository ran against the same etcd and Milvus images
and a newer MinIO (`RELEASE.2024-12-18T13-15-44Z`), in a private Docker network with no port
published; `AUTOINDEX` and `HNSW` both passed. It publishes ports 19530 (Milvus), 9091 (health
and WebUI), 9000 and 9001 (MinIO), and the MinIO access and secret keys are both `minioadmin`:
do not expose these ports to a network you do not trust.

| Action | Command |
|---|---|
| stop, keep the data | `docker compose down` |
| start again | `docker compose up -d` |
| delete all data (irreversible) | `docker compose down && rm -rf volumes` |

Check that it answers:

```bash
curl -f http://localhost:9091/healthz          # OK
python -c "from pymilvus import MilvusClient; print(MilvusClient('http://localhost:19530').list_collections())"
```

## Check the install

```bash
python -m unittest discover -s tests         # no GPU, no model, a few seconds
```

Some tests run a real model when you point an environment variable at it (`SIGLIP2_MODEL`,
`PE_CORE_MODEL`, `WHISPER_MODEL`, `TRANSLATION_MODEL`, `OCR_MODELS`, `YOLOE_WEIGHTS`); each is
named in the header of its test file, and `TEST_DEVICE` (for example `cuda:0`; the tests default to
the CPU) says where it runs. Run the OCR and objects tests in their own environments.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'pkg_resources'` when importing pymilvus | pymilvus 2.5.4 imports `pkg_resources`, which setuptools 82 removed: `pip install "setuptools>69,<82"` |
| `pymilvus 2.5.4 has requirement setuptools>69, but you have setuptools 65.5.0` | a new venv carries its own old setuptools: `pip install "setuptools>69,<82"` |
| `docker compose` is not a command | Compose V2 is needed; the old `docker-compose` (V1) is not what the Milvus documentation uses |
| Milvus containers exit or ports are taken | another service uses 19530, 9091, 9000 or 9001; stop it, or change the host side of the ports in `docker-compose.yml` |
| `invalid index type: HNSW` | Milvus Lite; use `AUTOINDEX` (the default here) or move to standalone |
| `Open local milvus failed` | another process holds the Milvus Lite file (see above); stop it, or use standalone |
| CUDA out of memory | lower `visual.batch_size`; run one step at a time (each loads one model); pick a freer card with `--device cuda:N`; for speech, `asr.compute_type: int8_float16` runs the model in 8 bits on the GPU (for int8 the faster-whisper README gives 2926 MB against 4525 MB in fp16, large-v2, 13 minutes of audio); PE-Core bigG needs a bigger card than SigLIP 2 |
| `libcuda.so.1: cannot open shared object file` from Paddle | `paddlepaddle-gpu` needs the NVIDIA driver even on the CPU; on a machine without one install the CPU build |
| Ultralytics tries to reach GitHub, or you are offline | `clip-anytorch` must be installed (it is in `requirements-objects.txt`); keep the weights and `mobileclip2_b.ts` in the working directory and set `YOLO_OFFLINE=True` |
| pip replaced your torch | install torch first, then the requirements (see Main) |
| `GetPassWarning: Can not control echo on the terminal` | the DRES password was read from a pipe, not a terminal; run `search.py --submit` in a real terminal |
| Many `UserWarning` lines during preprocessing | printed by transnetv2-pytorch while it runs; harmless |
| `ReduceMeanCheckIfOneDNNSupport` lines from Paddle | printed while it builds the models on the CPU; harmless |
| `failed to get mvccTs from milvus server` | printed by Milvus Lite when a whole video's rows are read back; harmless |
| `[SERVER][BlockLock][milvus] Process exit` at the end of a command | Milvus Lite shutting down with the script; harmless |
