"""Consent revocation: reversible consent, deterministically enforced.

If anyone on the call says "do not record this" (or a German equivalent),
Second Chair logs off: capture stops, the rolling buffer is purged. This is
a dumb regex on every transcribed segment ON PURPOSE — revocation must never
depend on an LLM's judgement, network, or latency. Whisper mishears things,
so the patterns are loose; a false-positive log-off is the cheap failure mode.

The v2 consent *gate* (only start after hearing consent) lives here too when
it's built; until then, asking for consent up front is on Jan.
"""

from __future__ import annotations

import re

REVOCATION_RE = re.compile(
    r"""
    (do\ n[o']?t|don'?t|please\ do\ not|stop) [\s\w]{0,15} (record|transcrib)
    | off\ the\ record
    | (nicht|bitte\ nicht|keine?) [\s\w]{0,15} (aufzeichn|aufnehm|aufnahme|mitschneid|mitschnitt|protokollier)
    | unter\ (uns|vier\ augen)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_revocation(text: str) -> bool:
    return bool(REVOCATION_RE.search(text))
