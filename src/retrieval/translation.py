"""Vietnamese to English for the visual query, with VietAI/envit5-translation.

The input is prefixed with "vi: " and the answer comes back prefixed with "en: ", as in the
model card. Only the visual text is translated: OCR and speech are matched in Vietnamese.
"""
from __future__ import annotations


class Translator:
    def __init__(self, model_id: str, device: str, max_length: int) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_id).to(device).eval()
        self.device = device
        self.max_length = max_length
        self._torch = torch

    def __call__(self, text: str) -> str:
        """The English of one query; the model's language prefix is taken off the answer."""
        inputs = self.tokenizer([f"vi: {text}"], return_tensors="pt", padding=True).input_ids.to(self.device)
        with self._torch.inference_mode():
            outputs = self.model.generate(inputs, max_length=self.max_length)
        answer = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
        return answer.removeprefix("en:").strip()
