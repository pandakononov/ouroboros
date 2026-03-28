"""
Research tools — arxiv, news, YouTube, video transcripts.
"""

from __future__ import annotations

import json
import os
import re
from typing import List

from ouroboros.tools.registry import ToolContext, ToolEntry


def _arxiv_search(ctx: ToolContext, query: str, max_results: int = 5) -> str:
    """Search arXiv for papers."""
    import requests
    url = f"http://export.arxiv.org/api/query?search_query=all:{requests.utils.quote(query)}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        # Parse Atom XML
        from xml.etree import ElementTree as ET
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.text)
        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
            summary = entry.findtext("atom:summary", "", ns).strip()[:300]
            link = ""
            for l in entry.findall("atom:link", ns):
                if l.get("type") == "text/html":
                    link = l.get("href", "")
                    break
            published = entry.findtext("atom:published", "", ns)[:10]
            authors = [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)]
            papers.append({
                "title": title, "authors": ", ".join(authors[:3]),
                "date": published, "url": link, "summary": summary,
            })
        return json.dumps({"papers": papers, "count": len(papers)}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _news_search(ctx: ToolContext, topic: str = "AI", lang: str = "ru") -> str:
    """Search recent news via DuckDuckGo News."""
    import requests
    from bs4 import BeautifulSoup
    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(topic + ' news')}&df=d"
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for div in soup.select(".result__body")[:7]:
            title = div.select_one(".result__title")
            snippet = div.select_one(".result__snippet")
            if snippet:
                results.append({
                    "title": title.get_text(strip=True) if title else "",
                    "snippet": snippet.get_text(strip=True)[:200],
                })
        return json.dumps({"topic": topic, "results": results}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _youtube_transcript(ctx: ToolContext, url: str) -> str:
    """Download transcript from a YouTube video."""
    # Extract video ID
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    if not match:
        return json.dumps({"error": "Cannot extract YouTube video ID from URL"})
    video_id = match.group(1)

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["ru", "en"])
        text = " ".join(entry["text"] for entry in transcript)
        return json.dumps({
            "video_id": video_id, "url": url,
            "transcript": text[:15000],
            "truncated": len(text) > 15000,
            "duration_segments": len(transcript),
        }, ensure_ascii=False, indent=2)
    except ImportError:
        # Try yt-dlp fallback
        try:
            import subprocess, sys
            result = subprocess.run(
                ["yt-dlp", "--write-auto-sub", "--sub-lang", "ru,en", "--skip-download",
                 "--sub-format", "txt", "-o", "/tmp/yt_%(id)s", url],
                capture_output=True, text=True, timeout=30,
            )
            # Read subtitle file
            import glob
            files = glob.glob(f"/tmp/yt_{video_id}*")
            if files:
                with open(files[0]) as f:
                    text = f.read()
                return json.dumps({"video_id": video_id, "transcript": text[:15000]}, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return json.dumps({"error": "Install youtube-transcript-api: pip install youtube-transcript-api"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("arxiv_search", {
            "name": "arxiv_search",
            "description": "Search arXiv for academic papers. Returns titles, authors, dates, abstracts.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "max_results": {"type": "integer"},
            }, "required": ["query"]},
        }, _arxiv_search),

        ToolEntry("news_search", {
            "name": "news_search",
            "description": "Search recent news on a topic via DuckDuckGo. Default topic: AI.",
            "parameters": {"type": "object", "properties": {
                "topic": {"type": "string"}, "lang": {"type": "string"},
            }},
        }, _news_search),

        ToolEntry("youtube_transcript", {
            "name": "youtube_transcript",
            "description": "Download transcript/subtitles from a YouTube video URL.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "description": "YouTube video URL"},
            }, "required": ["url"]},
        }, _youtube_transcript),
    ]
