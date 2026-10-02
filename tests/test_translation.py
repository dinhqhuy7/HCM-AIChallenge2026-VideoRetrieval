"""Translator with a stand-in model, and VietAI/envit5-translation itself when TRANSLATION_MODEL is set:

    TRANSLATION_MODEL=VietAI/envit5-translation python -m unittest tests.test_translation
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_TORCH = importlib.util.find_spec("torch") is not None


class FakeTokenizer:
    def __init__(self, answer):
        self.answer = answer
        self.seen = []

    def __call__(self, texts, return_tensors=None, padding=None):
        import torch
        from types import SimpleNamespace

        self.seen.append((texts, return_tensors, padding))
        return SimpleNamespace(input_ids=torch.zeros(len(texts), 3, dtype=torch.long))

    def batch_decode(self, outputs, skip_special_tokens=None):
        self.skipped = skip_special_tokens
        return [self.answer]


class FakeModel:
    def __init__(self):
        self.calls = []

    def generate(self, input_ids, max_length=None):
        import torch

        self.calls.append((tuple(input_ids.shape), max_length))
        return torch.zeros(1, 4, dtype=torch.long)


@unittest.skipUnless(HAVE_TORCH, "needs PyTorch")
class TranslatorTest(unittest.TestCase):
    def translator(self, answer):
        import torch

        from src.retrieval.translation import Translator

        translator = Translator.__new__(Translator)  # no weights: the stand-ins answer
        translator.tokenizer, translator.model = FakeTokenizer(answer), FakeModel()
        translator.device, translator.max_length, translator._torch = "cpu", 512, torch
        return translator

    def test_the_query_goes_in_as_vietnamese_and_the_prefix_comes_off(self):
        translator = self.translator("en: a man rides a motorbike")
        self.assertEqual(translator("một người đàn ông đi xe máy"), "a man rides a motorbike")
        self.assertEqual(translator.tokenizer.seen[0], (["vi: một người đàn ông đi xe máy"], "pt", True))
        self.assertEqual(translator.model.calls[0], ((1, 3), 512))
        self.assertTrue(translator.tokenizer.skipped)

    def test_an_answer_without_the_prefix_is_kept_as_it_is(self):
        self.assertEqual(self.translator("  a man rides a motorbike  ")("bất kỳ"), "a man rides a motorbike")


@unittest.skipUnless(HAVE_TORCH and os.environ.get("TRANSLATION_MODEL"), "set TRANSLATION_MODEL to run the model")
class TranslationModelTest(unittest.TestCase):
    def test_it_translates_a_query(self):
        from src.retrieval.translation import Translator

        translator = Translator(os.environ["TRANSLATION_MODEL"], os.environ.get("TEST_DEVICE", "cpu"), 512)
        english = translator("một người đàn ông mặc áo đỏ đi xe máy trên đường").lower()
        self.assertNotIn("en:", english)
        words = set(english.replace(",", " ").replace(".", " ").split())
        self.assertTrue({"man", "red"} <= words, english)
        self.assertTrue(words & {"motorbike", "motorcycle", "motorcycles"}, english)


if __name__ == "__main__":
    unittest.main()
