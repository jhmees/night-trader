"""Brief engine: hotkey -> assemble prompt -> LLM -> note | PASS.

PASS must be the modal outcome. Silence is the default, not the exception.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

from buffer import RollingBuffer
from llm import LLM

SYSTEM_PROMPT = """\
You are Jan's silent second chair in a client negotiation. You read a short \
transcript segment of an ongoing call (auto-transcribed, so expect \
recognition errors, especially in chemical names — reconstruct charitably). \
If anything deserves his attention — a number that sounds off, a \
contradiction with earlier statements or the deal context, a regulatory \
implication, an unfamiliar term, a negotiating tell — write a note of at \
most 2 lines. If a web lookup would materially improve the note, do it. \
Notes already shown this session are listed; never repeat one.

If nothing clears that bar, reply with exactly: PASS

Most segments deserve PASS. Silence is the default, not the exception."""


class BriefEngine:
    def __init__(self, cfg: dict, buffer: RollingBuffer, llm: LLM):
        self.window_sec = cfg["brief"]["window_sec"]
        self.deal_context_path = Path(cfg["brief"]["deal_context"])
        self.sessions_dir = Path(cfg["paths"]["sessions_dir"])
        self.buffer = buffer
        self.llm = llm
        self.shown_notes: list[str] = []

    def _deal_context(self) -> str:
        if self.deal_context_path.exists():
            return self.deal_context_path.read_text().strip()
        return "(no deal context file)"

    def build_user_prompt(self) -> str:
        shown = (
            "\n".join(f"- {n}" for n in self.shown_notes)
            if self.shown_notes
            else "(none yet)"
        )
        transcript = self.buffer.window(self.window_sec) or "(no speech captured)"
        return (
            f"## Deal context\n{self._deal_context()}\n\n"
            f"## Notes already shown this session\n{shown}\n\n"
            f"## Last {int(self.window_sec)}s of transcript\n{transcript}"
        )

    def run(self) -> str | None:
        """Returns the note text, or None on PASS."""
        answer = self.llm.complete(SYSTEM_PROMPT, self.build_user_prompt())
        is_pass = answer.strip().upper() == "PASS"
        self._log(answer, is_pass)
        if is_pass:
            return None
        self.shown_notes.append(answer)
        return answer

    def _log(self, answer: str, is_pass: bool) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        path = self.sessions_dir / f"{dt.date.today().isoformat()}.jsonl"
        entry = {
            "ts": time.time(),
            "result": "PASS" if is_pass else "note",
            "text": answer,
            "transcript_window": self.buffer.window(self.window_sec),
        }
        with path.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
