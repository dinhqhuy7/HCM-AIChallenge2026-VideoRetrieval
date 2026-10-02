"""Image-text encoders. Adding one is adding a class and a line in ENCODERS."""
from __future__ import annotations

from src.config import Settings
from src.embeddings.base import Encoder
from src.embeddings.pe_core import PECoreEncoder
from src.embeddings.siglip2 import SigLIP2Encoder

ENCODERS: dict[str, type[Encoder]] = {
    SigLIP2Encoder.name: SigLIP2Encoder,
    PECoreEncoder.name: PECoreEncoder,
}


def load_encoder(name: str, settings: Settings, device: str) -> Encoder:
    """``settings`` is configs/index.yaml; the model comes from ``visual.<name>.model``."""
    if name not in ENCODERS:
        raise ValueError(f"unknown encoder {name!r}; choose from {sorted(ENCODERS)}")
    return ENCODERS[name](settings.require(f"visual.{name}.model"), device)
