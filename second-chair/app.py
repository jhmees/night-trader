"""Second Chair as a desktop app: native window wrapping the local server.

  python app.py          # dev: same as server.py but in its own window
  ./build_app.sh         # mac: produces dist/Second Chair.app (double-clickable)

When frozen into a .app, working files (sessions/, deal_context.md) live in
~/SecondChair so the bundle stays read-only.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path


def wait_for_port(port: int, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def main() -> None:
    if getattr(sys, "frozen", False):          # running inside the .app bundle
        workdir = Path.home() / "SecondChair"
        workdir.mkdir(exist_ok=True)
        import os
        os.chdir(workdir)                       # sessions/, deal_context.md land here
        env = workdir / ".env"                  # Finder launches see no shell exports
        if env.exists():
            for line in env.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    import uvicorn
    import webview
    from server import app, CFG

    port = CFG["server"]["port"]
    threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning"),
        daemon=True,
    ).start()
    if not wait_for_port(port):
        raise SystemExit(f"server did not come up on port {port}")

    webview.create_window(
        "Second Chair", f"http://127.0.0.1:{port}",
        width=1240, height=820, min_size=(900, 600),
    )
    webview.start()                             # blocks until the window closes


if __name__ == "__main__":
    main()
