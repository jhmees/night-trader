"""Periodic LLM sweep that maintains the copilot state.

Every N seconds the engine sends: meeting setup + current state + fresh
transcript, and gets back the full updated state as JSON. The LLM owns the
judgement (what to ask, what to check, what changed); this module owns the
state, the schema, and surviving malformed output.

State schema (all lists may be empty; ids must stay stable across sweeps):
{
  "questions":   [{"id","rank","text","why","status":"open|answered","reason"}],
  "facts":       [{"id","claim","who","verdict":"checking|verified|misleading|false|unverifiable","detail"}],
  "numbers":     [{"id","label","value","who","flag"}],
  "commitments": [{"id","who":"them|me","text","due"}],
  "goals":       [{"id","text","status":"open|on-track|at-risk|met","note"}],
  "note":        null or "≤2-line note worth sliding to Jan now"
}
"""

from __future__ import annotations

import copy
import json
import re

EMPTY_STATE: dict = {
    "questions": [], "facts": [], "numbers": [],
    "commitments": [], "goals": [], "note": None,
}

SWEEP_SYSTEM = """\
You are Jan's silent second chair in a live meeting. You maintain his working
state between transcript sweeps. The transcript is auto-generated — expect
recognition errors and reconstruct charitably.

Return ONLY a JSON object with keys: questions, facts, numbers, commitments,
goals, note. No prose, no markdown fences.

Rules:
- questions: smart follow-ups JAN could ask, serving his stated goals. Max 5
  with status "open", ranked 1 = most relevant. If the other side already
  answered one (even unprompted), set status "answered" and say so in
  "reason" — never delete it. Rewrite "why" as the situation moves.
- facts: factual claims THE OTHER SIDE made that are checkable. Verdict
  "checking" until you can judge; use web search if available. Never fact-check
  Jan's own statements.
- numbers: every concrete figure on the table (prices, volumes, dates, terms),
  who said it. If a new figure contradicts an earlier one, set "flag" on the
  new entry (e.g. "was 200 t/yr at 03:19"). Otherwise flag = null.
- commitments: things either side promised to do. "due" if stated, else null.
- goals: Jan's goals from setup, split into 2-4 trackable items on the first
  sweep, ids stable after that. Update status/note as evidence arrives.
- note: normally null. Only set it when something Jan may have missed needs
  his eyes NOW (per his proactivity setting). Max 2 lines. Never repeat a
  note you already sent.
- Keep every id stable across sweeps. Return the FULL state each time.
"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

REQUIRED_KEYS = ("questions", "facts", "numbers", "commitments", "goals")


def extract_json(text: str) -> dict | None:
    m = _JSON_RE.search(text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or not all(k in obj for k in REQUIRED_KEYS):
        return None
    for k in REQUIRED_KEYS:
        if not isinstance(obj[k], list):
            return None
    obj.setdefault("note", None)
    return obj


class SweepEngine:
    def __init__(self, llm, setup: dict):
        """setup: {"purpose": str, "goals": str, "proactivity": str}"""
        self.llm = llm
        self.setup = setup
        self.state = copy.deepcopy(EMPTY_STATE)
        self.sent_notes: list[str] = []
        self.failures = 0

    def _prompt(self, transcript: str) -> str:
        return (
            f"## Meeting\nPurpose: {self.setup['purpose']}\n"
            f"Proactivity: {self.setup['proactivity']}\n"
            f"Jan's goals: {self.setup['goals']}\n\n"
            f"## Current state (yours, from last sweep)\n"
            f"{json.dumps(self.state, ensure_ascii=False)}\n\n"
            f"## Notes already slid to Jan (never repeat)\n"
            f"{json.dumps(self.sent_notes, ensure_ascii=False)}\n\n"
            f"## Transcript (recent window, oldest first)\n{transcript}\n\n"
            f"Return the full updated state JSON."
        )

    def sweep(self, transcript: str) -> dict | None:
        """Runs one sweep. Returns the new state, or None if the LLM output
        was unusable (state then stays as-is)."""
        raw = self.llm.complete(SWEEP_SYSTEM, self._prompt(transcript))
        new = extract_json(raw)
        if new is None:
            self.failures += 1
            return None
        note = new.get("note")
        if note and note in self.sent_notes:   # belt & braces vs rule above
            new["note"] = None
        elif note:
            self.sent_notes.append(note)
        self.state = new
        return new


DEBRIEF_SYSTEM = """\
You are Jan's second chair, writing the post-call debrief. Be concrete and
short. Markdown with exactly these sections:
# Debrief
## What happened (≤4 bullets)
## Goals (one line each: status + evidence)
## Commitments (theirs and ours, with dates)
## Watch out (contradictions, unverified claims — omit if none)
## Draft follow-up email (short, sendable, in the language of the call)
"""


def debrief(llm, setup: dict, state: dict, transcript: str) -> str:
    prompt = (
        f"Purpose: {setup['purpose']}\nJan's goals: {setup['goals']}\n\n"
        f"Final state:\n{json.dumps(state, ensure_ascii=False)}\n\n"
        f"Full transcript:\n{transcript}"
    )
    return llm.complete(DEBRIEF_SYSTEM, prompt)
