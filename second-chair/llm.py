"""Provider-agnostic LLM adapter. One function: complete(system, user) -> text.

Vendor-independence rule: only hard requirement on a backend is tool calling
(v1 tool set = web search). Anthropic uses the server-side web_search tool;
ollama runs tool-free (local fallback, transcripts never leave the machine).
"""

from __future__ import annotations

import json
import os
import urllib.request


class LLM:
    def __init__(self, cfg: dict):
        c = cfg["llm"]
        self.provider = c["provider"]
        self.model = c["model"]
        self.max_tokens = c.get("max_tokens", 400)
        self.web_search = c.get("web_search", True)

    def complete(self, system: str, user: str) -> str:
        return getattr(self, f"_{self.provider}")(system, user)

    def _anthropic(self, system: str, user: str) -> str:
        import anthropic

        client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env
        tools = (
            [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
            if self.web_search
            else []
        )
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            tools=tools,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    def _openai(self, system: str, user: str) -> str:
        import openai

        client = openai.OpenAI()  # OPENAI_API_KEY from env
        resp = client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    def _ollama(self, system: str, user: str) -> str:
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        body = json.dumps(
            {
                "model": self.model,
                "system": system,
                "prompt": user,
                "stream": False,
            }
        ).encode()
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)["response"].strip()
