"""Web search tool."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry


def _web_search(ctx: ToolContext, query: str) -> str:
    # Try Gemini with Google Search grounding first, then browse_page fallback
    import requests as _req

    # Method 1: Gemini with search grounding (via geminicli2api proxy)
    gemini_url = os.environ.get("GEMINI_SEARCH_URL", "http://localhost:8888/v1/chat/completions")
    gemini_key = os.environ.get("GEMINI_SEARCH_KEY", "ouroboros123")
    try:
        r = _req.post(gemini_url, timeout=30,
            headers={"Authorization": f"Bearer {gemini_key}", "Content-Type": "application/json"},
            json={
                "model": "gemini-2.5-flash-search",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 2000,
            })
        if r.status_code == 200:
            data = r.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if text:
                return json.dumps({"answer": text, "source": "gemini-search"}, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Method 2: OpenAI via Codex proxy
    openai_url = os.environ.get("OPENAI_SEARCH_URL", "http://localhost:8889/v1/chat/completions")
    openai_key = os.environ.get("OPENAI_SEARCH_KEY", "sk-openai-proxy")
    try:
        r = _req.post(openai_url, timeout=60,
            headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-5.4",
                "messages": [{"role": "user", "content": f"Search the web and answer: {query}"}],
                "max_tokens": 2000,
            })
        if r.status_code == 200:
            data = r.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if text:
                return json.dumps({"answer": text, "source": "gpt-5.4"}, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return json.dumps({"error": "Web search unavailable (all methods failed)."}, ensure_ascii=False)


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("web_search", {
            "name": "web_search",
            "description": "Search the web via OpenAI Responses API. Returns JSON with answer + sources.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
            }, "required": ["query"]},
        }, _web_search),
    ]
