"""Second Chair console: FastAPI backend + websocket, serves static/ UI.

  python server.py            # http://localhost:8710
  mode "demo": scripted call + mock LLM (no audio, no API key needed)
  mode "live": BlackHole/mic capture -> whisper -> real LLM sweeps

One session at a time — this is a single-user tool by design.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import time
from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

import consent
import sweeps
from buffer import RollingBuffer
from transcriber import Segment

app = FastAPI()
CFG = yaml.safe_load(open(Path(__file__).parent / "config.yaml"))


class Session:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.running = False
        self.mode = "demo"
        self.setup: dict = {}
        self.buffer: RollingBuffer | None = None
        self.engine: sweeps.SweepEngine | None = None
        self.llm = None
        self.tasks: list[asyncio.Task] = []
        self.streams: list = []          # live-audio streams
        self.transcript_log: list[dict] = []
        self.t0 = 0.0
        self.revoked = False
        self.seen_segments = 0           # sweep trigger: only sweep on new text

    def clock(self) -> str:
        s = int(time.time() - self.t0)
        return f"{s // 60:02d}:{s % 60:02d}"


S = Session()


async def broadcast(msg: dict) -> None:
    dead = []
    for ws in S.clients:
        try:
            await ws.send_text(json.dumps(msg, ensure_ascii=False))
        except Exception:
            dead.append(ws)
    for ws in dead:
        S.clients.discard(ws)


async def handle_segment(seg: Segment) -> None:
    """Single entry point for every transcribed segment, demo or live."""
    if S.revoked:
        return
    if consent.is_revocation(seg.text):
        S.revoked = True
        for st in S.streams:
            st.stop()
        S.buffer.purge()
        await broadcast({"type": "revoked"})
        return
    S.buffer.append(seg)
    entry = {"who": seg.channel, "ts": S.clock(), "text": seg.text}
    S.transcript_log.append(entry)
    await broadcast({"type": "seg", **entry})


async def sweep_loop() -> None:
    interval = CFG["server"]["demo_sweep_interval_sec"] if S.mode == "demo" \
        else CFG["server"]["sweep_interval_sec"]
    while S.running:
        await asyncio.sleep(interval)
        if S.revoked or len(S.transcript_log) == S.seen_segments:
            continue  # nothing new said — don't burn a call
        S.seen_segments = len(S.transcript_log)
        window = S.buffer.window(CFG["brief"]["buffer_sec"])
        state = await asyncio.to_thread(S.engine.sweep, window)
        if state is None:
            await broadcast({"type": "status", "text": "sweep failed — state kept"})
            continue
        await broadcast({"type": "state", "state": state})
        if state.get("note"):
            await broadcast({"type": "note", "text": state["note"]})


async def demo_feed() -> None:
    from demo import DEMO_SEGMENTS
    for delay, who, text in DEMO_SEGMENTS:
        await asyncio.sleep(delay)
        if not S.running:
            return
        await handle_segment(Segment(0, 0, text, who))
    await broadcast({"type": "status", "text": "demo call finished — hit End call for the debrief"})


def start_live_audio(loop: asyncio.AbstractEventLoop) -> None:
    import audio_capture
    import transcriber as transcriber_mod

    tr = transcriber_mod.from_config(CFG)

    def on_segment(seg: Segment) -> None:   # called from capture worker threads
        asyncio.run_coroutine_threadsafe(handle_segment(seg), loop)

    S.streams = audio_capture.start_capture(CFG, tr, on_segment)


@app.post("/api/start")
async def api_start(body: dict):
    await stop_session()
    S.__init__()
    S.mode = body.get("mode", "demo")
    S.setup = {
        "purpose": body.get("purpose", "Meeting"),
        "goals": body.get("goals", ""),
        "proactivity": body.get("proactivity", "second chair"),
    }
    S.buffer = RollingBuffer(CFG["brief"]["buffer_sec"])
    if S.mode == "demo":
        from demo import MockLLM
        S.llm = MockLLM()
    else:
        from llm import LLM
        S.llm = LLM(CFG)
    S.engine = sweeps.SweepEngine(S.llm, S.setup)
    S.t0 = time.time()
    S.running = True
    loop = asyncio.get_running_loop()
    if S.mode == "demo":
        S.tasks.append(asyncio.create_task(demo_feed()))
    else:
        try:
            await asyncio.to_thread(start_live_audio, loop)
        except Exception as e:
            S.running = False
            return {"ok": False, "error": f"audio start failed: {e}"}
    S.tasks.append(asyncio.create_task(sweep_loop()))
    return {"ok": True, "mode": S.mode}


async def stop_session() -> None:
    S.running = False
    for t in S.tasks:
        t.cancel()
    S.tasks.clear()
    for st in S.streams:
        try:
            st.stop()
        except Exception:
            pass
    S.streams.clear()


@app.post("/api/end")
async def api_end():
    """End the call: final sweep state -> debrief, persist session, stop."""
    transcript = "\n".join(f"[{e['ts']} {e['who']}] {e['text']}" for e in S.transcript_log)
    md = await asyncio.to_thread(
        sweeps.debrief, S.llm, S.setup, S.engine.state if S.engine else {}, transcript
    )
    sessions = Path(CFG["paths"]["sessions_dir"])
    sessions.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    (sessions / f"{stamp}_debrief.md").write_text(md)
    (sessions / f"{stamp}_session.json").write_text(json.dumps(
        {"setup": S.setup, "transcript": S.transcript_log,
         "state": S.engine.state if S.engine else {}},
        ensure_ascii=False, indent=1))
    await stop_session()
    await broadcast({"type": "debrief", "markdown": md})
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    S.clients.add(ws)
    # late joiner gets the story so far
    for e in S.transcript_log:
        await ws.send_text(json.dumps({"type": "seg", **e}, ensure_ascii=False))
    if S.engine and S.engine.state != sweeps.EMPTY_STATE:
        await ws.send_text(json.dumps({"type": "state", "state": S.engine.state},
                                      ensure_ascii=False))
    if S.revoked:
        await ws.send_text(json.dumps({"type": "revoked"}))
    try:
        while True:
            await ws.receive_text()      # client sends nothing; keepalive only
    except WebSocketDisconnect:
        S.clients.discard(ws)


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=CFG["server"]["port"], log_level="warning")
