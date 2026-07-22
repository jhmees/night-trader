# 🎧 Second Chair — Silent Meeting Copilot

A local macOS app that listens to Teams calls, transcribes them locally, and —
on a hotkey — sends the recent transcript to an LLM that decides whether
anything deserves a short silent note ("stat card") shown only to you.
Like a second chair in a negotiation who slides you a piece of paper when
something matters, and stays quiet otherwise.

Personal toy, not commercial. Design doc lives in Notion
("Second Chair — Silent Meeting Copilot").

## v1 shape

```
Teams call audio (system output + mic)
        │  BlackHole loopback + default mic     [audio_capture.py]
        ▼
whisper, local                                  [transcriber.py]
        │  rolling transcript buffer (~5 min)   [buffer.py]
        ▼
Global hotkey ⌥⌘B "brief me"                    [main.py]
        │  last 60–90s + deal context + notes already shown
        ▼
LLM, provider-agnostic, tool-calling            [llm.py + brief.py]
        │  answers PASS (the modal outcome) or a ≤2-line note
        ▼
Overlay card (always-on-top) + sessions/{date}.jsonl   [overlay.py]
```

## Gate 0 — run this before building anything else

Whisper must survive: chemical names (e.g. 1,2-Propylendiamin), spoken CAS
numbers, German/English switching. Test on real Teams recordings:

```bash
python gate0.py ~/recordings/call1.m4a ~/recordings/call2.m4a --terms terms.txt
```

`terms.txt` = one term per line that MUST survive transcription (chemical
names, product names, client names). The report shows per-term survival and
all CAS-number-shaped strings found. If chemical nomenclature is mangled
beyond recognition → narrow scope to company/market enrichment only, or stop.

## Setup (Mac Mini, Apple Silicon)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install mlx-whisper        # Mac only: GPU (Metal) transcription backend
```

Audio routing (one-time):
1. Install [BlackHole 2ch](https://existential.audio/blackhole/)
2. Audio MIDI Setup → create Multi-Output Device = speakers + BlackHole
3. Set Teams/system output to the Multi-Output Device
4. `config.yaml` → `audio.system_device: "BlackHole 2ch"`

Expect one-time macOS permission prompts: Microphone, Input Monitoring
(hotkey). Grant them to your terminal app.

Note: faster-whisper (CTranslate2) has **no Metal backend** — on Apple
Silicon it is CPU-only. That's why the transcriber is backend-switchable:
`mlx` (GPU, Mac) vs `faster-whisper` (CPU, works everywhere — used for
dev/Gate 0 on Linux too).

## Run

```bash
python main.py                 # starts capture; press ⌥⌘B to get briefed
```

Every card is appended to `sessions/{date}.jsonl` — that log is the tuning
dataset for v2 (auto-trigger + weekly hit/noise marking).

## Consent

Only use on calls where you have asked for and received consent to
record/transcribe. The v2+ design gates the agent on hearing consent in the
first minute of audio (pre-gate audio transient, never persisted).
