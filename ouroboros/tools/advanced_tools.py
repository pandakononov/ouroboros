"""
Advanced tools — self-improvement, capability tracking, deep research, summarize, PDF.

Tools: learn_from_error, learn_from_correction, capability_check, deep_research, summarize_text, read_pdf.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry

LEARNINGS_DIR = pathlib.Path(__file__).parent.parent.parent / "local_data" / "memory" / "learnings"


def _ensure_learnings_dir():
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    for f in ("ERRORS.md", "LEARNINGS.md", "FEATURE_REQUESTS.md", "CAPABILITIES.md"):
        path = LEARNINGS_DIR / f
        if not path.exists():
            path.write_text(f"# {f.replace('.md', '')}\n\n", encoding="utf-8")


# ── Self-Improving Agent ──────────────────────────────────────────────

def _learn_from_error(ctx: ToolContext, error: str, context: str = "", fix: str = "") -> str:
    """Log an error for future avoidance."""
    _ensure_learnings_dir()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()[:19]
    entry = f"\n## [{now}] Error\n\n**Error:** {error}\n"
    if context:
        entry += f"**Context:** {context}\n"
    if fix:
        entry += f"**Fix:** {fix}\n"
    entry += f"**Status:** logged\n"

    with open(LEARNINGS_DIR / "ERRORS.md", "a", encoding="utf-8") as f:
        f.write(entry)

    # Also store in vector memory for semantic search
    try:
        from ouroboros.vector_memory import get_memory
        mem = get_memory()
        mem.remember(f"Error: {error}. Fix: {fix}" if fix else f"Error: {error}",
                     store="procedural", metadata={"type": "error", "has_fix": str(bool(fix))})
    except Exception:
        pass

    return json.dumps({"status": "logged", "file": "ERRORS.md"})


def _learn_from_correction(ctx: ToolContext, wrong: str, correct: str,
                            category: str = "correction") -> str:
    """Log a correction or learning for continuous improvement.

    Categories: correction, knowledge_gap, best_practice, behavioral.
    """
    _ensure_learnings_dir()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()[:19]
    entry = f"\n## [{now}] {category}\n\n"
    entry += f"**Wrong:** {wrong}\n"
    entry += f"**Correct:** {correct}\n"
    entry += f"**Category:** {category}\n"

    with open(LEARNINGS_DIR / "LEARNINGS.md", "a", encoding="utf-8") as f:
        f.write(entry)

    # Store in vector memory
    try:
        from ouroboros.vector_memory import get_memory
        mem = get_memory()
        mem.remember(f"Learning [{category}]: was '{wrong}', should be '{correct}'",
                     store="procedural", metadata={"type": "learning", "category": category})
    except Exception:
        pass

    # Promote to SOUL.md if behavioral
    if category == "behavioral":
        soul_path = pathlib.Path(__file__).parent.parent.parent / "local_data" / "memory" / "SOUL.md"
        if soul_path.exists():
            with open(soul_path, "a", encoding="utf-8") as f:
                f.write(f"\n- Learned: {correct} (not: {wrong})\n")

    return json.dumps({"status": "logged", "category": category,
                        "promoted_to_soul": category == "behavioral"})


# ── Capability Evolver ────────────────────────────────────────────────

def _capability_check(ctx: ToolContext, action: str = "status") -> str:
    """Track and evolve capabilities.

    Actions:
    - status: list current capabilities and gaps
    - add: register a new capability
    - gap: register a missing capability / feature request
    - review: analyze errors and learnings for improvement opportunities
    """
    _ensure_learnings_dir()
    caps_path = LEARNINGS_DIR / "CAPABILITIES.md"

    if action == "status":
        return json.dumps({"capabilities": caps_path.read_text(encoding="utf-8")})

    if action == "review":
        # Analyze errors and learnings
        errors = (LEARNINGS_DIR / "ERRORS.md").read_text(encoding="utf-8") if (LEARNINGS_DIR / "ERRORS.md").exists() else ""
        learnings = (LEARNINGS_DIR / "LEARNINGS.md").read_text(encoding="utf-8") if (LEARNINGS_DIR / "LEARNINGS.md").exists() else ""
        error_count = errors.count("## [")
        learning_count = learnings.count("## [")

        return json.dumps({
            "errors_logged": error_count,
            "learnings_logged": learning_count,
            "last_errors": errors[-1000:] if errors else "(none)",
            "last_learnings": learnings[-1000:] if learnings else "(none)",
            "instruction": "Analyze patterns. What keeps failing? What have you learned? "
                           "Update CAPABILITIES.md with new skills and gaps.",
        }, ensure_ascii=False, indent=2)

    return json.dumps({"error": f"Unknown action: {action}"})


def _capability_update(ctx: ToolContext, text: str, is_gap: bool = False) -> str:
    """Add a capability or register a gap."""
    _ensure_learnings_dir()
    caps_path = LEARNINGS_DIR / "CAPABILITIES.md"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()[:19]
    prefix = "❌ GAP" if is_gap else "✅ CAN"

    with open(caps_path, "a", encoding="utf-8") as f:
        f.write(f"\n- [{now}] {prefix}: {text}\n")

    if is_gap:
        with open(LEARNINGS_DIR / "FEATURE_REQUESTS.md", "a", encoding="utf-8") as f:
            f.write(f"\n## [{now}] Feature Request\n\n{text}\n")

    return json.dumps({"status": "updated", "type": "gap" if is_gap else "capability"})


# ── Deep Research ─────────────────────────────────────────────────────

def _deep_research(ctx: ToolContext, topic: str, depth: str = "standard") -> str:
    """Multi-step deep research on a topic.

    Depth: quick (3 searches), standard (5), thorough (10).
    Uses web_search + read_url iteratively, building knowledge.
    """
    import requests as _req
    from ouroboros.tools.search import _web_search, _read_url

    max_steps = {"quick": 3, "standard": 5, "thorough": 10}.get(depth, 5)
    findings = []
    urls_read = set()

    # Step 1: Initial search
    search_result = json.loads(_web_search(ctx, topic))
    findings.append({"step": 1, "type": "search", "query": topic,
                     "result": search_result.get("answer", "")[:1000]})

    # Step 2-N: Follow up on search results, read URLs, refine
    for step in range(2, max_steps + 1):
        # Extract URLs from previous findings
        prev = findings[-1].get("result", "")

        # Try to find and read a URL
        import re
        urls = re.findall(r'https?://[^\s\)\"]+', prev)
        url_read = False
        for url in urls[:2]:
            if url in urls_read:
                continue
            urls_read.add(url)
            try:
                content = json.loads(_read_url(ctx, url, max_chars=5000))
                findings.append({"step": step, "type": "read_url", "url": url,
                                 "result": content.get("content", "")[:1000]})
                url_read = True
                break
            except Exception:
                continue

        # If no URL to read, do a follow-up search
        if not url_read:
            # Generate follow-up query based on findings so far
            follow_up = f"{topic} details specifics"
            if step > 3:
                follow_up = f"{topic} advanced analysis"
            search_result = json.loads(_web_search(ctx, follow_up))
            findings.append({"step": step, "type": "search", "query": follow_up,
                             "result": search_result.get("answer", "")[:1000]})

    return json.dumps({
        "topic": topic,
        "depth": depth,
        "steps": len(findings),
        "findings": findings,
        "instruction": "Synthesize these findings into a comprehensive answer. "
                       "Cite sources where possible.",
    }, ensure_ascii=False, indent=2)


# ── Summarize ─────────────────────────────────────────────────────────

def _summarize_text(ctx: ToolContext, text: str, style: str = "bullets",
                     max_length: int = 500) -> str:
    """Summarize text using LLM.

    Styles: bullets, paragraph, key_points, tldr.
    """
    style_prompts = {
        "bullets": "Summarize in bullet points. Russian if input is Russian.",
        "paragraph": "Summarize in 2-3 paragraphs. Russian if input is Russian.",
        "key_points": "Extract 3-5 key points. Russian if input is Russian.",
        "tldr": "TL;DR in 1-2 sentences. Russian if input is Russian.",
    }
    prompt = style_prompts.get(style, style_prompts["bullets"])

    try:
        from ouroboros.llm import LLMClient
        light_model = os.environ.get("OUROBOROS_MODEL_LIGHT", "light")
        client = LLMClient()
        resp, usage = client.chat(
            messages=[{"role": "user", "content": f"{prompt}\n\n{text[:15000]}"}],
            model=light_model,
            reasoning_effort="low",
            max_tokens=max_length,
        )
        summary = resp.get("content", "")
        return json.dumps({"summary": summary, "style": style,
                            "input_chars": len(text), "output_chars": len(summary)},
                           ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Summarization failed: {e}"})


# ── PDF Reader ────────────────────────────────────────────────────────

def _read_pdf(ctx: ToolContext, path: str, pages: str = "") -> str:
    """Read text from a PDF file.

    Args:
        path: file path to PDF
        pages: page range, e.g. "1-5" or "3" (empty = all)
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            import subprocess, sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pypdf"])
            from pypdf import PdfReader
        except Exception:
            return json.dumps({"error": "pypdf not available. Install with: pip install pypdf"})

    try:
        reader = PdfReader(path)
        total_pages = len(reader.pages)

        # Parse page range
        if pages:
            if "-" in pages:
                start, end = pages.split("-", 1)
                page_nums = range(int(start) - 1, min(int(end), total_pages))
            else:
                page_nums = [int(pages) - 1]
        else:
            page_nums = range(total_pages)

        text_parts = []
        for i in page_nums:
            if 0 <= i < total_pages:
                page_text = reader.pages[i].extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i+1} ---\n{page_text}")

        text = "\n\n".join(text_parts)

        return json.dumps({
            "path": path,
            "total_pages": total_pages,
            "pages_read": len(list(page_nums)),
            "content": text[:20000],
            "truncated": len(text) > 20000,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Failed to read PDF: {e}"})


# ── Tool Registration ─────────────────────────────────────────────────

def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("learn_from_error", {
            "name": "learn_from_error",
            "description": (
                "Log an error or failure for future avoidance. "
                "Stored in learnings/ERRORS.md and vector memory. "
                "Use when a command fails, API errors, or unexpected behavior occurs."
            ),
            "parameters": {"type": "object", "properties": {
                "error": {"type": "string", "description": "What went wrong"},
                "context": {"type": "string", "description": "What you were trying to do"},
                "fix": {"type": "string", "description": "How it was fixed (if known)"},
            }, "required": ["error"]},
        }, _learn_from_error),

        ToolEntry("learn_from_correction", {
            "name": "learn_from_correction",
            "description": (
                "Log a correction or learning. Categories: correction (user corrected you), "
                "knowledge_gap (info was wrong), best_practice (found better way), "
                "behavioral (personality/style fix → promoted to SOUL.md). "
                "Philosophy: 'Correct once, never again.'"
            ),
            "parameters": {"type": "object", "properties": {
                "wrong": {"type": "string", "description": "What was wrong"},
                "correct": {"type": "string", "description": "What is correct"},
                "category": {"type": "string", "enum": ["correction", "knowledge_gap", "best_practice", "behavioral"]},
            }, "required": ["wrong", "correct"]},
        }, _learn_from_correction),

        ToolEntry("capability_check", {
            "name": "capability_check",
            "description": (
                "Track capabilities and gaps. Actions: "
                "'status' (list capabilities), 'review' (analyze errors/learnings for patterns)."
            ),
            "parameters": {"type": "object", "properties": {
                "action": {"type": "string", "enum": ["status", "review"]},
            }},
        }, _capability_check),

        ToolEntry("capability_update", {
            "name": "capability_update",
            "description": "Register a new capability or gap. Gaps are also logged as feature requests.",
            "parameters": {"type": "object", "properties": {
                "text": {"type": "string", "description": "Capability or gap description"},
                "is_gap": {"type": "boolean", "description": "True if this is a missing capability"},
            }, "required": ["text"]},
        }, _capability_update),

        ToolEntry("deep_research", {
            "name": "deep_research",
            "description": (
                "Multi-step deep research on a topic. Iteratively searches and reads URLs. "
                "Depth: 'quick' (3 steps), 'standard' (5), 'thorough' (10). "
                "Returns structured findings for synthesis."
            ),
            "parameters": {"type": "object", "properties": {
                "topic": {"type": "string", "description": "Research topic"},
                "depth": {"type": "string", "enum": ["quick", "standard", "thorough"]},
            }, "required": ["topic"]},
        }, _deep_research),

        ToolEntry("summarize_text", {
            "name": "summarize_text",
            "description": (
                "Summarize text using LLM. Styles: 'bullets', 'paragraph', 'key_points', 'tldr'."
            ),
            "parameters": {"type": "object", "properties": {
                "text": {"type": "string", "description": "Text to summarize"},
                "style": {"type": "string", "enum": ["bullets", "paragraph", "key_points", "tldr"]},
                "max_length": {"type": "integer", "description": "Max output tokens"},
            }, "required": ["text"]},
        }, _summarize_text),

        ToolEntry("read_pdf", {
            "name": "read_pdf",
            "description": (
                "Read text from a PDF file. Supports page ranges (e.g. '1-5'). "
                "Returns extracted text content."
            ),
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Path to PDF file"},
                "pages": {"type": "string", "description": "Page range, e.g. '1-5' or '3' (empty=all)"},
            }, "required": ["path"]},
        }, _read_pdf),
    ]
