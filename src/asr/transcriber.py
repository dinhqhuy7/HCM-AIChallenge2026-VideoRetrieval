"""Speech to timed text with faster-whisper (Whisper models converted for CTranslate2)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import Settings
from src.retrieval.text import tidy

# Keys of the ``asr`` section read here. Every other key goes to transcribe() as it is, so
# any faster-whisper option can be set in configs/index.yaml; a key left null is not passed
# and the library's default holds. transcribe() takes no other keyword, so a misspelt key
# makes every video fail with a TypeError that names it, instead of being ignored.
OWN_KEYS = {"model", "device", "compute_type", "drop_phrases", "shot_padding_ms"}


def whisper_device(device: str) -> tuple[str, int]:
    """faster-whisper takes the card number apart: "cuda:1" -> ("cuda", 1)."""
    name, _, number = str(device).partition(":")
    return name, int(number) if number else 0


def audio_start_ms(video: Path) -> float | None:
    """Where the audio track starts on the file's clock, the clock the keyframe times are on;
    None when the file has no audio track."""
    import av

    with av.open(str(video)) as container:
        if not container.streams.audio:
            return None
        stream = container.streams.audio[0]
        return float(stream.start_time * stream.time_base) * 1000 if stream.start_time is not None else 0.0


def transcribe_options(settings: Settings) -> dict[str, Any]:
    return {key: value for key, value in settings.to_dict().items() if key not in OWN_KEYS and value is not None}


class Transcriber:
    def __init__(self, settings: Settings, device: str | None = None) -> None:
        """``settings``: the ``asr`` section of configs/index.yaml; ``device`` overrides its device."""
        from faster_whisper import WhisperModel

        name, index = whisper_device(device or settings.get("device", "auto"))
        self.model = WhisperModel(settings.require("model"), device=name, device_index=index,
                                  compute_type=settings.get("compute_type", "default"))
        self.options = transcribe_options(settings)
        self.drop = [tidy(phrase).casefold() for phrase in settings.get("drop_phrases", [])]

    def transcribe(self, video: Path) -> list[dict[str, Any]]:
        """Segments as {start_ms, end_ms, text}, on the file's clock like the keyframes. faster-
        whisper decodes the audio track itself and counts from its first sample, so the track's
        start is added. A file with no audio track has no speech. It transcribes as the
        segments are read."""
        start = audio_start_ms(video)
        if start is None:
            return []
        segments, _ = self.model.transcribe(str(video), **self.options)
        kept = []
        for segment in segments:
            text = tidy(segment.text)
            if text and not any(phrase in text.casefold() for phrase in self.drop):
                kept.append({"start_ms": round(start + segment.start * 1000),
                             "end_ms": round(start + segment.end * 1000), "text": text})
        return kept
