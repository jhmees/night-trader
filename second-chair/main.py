"""Second Chair v1 — wire everything together.

  python main.py                # full app: capture + hotkey + overlay
  python main.py --no-ui        # capture + hotkey, notes to terminal
  python main.py --file x.wav   # build-order step 2: transcribe a WAV, no live audio
"""

from __future__ import annotations

import argparse
import threading

import yaml

import transcriber as transcriber_mod
from brief import BriefEngine
from buffer import RollingBuffer
from llm import LLM


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--file", help="transcribe one audio file and exit")
    ap.add_argument("--no-ui", action="store_true", help="print notes, no overlay")
    args = ap.parse_args()

    cfg = load_config(args.config)
    tr = transcriber_mod.from_config(cfg)

    if args.file:
        for seg in tr.transcribe(args.file):
            print(f"[{seg.start:7.1f}s] {seg.text}")
        return

    buffer = RollingBuffer(cfg["brief"]["buffer_sec"])
    engine = BriefEngine(cfg, buffer, LLM(cfg))

    import audio_capture
    import consent

    streams: list = []

    def on_segment(seg):
        if consent.is_revocation(seg.text):
            # reversible consent: someone said "do not record this" -> log off
            for s in streams:
                s.stop()
            buffer.purge()
            print("⏻ consent revoked — capture stopped, buffer purged")
            return
        buffer.append(seg)
        print(f"  · [{seg.channel}] {seg.text}")

    streams.extend(audio_capture.start_capture(cfg, tr, on_segment))
    print("Capturing. Hotkey:", cfg["brief"]["hotkey"])

    overlay = None
    if not args.no_ui:
        from overlay import Overlay
        overlay = Overlay()

    def on_hotkey():
        print("brief requested …", flush=True)
        # LLM call off the hotkey thread so the listener never blocks
        def run():
            note = engine.run()
            if note is None:
                print("PASS")
            else:
                print(f"NOTE: {note}")
                if overlay:
                    overlay.show(note)
        threading.Thread(target=run, daemon=True).start()

    from pynput import keyboard
    hotkeys = keyboard.GlobalHotKeys({cfg["brief"]["hotkey"]: on_hotkey})
    hotkeys.start()

    if overlay:
        overlay.mainloop()   # macOS: Tk must own the main thread
    else:
        hotkeys.join()


if __name__ == "__main__":
    main()
