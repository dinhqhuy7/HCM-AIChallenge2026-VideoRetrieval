import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("numpy", "PIL", "torch"))


@unittest.skipUnless(HAVE_LIBRARIES, "needs numpy, Pillow and PyTorch")
class EncoderBaseTest(unittest.TestCase):
    def test_dim_is_measured_once(self):
        import numpy as np

        from src.embeddings.base import Encoder

        class Fake(Encoder):
            name, calls = "fake", 0

            def encode_images(self, images):
                return np.zeros((len(images), 3), dtype=np.float32)

            def encode_texts(self, texts):
                self.calls += 1
                return np.zeros((len(texts), 3), dtype=np.float32)

        encoder = Fake()
        self.assertEqual((encoder.dim, encoder.dim, encoder.calls), (3, 3, 1))

    def test_normalised_rows(self):
        import numpy as np
        import torch

        from src.embeddings.base import normalised

        rows = normalised(torch.tensor([[3.0, 4.0], [0.0, 0.0], [1.0, 1.0]], dtype=torch.float16))
        self.assertEqual(rows.dtype, np.float32)
        np.testing.assert_allclose(rows, [[0.6, 0.8], [0.0, 0.0], [0.7071068, 0.7071068]], atol=1e-3)

    def test_half_on_cuda(self):
        import torch

        from src.embeddings.base import half_on_cuda

        self.assertEqual([half_on_cuda(d) for d in ("cuda", "cuda:1", "cpu")],
                         [torch.float16, torch.float16, torch.float32])


if __name__ == "__main__":
    unittest.main()
