"""Demo call: a scripted negotiation + a mock LLM with canned sweep states.

Two jobs: (1) try the whole app with no headset, no API key, no Mac —
`mode: demo` in the UI; (2) integration-test harness for the real pipeline
(segments flow through the same buffer/consent/sweep/broadcast code paths).
"""

from __future__ import annotations

import json

# (delay_sec, who, text) — mirrors the design-doc negotiation, extended with
# commitments and a deliberate number contradiction (200 t -> 150 t).
DEMO_SEGMENTS: list[tuple[float, str, str]] = [
    (1.0, "them", "So — we reviewed the offer. Honestly, €2.40 per kilo for the propylenediamine is well above what we see in the market right now."),
    (4.0, "me",   "That figure includes REACH registration, CoA per batch and delivered logistics — happy to break it down."),
    (5.0, "them", "Fair enough. For planning purposes we'd need roughly 200 tonnes a year, delivered quarterly to Hamburg."),
    (5.0, "them", "And I'll be direct: Brenntag offered us €2.15 fixed for twenty-four months."),
    (5.0, "me",   "Wenn der Preis wirklich der einzige Punkt ist, sollten wir über Laufzeit sprechen. Aber ist er das?"),
    (5.0, "them", "It's not only price. Last year we had two stock-outs with our current supplier. Production stood still for four days."),
    (5.0, "me",   "Then let's talk about guaranteed availability, not just cents per kilo."),
    (5.0, "them", "Send me the written proposal with the buffer-stock option. I'll share our forecast — realistically it's more like 150 tonnes in year one."),
    (4.0, "me",   "Deal. You'll have the proposal by Thursday, and I'd appreciate that Brenntag offer in writing."),
    (4.0, "them", "I'll send it over tomorrow. Let's reconnect next week."),
]

# Sweep states the mock LLM plays back, one per sweep, then holds the last.
_STAGES: list[dict] = [
    {  # after the price anchor
        "questions": [
            {"id": "q1", "rank": 1, "text": "What annual volume do you have in mind?", "why": "Qualify deal size before conceding anything on price.", "status": "open", "reason": None},
            {"id": "q2", "rank": 2, "text": "When you say “the market” — spot or delivered contract?", "why": "Their anchor may compare spot ex-works against delivered price.", "status": "open", "reason": None},
        ],
        "facts": [
            {"id": "f1", "claim": "€2.40/kg is well above market", "who": "them", "verdict": "misleading", "detail": "Spot ≈ €2.10 ex-works; delivered contract incl. REACH docs runs €2.30–2.55. Mixed price bases."},
        ],
        "numbers": [
            {"id": "n1", "label": "Their anchor", "value": "€2.40/kg", "who": "them", "flag": None},
        ],
        "commitments": [],
        "goals": [
            {"id": "g1", "text": "Close 24-month contract ≥ €2.30/kg delivered", "status": "open", "note": None},
            {"id": "g2", "text": "Trade term length before price", "status": "open", "note": None},
            {"id": "g3", "text": "Find their real pain: price vs supply security", "status": "open", "note": None},
        ],
        "note": None,
    },
    {  # volume answered unprompted; Brenntag claim lands
        "questions": [
            {"id": "q1", "rank": 3, "text": "What annual volume do you have in mind?", "why": "Qualify deal size.", "status": "answered", "reason": "Answered unprompted: 200 t/yr, quarterly, Hamburg."},
            {"id": "q2", "rank": 2, "text": "When you say “the market” — spot or delivered contract?", "why": "Their anchor may compare spot against delivered.", "status": "open", "reason": None},
            {"id": "q3", "rank": 1, "text": "Is price the concern this year — or supply security?", "why": "Find the real pain before trading term length for price.", "status": "open", "reason": None},
        ],
        "facts": [
            {"id": "f1", "claim": "€2.40/kg is well above market", "who": "them", "verdict": "misleading", "detail": "Spot ≈ €2.10 ex-works; delivered contract incl. REACH docs runs €2.30–2.55. Mixed price bases."},
            {"id": "f2", "claim": "Brenntag: €2.15 fixed, 24 months", "who": "them", "verdict": "unverifiable", "detail": "8–10% under any published 24-month fixed at this volume; no public source. Ask for it in writing."},
        ],
        "numbers": [
            {"id": "n1", "label": "Their anchor", "value": "€2.40/kg", "who": "them", "flag": None},
            {"id": "n2", "label": "Volume, cadence", "value": "200 t/yr · quarterly · Hamburg", "who": "them", "flag": None},
            {"id": "n3", "label": "Competing claim", "value": "€2.15/kg · 24 mo", "who": "them", "flag": None},
        ],
        "commitments": [],
        "goals": [
            {"id": "g1", "text": "Close 24-month contract ≥ €2.30/kg delivered", "status": "at-risk", "note": "€2.15 counter-anchor on the table."},
            {"id": "g2", "text": "Trade term length before price", "status": "open", "note": None},
            {"id": "g3", "text": "Find their real pain: price vs supply security", "status": "open", "note": None},
        ],
        "note": "Their €2.15 fixed/24 mo claim is below plausible range. Don't counter a number you haven't seen — ask for the written offer.",
    },
    {  # stock-outs revealed; pain identified
        "questions": [
            {"id": "q3", "rank": 4, "text": "Is price the concern this year — or supply security?", "why": "Find the real pain.", "status": "answered", "reason": "Answered: two stock-outs last year, four days of standstill."},
            {"id": "q4", "rank": 1, "text": "What did those four days of standstill cost you?", "why": "Let them price supply risk themselves — it reframes your €2.40.", "status": "open", "reason": None},
            {"id": "q5", "rank": 2, "text": "Would a guaranteed buffer stock in Hamburg change the calculus?", "why": "Trades on their pain, not on your price.", "status": "open", "reason": None},
            {"id": "q2", "rank": 3, "text": "When you say “the market” — spot or delivered contract?", "why": "Still open; low urgency now.", "status": "open", "reason": None},
        ],
        "facts": [
            {"id": "f1", "claim": "€2.40/kg is well above market", "who": "them", "verdict": "misleading", "detail": "Spot ≈ €2.10 ex-works; delivered contract runs €2.30–2.55."},
            {"id": "f2", "claim": "Brenntag: €2.15 fixed, 24 months", "who": "them", "verdict": "unverifiable", "detail": "Below published range; no source. Written offer requested?"},
        ],
        "numbers": [
            {"id": "n1", "label": "Their anchor", "value": "€2.40/kg", "who": "them", "flag": None},
            {"id": "n2", "label": "Volume, cadence", "value": "200 t/yr · quarterly · Hamburg", "who": "them", "flag": None},
            {"id": "n3", "label": "Competing claim", "value": "€2.15/kg · 24 mo", "who": "them", "flag": None},
            {"id": "n4", "label": "Their downtime", "value": "2 stock-outs · 4 days", "who": "them", "flag": None},
        ],
        "commitments": [],
        "goals": [
            {"id": "g1", "text": "Close 24-month contract ≥ €2.30/kg delivered", "status": "open", "note": "Leverage shifted: supply security beats price."},
            {"id": "g2", "text": "Trade term length before price", "status": "on-track", "note": "Laufzeit is on the table."},
            {"id": "g3", "text": "Find their real pain: price vs supply security", "status": "met", "note": "Supply security — 4 days standstill last year."},
        ],
        "note": None,
    },
    {  # closing: commitments made, volume revised down -> flag
        "questions": [
            {"id": "q4", "rank": 1, "text": "What did those four days of standstill cost you?", "why": "Quantifies the value of your buffer-stock option for the proposal.", "status": "open", "reason": None},
        ],
        "facts": [
            {"id": "f1", "claim": "€2.40/kg is well above market", "who": "them", "verdict": "misleading", "detail": "Mixed price bases."},
            {"id": "f2", "claim": "Brenntag: €2.15 fixed, 24 months", "who": "them", "verdict": "unverifiable", "detail": "They committed to sending it in writing tomorrow."},
        ],
        "numbers": [
            {"id": "n1", "label": "Their anchor", "value": "€2.40/kg", "who": "them", "flag": None},
            {"id": "n2", "label": "Volume, cadence", "value": "200 t/yr · quarterly · Hamburg", "who": "them", "flag": None},
            {"id": "n3", "label": "Competing claim", "value": "€2.15/kg · 24 mo", "who": "them", "flag": None},
            {"id": "n4", "label": "Their downtime", "value": "2 stock-outs · 4 days", "who": "them", "flag": None},
            {"id": "n5", "label": "Revised volume", "value": "150 t in year one", "who": "them", "flag": "was 200 t/yr earlier in this call"},
        ],
        "commitments": [
            {"id": "c1", "who": "me", "text": "Written proposal incl. buffer-stock option", "due": "Thursday"},
            {"id": "c2", "who": "them", "text": "Brenntag offer in writing", "due": "tomorrow"},
            {"id": "c3", "who": "them", "text": "Share volume forecast", "due": None},
        ],
        "goals": [
            {"id": "g1", "text": "Close 24-month contract ≥ €2.30/kg delivered", "status": "on-track", "note": "Proposal requested — anchor survived."},
            {"id": "g2", "text": "Trade term length before price", "status": "met", "note": "Buffer stock + term is the frame now."},
            {"id": "g3", "text": "Find their real pain: price vs supply security", "status": "met", "note": "Supply security."},
        ],
        "note": "They quietly cut volume 200→150 t while asking for the proposal. Price the buffer-stock option on 150 t — don't gift the 200 t price.",
    },
]

DEMO_DEBRIEF = """\
# Debrief
## What happened
- They anchored low (€2.40 "above market", Brenntag €2.15/24 mo — unverified) but revealed the real pain: two stock-outs, four days of standstill.
- Conversation reframed from price to guaranteed availability; they asked for a written proposal with a buffer-stock option.
- Volume quietly revised down: 200 t/yr → 150 t in year one.
## Goals
- **Close 24-mo contract ≥ €2.30/kg delivered** — on-track: anchor survived, proposal requested.
- **Trade term length before price** — met: buffer stock + term is the frame.
- **Find their real pain** — met: supply security, not price.
## Commitments
- **Ours:** written proposal incl. buffer-stock option — Thursday.
- **Theirs:** Brenntag offer in writing — tomorrow; volume forecast — open.
## Watch out
- Brenntag €2.15 fixed/24 mo remains unverified until the written offer arrives.
- Volume contradiction (200 → 150 t): price year one on 150 t.
## How you played it
- **Keep:** "Wenn der Preis wirklich der einzige Punkt ist…" — the direct challenge cracked the price framing and surfaced the stock-outs.
- **Keep:** You asked for the Brenntag offer in writing instead of countering an unseen number.
- **Change:** You answered the €2.40 anchor by justifying it (REACH, CoA) before knowing their volume — next time ask the qualifying question first, justify second.
- **Change:** The 200→150 t revision passed without comment; name contradictions in the room, gently, while they're fresh.
## Next call
- Their likely opening: the written Brenntag offer — real, expired, or hedged with conditions. Read the term-length and volume clauses before reacting.
- Have ready: cost-of-downtime math (4 days standstill × their line rate) to price the buffer-stock option in their numbers, not yours.
- Bring: proposal at 150 t with a stated path to the 200 t price — makes the volume cut **their** cost, not your concession.
- Trap to expect: "split the difference" between 2.15 and 2.40 — your floor is €2.30 delivered; trade term or buffer, not cents.
## Draft follow-up email
Subject: Proposal — supply agreement incl. buffer stock

Hallo [Name],

danke für das offene Gespräch. Wie besprochen erhalten Sie bis Donnerstag unser
Angebot über 150 t im ersten Jahr (Option auf 200 t), quartalsweise geliefert
nach Hamburg, inkl. garantiertem Pufferlager. Ich bin gespannt auf das
schriftliche Wettbewerbsangebot — danach fixieren wir die Konditionen.

Beste Grüße
Jan
"""


class MockLLM:
    """Plays the staged states back, one per sweep. Debrief prompts get the
    canned debrief. Interface-compatible with llm.LLM."""

    def __init__(self):
        self._i = 0

    def complete(self, system: str, user: str) -> str:
        if "post-call debrief" in system:
            return DEMO_DEBRIEF
        stage = _STAGES[min(self._i, len(_STAGES) - 1)]
        self._i += 1
        return json.dumps(stage, ensure_ascii=False)
