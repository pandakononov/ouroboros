"""Web search + URL reading tools."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry


def _web_search(ctx: ToolContext, query: str) -> str:
    """Search the web. Tries Exa → Gemini Search → GPT-5.4 fallback."""
    import requests as _req

    # Method 1: DuckDuckGo (free, no API key, no rate limits)
    try:
        from html.parser import HTMLParser
        ddg_url = f"https://html.duckduckgo.com/html/?q={_req.utils.quote(query)}"
        r = _req.get(ddg_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        if r.status_code == 200:
            # Parse snippets from DDG HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for result_div in soup.select(".result__body")[:5]:
                title_el = result_div.select_one(".result__title")
                snippet_el = result_div.select_one(".result__snippet")
                link_el = result_div.select_one(".result__url")
                title = title_el.get_text(strip=True) if title_el else ""
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                link = link_el.get_text(strip=True) if link_el else ""
                if snippet:
                    results.append(f"**{title}** ({link})\n{snippet}")
            if results:
                text = "\n\n".join(results)
                return json.dumps({"answer": text, "source": "duckduckgo", "results": len(results)},
                                  ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Method 2: Gemini with Google Search grounding
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

    # Method 3: GPT-5.4 via Codex proxy
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


def _read_url(ctx: ToolContext, url: str, max_chars: int = 10000) -> str:
    """Read and extract text content from a URL via Lightpanda or direct fetch."""
    import requests as _req

    # Method 1: Lightpanda browser (JS-capable)
    cdp_url = os.environ.get("BROWSER_CDP_URL", "")
    if cdp_url:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.connect_over_cdp(cdp_url)
                page = browser.new_page()
                page.goto(url, timeout=15000)
                text = page.inner_text("body")
                page.close()
                if text:
                    return json.dumps({
                        "url": url,
                        "content": text[:max_chars],
                        "source": "lightpanda",
                        "truncated": len(text) > max_chars,
                    }, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # Method 2: Direct HTTP fetch (no JS)
    try:
        from bs4 import BeautifulSoup
        r = _req.get(url, timeout=10, headers={"User-Agent": "Ouroboros/1.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return json.dumps({
            "url": url,
            "content": text[:max_chars],
            "source": "http_fetch",
            "truncated": len(text) > max_chars,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        pass

    # Method 3: Raw fetch
    try:
        r = _req.get(url, timeout=10, headers={"User-Agent": "Ouroboros/1.0"})
        text = r.text[:max_chars]
        return json.dumps({
            "url": url,
            "content": text,
            "source": "raw_fetch",
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Cannot read URL: {e}"}, ensure_ascii=False)


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("web_search", {
            "name": "web_search",
            "description": (
                "Search the web for current information. Uses Exa neural search (free), "
                "Gemini Google Search, and GPT-5.4 as fallbacks. "
                "Returns structured answer with source attribution."
            ),
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Search query"},
            }, "required": ["query"]},
        }, _web_search),

        ToolEntry("read_url", {
            "name": "read_url",
            "description": (
                "Read and extract text content from a URL. "
                "Uses Lightpanda browser (JS-capable) with HTTP fetch fallback. "
                "Returns cleaned text content."
            ),
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "description": "URL to read"},
                "max_chars": {"type": "integer", "description": "Max chars to return (default 10000)"},
            }, "required": ["url"]},
        }, _read_url),
    ]
