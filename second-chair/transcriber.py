"""Transcription behind one interface, backend-switchable.

- faster-whisper: CTranslate2, CPU-only on Apple Silicon (no Metal backend).
  Works everywhere; used for dev and Gate 0 on Linux.
- mlx: mlx-whisper, Apple Silicon GPU. Mac only. No built-in VAD, so segments
  come from whisper's own timestamps; live chunking is handled upstream by
  audio_capture's silence-based cutting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Segment:
    start: float          # seconds, relative to whatever audio was passed in
    end: float
    text: str
    channel: str = "them"  # "them" (system audio) | "me" (mic)


class Transcriber:
    """transcribe(audio) -> list[Segment]; audio is a file path or a
    float32 mono numpy array at 16 kHz."""

    def __init__(self, backend: str, model: str, language: str | None = None):
        self.backend = backend
        self.model_name = model
        self.language = language
        if backend == "faster-whisper":
            from faster_whisper import WhisperModel
            self._model = WhisperModel(model, device="auto", compute_type="auto")
        elif backend == "mlx":
            import mlx_whisper  # noqa: F401  (Mac only)
            self._model = None
            self._mlx_repo = (
                model if "/" in model else f"mlx-community/whisper-{model}"
            )
        else:
            raise ValueError(f"unknown whisper backend: {backend}")

    def transcribe(self, audio, channel: str = "them") -> list[Segment]:
        if self.backend == "faster-whisper":
            segments, _info = self._model.transcribe(
                audio,
                language=self.language,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            return [
                Segment(s.start, s.end, s.text.strip(), channel)
                for s in segments
                if s.text.strip()
            ]
        else:
            import mlx_whisper
            result = mlx_whisper.transcribe(
                audio, path_or_hf_repo=self._mlx_repo, language=self.language
            )
            return [
                Segment(s["start"], s["end"], s["text"].strip(), channel)
                for s in result["segments"]
                if s["text"].strip()
            ]


def from_config(cfg: dict) -> Transcriber:
    w = cfg["whisper"]
    return Transcriber(w["backend"], w["model"], w.get("language"))
