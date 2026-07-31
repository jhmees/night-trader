#!/bin/bash
# Build Second Chair.app (run ON the Mac, from the second-chair directory).
#   bash build_app.sh
# Result: dist/Second Chair.app — drag it to /Applications like any other app.
# Built locally, so Gatekeeper does not quarantine it. Mic/permission prompts
# will name "Second Chair" instead of your terminal.
set -euo pipefail

if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q -r requirements.txt pywebview pyinstaller
pip install -q mlx-whisper || echo "mlx-whisper skipped (not Apple Silicon?)"

pyinstaller --noconfirm --windowed --name "Second Chair" \
  --add-data "static:static" \
  --add-data "config.yaml:." \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  app.py

echo
echo "Done → dist/Second Chair.app"
echo "Note: the sweeps need ANTHROPIC_API_KEY. Launched from Finder, apps don't"
echo "see your shell exports — put the key in ~/SecondChair/.env (KEY=value) or"
echo "run once via: open dist/Second\\ Chair.app --env ANTHROPIC_API_KEY=sk-..."
