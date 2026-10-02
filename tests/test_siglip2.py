"""SigLIP2Encoder with a stand-in processor and model; with the real model when SIGLIP2_MODEL is set.

    SIGLIP2_MODEL=google/siglip2-so400m-patch14-384 python -m unittest tests.test_siglip2
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("numpy", "PIL", "torch"))


class Batch(dict):
    def to(self, device):
        return self


class FakeProcessor:
    def __init__(self):
        self.calls = []

    def __call__(self, text=None, images=None, **options):
        import torch

        self.calls.append((text, options))
        if images is not None:
            return Batch(pixel_values=torch.zeros(len(images), 3, 4, 4, dtype=torch.float32))
        return Batch(input_ids=torch.zeros(len(text), options["max_length"], dtype=torch.long))


class FakeModel:
    def __init__(self):
        self.pixel_dtype = None

    def get_image_features(self, pixel_values):
        import torch

        self.pixel_dtype = pixel_values.dtype
        return torch.full((len(pixel_values), 3), 2.0)

    def get_text_features(self, input_ids):
        import torch

        return torch.tensor([[3.0, 4.0, 0.0]] * len(input_ids))


@unittest.skipUnless(HAVE_LIBRARIES, "needs numpy, Pillow and PyTorch")
class SigLIP2GlueTest(unittest.TestCase):
    def setUp(self):
        import torch

        from src.embeddings.siglip2 import SigLIP2Encoder

        self.encoder = SigLIP2Encoder.__new__(SigLIP2Encoder)  # no weights: the stand-ins answer
        self.encoder.device, self.encoder.dtype, self.encoder._torch = "cpu", torch.float16, torch
        self.encoder.processor, self.encoder.model = FakeProcessor(), FakeModel()

    def test_text_is_lower_cased_and_padded_to_64_tokens(self):
        import numpy as np

        vectors = self.encoder.encode_texts(["Hai Người Phụ Nữ"])
        (texts, options), = self.encoder.processor.calls
        self.assertEqual(texts, ["hai người phụ nữ"])
        expected = {"padding": "max_length", "max_length": 64, "truncation": True, "return_tensors": "pt"}
        self.assertEqual(options, expected)
        np.testing.assert_allclose(vectors, [[0.6, 0.8, 0.0]], atol=1e-6)

    def test_pictures_are_cast_to_the_model_type(self):
        import numpy as np
        from PIL import Image

        vectors = self.encoder.encode_images([Image.new("RGB", (8, 8))] * 2)
        self.assertEqual(str(self.encoder.model.pixel_dtype), "torch.float16")
        self.assertEqual(vectors.dtype, np.float32)
        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), [1.0, 1.0], atol=1e-6)


@unittest.skipUnless(HAVE_LIBRARIES and os.environ.get("SIGLIP2_MODEL"), "set SIGLIP2_MODEL to run the real model")
class SigLIP2ModelTest(unittest.TestCase):
    def test_a_colour_finds_its_words(self):
        from PIL import Image

        from src.embeddings.siglip2 import SigLIP2Encoder

        encoder = SigLIP2Encoder(os.environ["SIGLIP2_MODEL"], os.environ.get("TEST_DEVICE", "cpu"))
        picture = encoder.encode_images([Image.new("RGB", (384, 384), (220, 20, 20))])[0]
        red, blue = encoder.encode_texts(["a red picture", "a blue picture"])
        self.assertEqual(encoder.dim, 1152)
        self.assertGreater(picture @ red, picture @ blue)


if __name__ == "__main__":
    unittest.main()
