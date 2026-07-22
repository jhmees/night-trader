"""Gate 0 — Whisper reality check. Run this BEFORE building anything else.

Transcribes real Teams recordings and reports whether the terms that matter
(chemical names, spoken CAS numbers, German/English switching) survive.

  python gate0.py call1.m4a call2.m4a --terms terms.txt
  python gate0.py call1.m4a --model distil-large-v3 --backend faster-whisper

terms.txt: one must-survive term per line; '#' comments allowed.
Exit code 0 = all terms found in all files, 1 = something got mangled.

Verdict rule from the design doc: if chemical nomenclature is mangled beyond
recognition, narrow scope to company/market enrichment only — or stop.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

from transcriber import Transcriber

CAS_RE = re.compile(r"\b\d{2,7}-\d{2}-\d\b")


def load_terms(path: str) -> list[str]:
    lines = Path(path).read_text().splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


def check_term(term: str, transcript: str) -> tuple[str, str]:
    """Returns (status, evidence): exact | fuzzy | MISSING."""
    low, term_low = transcript.lower(), term.lower()
    if term_low in low:
        return "exact", term
    # fuzzy: best-matching window of the same word-length as the term
    words = transcript.split()
    n = max(1, len(term.split()))
    best_score, best_snippet = 0.0, ""
    for i in range(max(1, len(words) - n + 1)):
        snippet = " ".join(words[i : i + n])
        score = difflib.SequenceMatcher(None, term_low, snippet.lower()).ratio()
        if score > best_score:
            best_score, best_snippet = score, snippet
    if best_score >= 0.75:
        return "fuzzy", f"{best_snippet!r} ({best_score:.0%})"
    return "MISSING", f"best guess {best_snippet!r} ({best_score:.0%})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("recordings", nargs="+", help="audio files (wav/m4a/mp3/...)")
    ap.add_argument("--terms", help="file with must-survive terms, one per line")
    ap.add_argument("--backend", default="faster-whisper",
                    choices=["faster-whisper", "mlx"])
    ap.add_argument("--model", default="large-v3-turbo")
    ap.add_argument("--transcript-out", help="dir to dump full transcripts")
    args = ap.parse_args()

    print(f"Loading {args.backend} / {args.model} …", flush=True)
    tr = Transcriber(args.backend, args.model, language=None)
    terms = load_terms(args.terms) if args.terms else []
    failed = False

    for rec in args.recordings:
        print(f"\n=== {rec} ===", flush=True)
        segments = tr.transcribe(rec)
        transcript = "\n".join(s.text for s in segments)
        print(f"{len(segments)} segments, {len(transcript.split())} words")

        if args.transcript_out:
            out = Path(args.transcript_out)
            out.mkdir(parents=True, exist_ok=True)
            (out / (Path(rec).stem + ".txt")).write_text(transcript)

        cas_hits = sorted(set(CAS_RE.findall(transcript)))
        print(f"CAS-shaped strings found: {cas_hits or 'none'}")

        for term in terms:
            status, evidence = check_term(term, transcript)
            mark = {"exact": "✓", "fuzzy": "~", "MISSING": "✗"}[status]
            print(f"  {mark} {term:<40} {status:<8} {evidence}")
            if status == "MISSING":
                failed = True

        if not terms:
            print("(no --terms file: eyeball the transcript yourself)")
            print(transcript[:2000])

    print("\nGate 0 verdict:", "FAIL — narrow scope or stop" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
