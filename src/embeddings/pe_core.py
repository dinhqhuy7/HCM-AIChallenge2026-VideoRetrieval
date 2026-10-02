"""Perception Encoder (PE-Core) through OpenCLIP (model card: timm/PE-Core-bigG-14-448)."""
from __future__ import annotations

import numpy as np
from PIL import Image

from src.embeddings.base import Encoder, normalised


class PECoreEncoder(Encoder):
    name = "pe_core"

    def __init__(self, model_id: str, device: str) -> None:
        import open_clip
        import torch

        model, _, self.preprocess = open_clip.create_model_and_transforms(model_id)
        if str(device).startswith("cuda"):
            # Halve before moving: bigG in fp32 is about 9.7 GB, more than many cards hold.
            model = model.half()
        self.model = model.to(device).eval()
        self.tokenizer = open_clip.get_tokenizer(model_id)
        self.device = device
        self.dtype = next(self.model.parameters()).dtype
        self._torch = torch

    def encode_images(self, images: list[Image.Image]) -> np.ndarray:
        batch = self._torch.stack([self.preprocess(image) for image in images]).to(self.device, self.dtype)
        with self._torch.inference_mode():
            return normalised(self.model.encode_image(batch))

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        # The tokenizer cuts text at the model's context length (72 tokens for bigG).
        tokens = self.tokenizer(texts).to(self.device)
        with self._torch.inference_mode():
            return normalised(self.model.encode_text(tokens))
