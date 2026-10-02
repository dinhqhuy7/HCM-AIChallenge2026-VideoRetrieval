# Models

Sizes are those of the downloaded weight files, in decimal GB. Licences are the ones named on
each model's own page; read them before you build on a model.

| Model | Used for | Where it comes from | Licence | Size |
|---|---|---|---|---|
| TransNetV2 | shot boundaries | weights bundled in the `transnetv2-pytorch` package, a PyTorch port of [soCzech/TransNetV2](https://github.com/soCzech/TransNetV2) | MIT | 30 MB |
| [google/siglip2-so400m-patch14-384](https://huggingface.co/google/siglip2-so400m-patch14-384) | image and text embeddings, 1152 dimensions | Hugging Face, loaded with transformers | Apache-2.0 | 4.5 GB |
| [timm/PE-Core-bigG-14-448](https://huggingface.co/timm/PE-Core-bigG-14-448) | image and text embeddings, 1280 dimensions, text up to 72 tokens | Hugging Face, loaded with OpenCLIP (`hf-hub:` name) | Apache-2.0 | 9.7 GB |
| [timm/PE-Core-L-14-336](https://huggingface.co/timm/PE-Core-L-14-336) | the smaller PE-Core: 1024 dimensions, text up to 32 tokens | as above | Apache-2.0 | 2.7 GB |
| [VietAI/envit5-translation](https://huggingface.co/VietAI/envit5-translation) | Vietnamese to English, visual query only | Hugging Face, loaded with transformers | OpenRAIL | 1.1 GB |
| [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3) | speech to text | Hugging Face, loaded by faster-whisper as `large-v3` | MIT (converted from [openai/whisper-large-v3](https://huggingface.co/openai/whisper-large-v3), Apache-2.0) | 3.1 GB |
| PP-OCRv6_medium_det | text detection | PaddleOCR, downloaded on first use | Apache-2.0 | 62 MB |
| PP-OCRv6_medium_rec | text recognition | PaddleOCR, downloaded on first use | Apache-2.0 | 77 MB |
| [PP-LCNet_x1_0_textline_ori](https://huggingface.co/PaddlePaddle/PP-LCNet_x1_0_textline_ori) | text-line orientation, used by the default OCR pipeline | PaddleOCR, downloaded on first use | Apache-2.0 | 7 MB |
| yoloe-26l-seg (optional) | objects from text prompts | Ultralytics, downloaded on first use | AGPL-3.0 (the `ultralytics` package) | 79 MB |
| MobileCLIP2-B text encoder (optional) | YOLOE's text prompts | Ultralytics fetches it as `mobileclip2_b.ts` | Apple's card for [apple/MobileCLIP2-B](https://huggingface.co/apple/MobileCLIP2-B) names `apple-amlr` | 254 MB |

How to download them ahead, and where each cache lives: [setup.md](setup.md#models).

## Notes per model

**SigLIP 2.** Text is lower-cased and padded to 64 tokens, the defaults of its processor in
transformers: the model was trained on lower-cased text. Its card is titled "Multilingual
Vision-Language Encoders", so a Vietnamese query can be searched as typed. Loaded in fp16 on a
GPU; a batch of 16 keyframes peaks at 2.5 GiB.

**PE-Core.** Loaded as in its model card:
`open_clip.create_model_and_transforms('hf-hub:timm/PE-Core-bigG-14-448')`. The weights are
halved *before* they are moved to the GPU; the other way round, the fp32 copy (9.7 GB) has to
fit on the card first, and loading peaked at 4.5 GiB with the halving first. The text encoder
cuts a query at its context length (72 tokens for bigG, 32 for the L model). The card does not
say which languages the text encoder reads. Measured on the L model, it reads Vietnamese poorly
(next section), so turn on `translation` in `configs/search.yaml` when you search it.

**envit5-translation.** The input is prefixed with `vi: `; the output comes back prefixed with
`en: `, as in the model card, and `generate(..., max_length=512)` follows its example. The prefix
is not decoration: without it the same query came back as repeated words. The English is cut
off at 512 tokens: a query of 4,500 characters came back ending mid-sentence. It costs 0.2 to
0.5 s a query on a GPU, and it makes mistakes (see below). The licence is OpenRAIL, which carries
use restrictions.

**Whisper large-v3 (faster-whisper).** Runs on CTranslate2; the weights are stored in fp16. With
the library's default settings it invented speech over music on a contest video: with
`vad_filter` off, the opening three minutes of one video came out as a single made-up "subscribe
to the channel" line, repeated every 30 seconds, in place of the real speech. With it on, the
same minutes were transcribed. `configs/index.yaml` turns it on
([offline/04-asr.md](offline/04-asr.md)). A 21-minute video took 141 s on one RTX 2080 Ti.

**PP-OCRv6 medium.** The recogniser's dictionary has 18,708 entries, 83% of them single Chinese
characters. Of the 67 accented Vietnamese lower-case letters it holds 23:

- it can write: à á ã ă â è é ê ì í ĩ ò ó õ ô ồ ơ ù ú ũ ư ý đ
- it cannot write the other 44: ả ạ ằ ắ ẳ ẵ ặ ầ ấ ẩ ẫ ậ ẻ ẽ ẹ ề ế ể ễ ệ ỉ ị ỏ ọ ố ổ ỗ ộ ờ ớ ở ỡ ợ ủ ụ ừ ứ ử ữ ự ỳ ỷ ỹ ỵ

The upper-case letters have the same gaps (23 of 67). Check it yourself: the list is under
`character_dict` in the model's `inference.yml`. A letter that is not in the dictionary comes
out as a close one when it is upper case ("CẤP TỐC" read as "CÃP TÕC") and is dropped when it is
lower case ("chạy" read as "chy"). The keyword index folds accents away on both sides, so the
first kind of mistake still matches; the second does not.

`PaddleOCR(lang="vi")` selects this same pair of models in PaddleOCR 3.7.0, not a Vietnamese
one. On two keyframes whose 43 words were written out by hand, it found 34 of them once accents
were folded, against 26 for `latin_PP-OCRv5_mobile_rec`, whose dictionary holds 22 of the 67
letters. That is a small sample.

The default pipeline also runs the text-line orientation model. On six landscape keyframes it
changed nothing; on one portrait keyframe it turned a short "10" upside down and read "DI"
(score 0.84), where with the model off it read "10" (0.99). The configuration leaves it at the
library default.

**YOLOE.** Optional and off by default. The object names to look for are the text prompts
(`objects.classes`). At the library's default thresholds one object can get two boxes (the whole
body and the upper body), and a box over nearly the whole frame can appear with a low score (an
"airplane" at 0.29 on an airport shot), so per-keyframe counts run high; `objects.conf` is yours to
choose and has no published value. Setup: [setup.md](setup.md#objects-optional).

## Does the language of the query matter?

A check you can repeat on your own keyframes. For ten queries (a studio, a street with
motorbikes, a rice field, a lion dance, a runway ...) on 416 keyframes of three videos, the same
question was asked in Vietnamese, machine-translated with envit5, and written in English by hand.
The table is how many of the first 10 keyframes of the Vietnamese or translated query are also
among the first 10 of the English one (chance level: 0.24):

| Model | Vietnamese as typed | Translated by envit5 |
|---|---|---|
| PE-Core-L-14-336 | 1.8 of 10 | 7.9 of 10 |
| SigLIP 2 | 6.4 of 10 | 7.5 of 10 |

For the studio keyframe checked by eye, PE-Core-L ranked it 106th for the Vietnamese query, 13th
for the translated one and 3rd for the English one; SigLIP 2 ranked it 2nd, 2nd and 1st. The
translator is not safe either: "múa lân trên cột cao" (a lion dance on high poles) came back as
"Flying phosphors on a high mast", and that query agreed with the English one on 0 of 10.

So: SigLIP 2 takes Vietnamese as typed, and trying `translation` both ways on your own queries
is cheap; PE-Core wants it on. Ten queries and three videos are an indication, not a benchmark,
and PE-Core bigG was not measured.
