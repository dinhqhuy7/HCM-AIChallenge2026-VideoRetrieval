"""SigLIP 2 through Hugging Face transformers (model card: google/siglip2-so400m-patch14-384)."""
from __future__ import annotations

import numpy as np
from PIL import Image

from src.embeddings.base import Encoder, half_on_cuda, normalised


class SigLIP2Encoder(Encoder):
    name = "siglip2"
    # The model was trained on lower-cased text, padded and cut to 64 tokens. These are the
    # defaults of the SigLIP 2 processor in transformers, and its documentation lower-cases
    # text first; they are written out so that a reader sees what reaches the model.
    TEXT_LENGTH = 64

    def __init__(self, model_id: str, device: str) -> None:
        import torch
        from transformers import AutoModel, AutoProcessor

        self.device = device
        self.dtype = half_on_cuda(device)
        self.model = AutoModel.from_pretrained(model_id, dtype=self.dtype).to(device).eval()
        self.processor = AutoProcessor.from_pretrained(model_id)
        self._torch = torch

    def encode_images(self, images: list[Image.Image]) -> np.ndarray:
        inputs = self.processor(images=images, return_tensors="pt").to(self.device)
        with self._torch.inference_mode():
            features = self.model.get_image_features(pixel_values=inputs["pixel_values"].to(self.dtype))
        return normalised(features)

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        inputs = self.processor(text=[text.lower() for text in texts], padding="max_length",
                                max_length=self.TEXT_LENGTH, truncation=True, return_tensors="pt").to(self.device)
        with self._torch.inference_mode():
            features = self.model.get_text_features(**inputs)
        return normalised(features)
