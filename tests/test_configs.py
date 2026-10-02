"""The settings files shipped in configs/ parse, and give the documented defaults."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("yaml", "numpy", "PIL"))


@unittest.skipUnless(HAVE_LIBRARIES, "needs PyYAML, numpy and Pillow")
class PreprocessConfigTest(unittest.TestCase):
    def setUp(self):
        from src.config import Settings

        self.settings = Settings.load(ROOT / "configs" / "preprocess.yaml")

    def test_library_defaults(self):
        self.assertEqual(self.settings.get("shots.threshold"), 0.5)
        self.assertEqual(self.settings.get("shots.device"), "auto")
        self.assertEqual(self.settings.get("keyframes.jpeg_quality"), 75)

    def test_steps_without_a_published_default_are_off(self):
        from src.preprocess.keyframes import MiddleFrame, keyframe_policy
        from src.preprocess.quality import EachFrameAlone, KeepAll, grouping, quality_gate

        self.assertIsInstance(keyframe_policy(self.settings), MiddleFrame)
        self.assertIsInstance(quality_gate(self.settings), KeepAll)
        self.assertIsInstance(grouping(self.settings), EachFrameAlone)
        for key in ("keyframes.dense.frame_gap", "keyframes.dense.search_radius", "quality.min_sharpness",
                    "quality.min_brightness", "quality.max_brightness", "quality.min_entropy", "grouping.max_distance"):
            self.assertIsNone(self.settings.get(key), key)


@unittest.skipUnless(HAVE_LIBRARIES, "needs PyYAML, numpy and Pillow")
class IndexConfigTest(unittest.TestCase):
    def setUp(self):
        from src.config import Settings

        self.settings = Settings.load(ROOT / "configs" / "index.yaml")

    def test_every_section_the_steps_read(self):
        from src import embeddings

        self.assertTrue(set(self.settings.require("visual.encoders")) <= set(embeddings.ENCODERS))
        for name in self.settings.get("visual.encoders"):
            self.settings.require(f"visual.{name}.model")
        self.assertEqual((self.settings.get("milvus.index_type"), self.settings.get("milvus.metric_type")),
                         ("AUTOINDEX", "COSINE"))
        self.assertNotIn("://", self.settings.get("milvus.uri"))  # Milvus Lite by default
        self.assertEqual((self.settings.get("keywords.k1"), self.settings.get("keywords.b")), (1.2, 0.75))

    def test_ocr_keys_are_paddleocr_arguments(self):
        from src.ocr.reader import OPTIONS

        self.assertEqual(set(self.settings.section("ocr").to_dict()) - {"device"}, set(OPTIONS))

    def test_asr_keys_are_transcribe_arguments(self):
        from src.asr.transcriber import OWN_KEYS, transcribe_options

        asr = self.settings.section("asr")
        self.assertTrue(OWN_KEYS <= set(asr.to_dict()))
        self.assertEqual(transcribe_options(asr), {"language": "vi", "vad_filter": True})
        if importlib.util.find_spec("faster_whisper") is not None:
            import inspect

            from faster_whisper import WhisperModel

            accepted = set(inspect.signature(WhisperModel.transcribe).parameters)
            self.assertEqual(set(asr.to_dict()) - OWN_KEYS - accepted, set())

    def test_objects_are_off_and_need_prompts_to_be_turned_on(self):
        from src.object_detection.detector import OPTIONS, prompts

        objects = self.settings.section("objects")
        self.assertFalse(objects.get("enabled"))
        self.assertEqual(set(objects.to_dict()) - {"enabled", "weights", "classes", "device"}, set(OPTIONS))
        with self.assertRaises(ValueError):
            prompts(objects)



@unittest.skipUnless(HAVE_LIBRARIES, "needs PyYAML, numpy and Pillow")
class IndexConfigTest(unittest.TestCase):
    def setUp(self):
        from src.config import Settings

        self.settings = Settings.load(ROOT / "configs" / "index.yaml")

    def test_encoders_and_milvus(self):
        from src.embeddings import ENCODERS

        self.assertLessEqual(set(self.settings.get("visual.encoders")), set(ENCODERS))
        for name in ENCODERS:
            self.assertTrue(self.settings.get(f"visual.{name}.model"), name)
        self.assertEqual((self.settings.get("milvus.index_type"), self.settings.get("milvus.metric_type")),
                         ("AUTOINDEX", "COSINE"))

    def test_every_ocr_key_is_a_paddleocr_argument_and_the_thresholds_are_left_to_it(self):
        from src.ocr.reader import OPTIONS

        ocr = self.settings.section("ocr")
        self.assertEqual(set(ocr.to_dict()) - set(OPTIONS), {"device"})
        for key in ("use_textline_orientation", "text_det_limit_side_len", "text_det_limit_type", "text_det_thresh",
                    "text_det_box_thresh", "text_det_unclip_ratio", "text_rec_score_thresh"):
            self.assertIsNone(ocr.get(key), key)

    def test_every_asr_key_reaches_transcribe_by_its_own_name(self):
        from src.asr.transcriber import OWN_KEYS, transcribe_options

        asr = self.settings.section("asr")
        self.assertEqual(transcribe_options(asr), {"language": "vi", "vad_filter": True})
        self.assertLessEqual(OWN_KEYS, set(asr.to_dict()))
        if importlib.util.find_spec("faster_whisper"):
            import inspect

            from faster_whisper import WhisperModel

            passed = set(asr.to_dict()) - OWN_KEYS
            self.assertLessEqual(passed, set(inspect.signature(WhisperModel.transcribe).parameters))

    def test_objects_are_off_and_need_prompts(self):
        from src.object_detection.detector import OPTIONS, prompts

        objects = self.settings.section("objects")
        self.assertFalse(objects.get("enabled"))
        self.assertEqual(set(objects.to_dict()) - set(OPTIONS), {"enabled", "weights", "classes", "device"})
        with self.assertRaises(ValueError):
            prompts(objects)

    def test_bm25_takes_the_lucene_defaults(self):
        self.assertEqual((self.settings.get("keywords.k1"), self.settings.get("keywords.b")), (1.2, 0.75))


@unittest.skipUnless(HAVE_LIBRARIES, "needs PyYAML, numpy and Pillow")
class SearchConfigTest(unittest.TestCase):
    def setUp(self):
        from src.config import Settings

        self.settings = Settings.load(ROOT / "configs" / "search.yaml")

    def numbers(self, value, path=""):
        if isinstance(value, dict):
            for key, inner in value.items():
                yield from self.numbers(inner, f"{path}.{key}" if path else key)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            yield path, value

    def test_only_the_numbers_with_a_source_are_set(self):
        # Every other number is null. A new one has to be added here on purpose, with its source.
        self.assertEqual(dict(self.numbers(self.settings.to_dict())),
                         {"translation.max_length": 512, "depth": 100, "rows": 100, "submission.frame_id_base": 0})

    def test_the_sections_are_the_ones_the_code_reads(self):
        self.assertEqual(set(self.settings.to_dict()),
                         {"device", "visual", "translation", "depth", "fusion", "rows", "spread", "trake",
                          "submission"})

    def test_the_encoder_is_one_the_index_can_hold(self):
        from src.embeddings import ENCODERS

        self.assertIn(self.settings.get("visual.encoder"), ENCODERS)

    def test_translation_is_off_and_names_what_the_translator_takes(self):
        import inspect

        from src.retrieval.translation import Translator

        translation = self.settings.section("translation")
        self.assertFalse(translation.get("enabled"))
        parameters = inspect.signature(Translator.__init__).parameters
        self.assertEqual([name for name in parameters if name != "self"], ["model_id", "device", "max_length"])
        self.assertTrue(translation.require("model") and translation.require("max_length"))

    def test_the_rows_do_not_pass_what_the_organisers_accept(self):
        from src.submission.answers import MAX_ROWS

        self.assertLessEqual(self.settings.get("rows"), MAX_ROWS)

    def test_rrf_needs_a_k_the_user_chooses(self):
        from src.config import MissingSetting
        from src.fusion.rank_fusion import ReciprocalRankFusion
        from src.fusion.shaping import ResultShaper
        from src.retrieval.engine import SearchEngine

        self.assertIsNone(self.settings.get("fusion.rrf_k"))
        with self.assertRaisesRegex(ValueError, "fusion.rrf_k"):
            ReciprocalRankFusion(self.settings.get("fusion.rrf_k"))
        engine = SearchEngine({"visual": None, "ocr": None}, None, ResultShaper(self.settings.get("rows")),
                              self.settings.get("depth"))
        with self.assertRaisesRegex(MissingSetting, "fusion.rrf_k"):
            engine.search({"visual": "a", "ocr": "b"})

    def test_the_spread_is_off_and_asks_for_its_numbers_when_turned_on(self):
        from src.config import MissingSetting

        spread = self.settings.section("spread")
        self.assertFalse(spread.get("enabled"))
        for key in ("keep_top", "per_video"):
            with self.assertRaises(MissingSetting):
                spread.require(key)
        self.assertFalse(self.settings.get("trake.spread"))

    def test_the_trake_rules_build_with_the_open_defaults(self):
        from src.retrieval.trake import ChainRules

        trake = self.settings.section("trake")
        rules = ChainRules(trake.get("order"), trake.get("min_gap_ms"), trake.get("max_gap_ms"))
        self.assertEqual((rules.order, rules.min_gap_ms, rules.max_gap_ms), ("strict", None, None))

    def test_submission_counts_from_the_decoder_and_the_address_is_left_to_the_user(self):
        from src.config import MissingSetting

        self.assertEqual(self.settings.get("submission.frame_id_base"), 0)
        with self.assertRaisesRegex(MissingSetting, "the DRES address the organisers give you"):
            self.settings.require("submission.dres.base_url", "the DRES address the organisers give you")

if __name__ == "__main__":
    unittest.main()
