"""Extraction firewall: raw fetched text -> TypedEvent (RT-5).

Contract (non-negotiable, enforced by the type system and tests):

- Raw text from GDELT / news APIs / scraped filings is treated as DATA, never
  instructions. An LLM (cheap tier, see models.yaml `extraction_firewall`) may
  read it HERE and only here.
- The only output that crosses this boundary is a validated ``TypedEvent`` —
  typed fields, bounded severity, no free text except short enum-adjacent
  strings. Downstream agents reason over the structured form only.
- The original text is archived to ``data/raw/`` and referenced by
  ``raw_ref`` for human audit; it never re-enters agent context.

The LLM extraction call itself is Phase 2 work. ``validate_event`` is the
firewall's output gate and is used by tests (including adversarial fixtures)
from Phase 0 onward.
"""

from __future__ import annotations

from typing import Any

from nighttrader.schemas import TypedEvent

# Fields an extractor is allowed to emit. Anything else (e.g. smuggled
# "instructions" keys) fails validation — schemas forbid extra fields.
ALLOWED_FIELDS = set(TypedEvent.model_fields)


def validate_event(candidate: dict[str, Any]) -> TypedEvent:
    """Validate an extractor's raw output dict into a TypedEvent.

    Raises pydantic.ValidationError on anything malformed — a malformed event
    is dropped and logged by the caller, never "fixed up" by an LLM.
    """
    return TypedEvent.model_validate(candidate)
