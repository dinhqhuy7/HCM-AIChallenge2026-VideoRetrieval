"""The one interface every image-text encoder offers to the rest of the system."""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from PIL import Image


class Encoder(ABC):
    """Maps pictures and sentences into one space. Vectors come out L2-normalised, so an
    inner product between two of them is their cosine similarity."""

    name: str

    @abstractmethod
    def encode_images(self, images: list[Image.Image]) -> np.ndarray:
        """float32 array of shape (len(images), dim)."""

    @abstractmethod
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        """float32 array of shape (len(texts), dim)."""

    @property
    def dim(self) -> int:
        """Length of a vector, measured once on a short sentence."""
        if not hasattr(self, "_dim"):
            self._dim = int(self.encode_texts(["a"]).shape[1])
        return self._dim


def normalised(features) -> np.ndarray:
    """A torch tensor, on any device and in any float type, as unit-length float32 rows."""
    import torch

    return torch.nn.functional.normalize(features.float(), dim=-1).cpu().numpy().astype(np.float32)


def half_on_cuda(device: str):
    """fp16 on a GPU, fp32 on the CPU."""
    import torch

    return torch.float16 if str(device).startswith("cuda") else torch.float32
