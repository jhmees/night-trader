"""Live audio capture -> silence-cut chunks -> transcriber -> rolling buffer.

macOS path: BlackHole 2ch carries system output (what the client says);
the default mic carries Jan. Two independent streams, tagged them/me.
Chunking is deliberately dumb: cut on ~0.8s of silence (RMS gate) or at
max_chunk_sec, then hand the chunk to whisper (whose own VAD trims edges).
Runs on any OS sounddevice supports; only the BlackHole routing is Mac-specific.
"""

from __future__ import annotations

import queue
import threading

import numpy as np
import sounddevice as sd

from transcriber import Transcriber

RMS_SILENCE = 0.01  # tune if the gate never/always fires


class ChannelCapture:
    """One input device -> chunk queue."""

    def __init__(self, device: str | None, channel: str, cfg: dict):
        a = cfg["audio"]
        self.device = device
        self.channel = channel
        self.rate = a["sample_rate"]
        self.silence_blocks = int(a["silence_sec"] * self.rate / 1024)
        self.max_blocks = int(a["max_chunk_sec"] * self.rate / 1024)
        self.chunks: queue.Queue[np.ndarray] = queue.Queue()
        self._current: list[np.ndarray] = []
        self._quiet = 0

    def _on_block(self, indata, frames, t, status):
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata[:, 0]
        self._current.append(mono.copy())
        rms = float(np.sqrt(np.mean(mono**2)))
        self._quiet = self._quiet + 1 if rms < RMS_SILENCE else 0
        long_enough = len(self._current) >= self.max_blocks
        pause = self._quiet >= self.silence_blocks and len(self._current) > self._quiet
        if long_enough or pause:
            chunk = np.concatenate(self._current)
            self._current, self._quiet = [], 0
            if float(np.sqrt(np.mean(chunk**2))) >= RMS_SILENCE / 2:
                self.chunks.put(chunk)

    def start(self) -> sd.InputStream:
        stream = sd.InputStream(
            device=self.device,
            samplerate=self.rate,
            blocksize=1024,
            channels=1,
            dtype="float32",
            callback=self._on_block,
        )
        stream.start()
        return stream


def start_capture(cfg: dict, transcriber: Transcriber,
                  on_segment) -> list[sd.InputStream]:
    """Starts them+me capture and a transcription worker per channel.
    Every finalized Segment goes to on_segment (which owns the buffer)."""
    a = cfg["audio"]
    captures = [
        ChannelCapture(a["system_device"], "them", cfg),
        ChannelCapture(a.get("mic_device"), "me", cfg),
    ]

    def worker(cap: ChannelCapture):
        while True:
            chunk = cap.chunks.get()
            for seg in transcriber.transcribe(chunk, channel=cap.channel):
                on_segment(seg)

    streams = []
    for cap in captures:
        streams.append(cap.start())
        threading.Thread(target=worker, args=(cap,), daemon=True).start()
    return streams
