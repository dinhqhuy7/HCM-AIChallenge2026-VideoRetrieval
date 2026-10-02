"""PECoreEncoder with stand-ins, the encoder registry, and the real model when PE_CORE_MODEL is set.

    PE_CORE_MODEL=hf-hub:timm/PE-Core-bigG-14-448 python -m unittest tests.test_pe_core
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("numpy", "PIL", "torch", "yaml"))


class FakeModel:
    def __init__(self):
        self.image_dtype = None

    def encode_image(self, batch):
        import torch

        self.image_dtype = batch.dtype
        return torch.full((len(batch), 4), 1.0)

    def encode_text(self, tokens):
        import torch

        return torch.tensor([[0.0, 0.0, 3.0, 4.0]] * len(tokens))


@unittest.skipUnless(HAVE_LIBRARIES, "needs numpy, Pillow, PyTorch and PyYAML")
class PECoreGlueTest(unittest.TestCase):
    def setUp(self):
        import torch

        from src.embeddings.pe_core import PECoreEncoder

        self.encoder = PECoreEncoder.__new__(PECoreEncoder)  # no weights: the stand-ins answer
        self.encoder.model, self.encoder.device, self.encoder.dtype = FakeModel(), "cpu", torch.float16
        self.encoder.preprocess = lambda image: torch.zeros(3, 8, 8)
        self.encoder.tokenizer = lambda texts: torch.zeros(len(texts), 72, dtype=torch.long)
        self.encoder._torch = torch

    def test_pictures_and_texts(self):
        import numpy as np
        from PIL import Image

        pictures = self.encoder.encode_images([Image.new("RGB", (8, 8))] * 3)
        self.assertEqual((pictures.shape, str(self.encoder.model.image_dtype)), ((3, 4), "torch.float16"))
        np.testing.assert_allclose(self.encoder.encode_texts(["a"]), [[0.0, 0.0, 0.6, 0.8]], atol=1e-6)


@unittest.skipUnless(HAVE_LIBRARIES, "needs numpy, Pillow, PyTorch and PyYAML")
class RegistryTest(unittest.TestCase):
    def test_names_and_settings(self):
        from src import embeddings
        from src.config import MissingSetting, Settings

        self.assertEqual(sorted(embeddings.ENCODERS), ["pe_core", "siglip2"])
        with self.assertRaises(ValueError):
            embeddings.load_encoder("clip", Settings({}), "cpu")
        with self.assertRaises(MissingSetting):
            embeddings.load_encoder("pe_core", Settings({"visual": {"pe_core": {"model": None}}}), "cpu")


@unittest.skipUnless(HAVE_LIBRARIES and os.environ.get("PE_CORE_MODEL"), "set PE_CORE_MODEL to run the real model")
class PECoreModelTest(unittest.TestCase):
    def test_a_colour_finds_its_words(self):
        from PIL import Image

        from src.embeddings.pe_core import PECoreEncoder

        encoder = PECoreEncoder(os.environ["PE_CORE_MODEL"], os.environ.get("TEST_DEVICE", "cpu"))
        picture = encoder.encode_images([Image.new("RGB", (448, 448), (220, 20, 20))])[0]
        red, blue = encoder.encode_texts(["a red picture", "a blue picture"])
        self.assertGreater(picture @ red, picture @ blue)


if __name__ == "__main__":
    unittest.main()
