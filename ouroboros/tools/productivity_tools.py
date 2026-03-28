"""
Productivity tools — documents, cost tracking, token optimization, daily rhythm, agent diagnostics.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
from typing import List

from ouroboros.tools.registry import ToolContext, ToolEntry


def _read_office(ctx: ToolContext, path: str) -> str:
    """Read Excel (.xlsx) or Word (.docx) files."""
    ext = pathlib.Path(path).suffix.lower()

    if ext == ".xlsx":
        try:
            import openpyxl
        except ImportError:
            try:
                import subprocess, sys
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "openpyxl"])
                import openpyxl
            except Exception:
                return json.dumps({"error": "Install openpyxl: pip install openpyxl"})
        try:
            wb = openpyxl.load_workbook(path, read_only=True)
            sheets = {}
            for name in wb.sheetnames:
                ws = wb[name]
                rows = []
                for row in ws.iter_rows(max_row=100, values_only=True):
                    rows.append([str(c) if c is not None else "" for c in row])
                sheets[name] = rows
            return json.dumps({"type": "xlsx", "sheets": sheets}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    elif ext == ".docx":
        try:
            from docx import Document
        except ImportError:
            try:
                import subprocess, sys
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "python-docx"])
                from docx import Document
            except Exception:
                return json.dumps({"error": "Install python-docx: pip install python-docx"})
        try:
            doc = Document(path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return json.dumps({"type": "docx", "paragraphs": paragraphs[:200],
                               "total_paragraphs": len(paragraphs)}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return json.dumps({"error": f"Unsupported format: {ext}. Use .xlsx or .docx"})


def _cost_report(ctx: ToolContext) -> str:
    """Generate API cost report from state and logs."""
    try:
        from supervisor.state import load_state
        st = load_state()
        spent = float(st.get("spent_usd", 0))
        total = float(st.get("total_budget", 10))
        remaining = total - spent

        # Count requests from router log
        router_log = pathlib.Path("/tmp/model_router.log")
        request_count = 0
        provider_counts = {}
        if router_log.exists():
            for line in router_log.read_text().split("\n"):
                if "success via" in line:
                    request_count += 1
                    parts = line.split("success via ")
                    if len(parts) > 1:
                        provider = parts[1].split("/")[0]
                        provider_counts[provider] = provider_counts.get(provider, 0) + 1

        return json.dumps({
            "budget_usd": total,
            "spent_usd": round(spent, 4),
            "remaining_usd": round(remaining, 4),
            "pct_used": round(spent / total * 100, 1) if total else 0,
            "total_requests": request_count,
            "by_provider": provider_counts,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _daily_rhythm(ctx: ToolContext) -> str:
    """Show daily rhythm — what happened today, what's planned."""
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.strftime("%Y-%m-%d")

    # Today's chat activity
    chat_path = pathlib.Path(__file__).parent.parent.parent / "local_data" / "logs" / "chat.jsonl"
    today_msgs = 0
    first_msg = ""
    last_msg = ""
    if chat_path.exists():
        for line in chat_path.read_text().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("ts", "").startswith(today):
                    today_msgs += 1
                    if not first_msg:
                        first_msg = entry.get("ts", "")[:19]
                    last_msg = entry.get("ts", "")[:19]
            except Exception:
                continue

    # Memory stats
    try:
        from ouroboros.vector_memory import get_memory
        stats = get_memory().stats()
    except Exception:
        stats = {}

    # Scratchpad
    sp_path = pathlib.Path(__file__).parent.parent.parent / "local_data" / "memory" / "scratchpad.md"
    scratchpad = sp_path.read_text(encoding="utf-8")[:500] if sp_path.exists() else ""

    return json.dumps({
        "date": today,
        "messages_today": today_msgs,
        "first_message": first_msg,
        "last_message": last_msg,
        "memory_stats": stats,
        "scratchpad_preview": scratchpad,
    }, ensure_ascii=False, indent=2)


def _agent_doctor(ctx: ToolContext) -> str:
    """Diagnose agent health — check all services and components."""
    import requests as _req
    checks = {}

    # Model Router
    try:
        r = _req.get("http://localhost:4000/health", timeout=3)
        checks["model_router"] = "✅ ok" if r.status_code == 200 else f"⚠️ {r.status_code}"
    except Exception:
        checks["model_router"] = "❌ down"

    # Gemini proxy
    try:
        r = _req.get("http://localhost:8888/v1/models", timeout=3)
        checks["gemini_proxy"] = "✅ ok" if r.status_code in (200, 401) else f"⚠️ {r.status_code}"
    except Exception:
        checks["gemini_proxy"] = "❌ down"

    # OpenAI proxy
    try:
        r = _req.get("http://localhost:8889/health", timeout=3)
        checks["openai_proxy"] = "✅ ok" if r.status_code == 200 else f"⚠️ {r.status_code}"
    except Exception:
        checks["openai_proxy"] = "❌ down"

    # Lightpanda
    try:
        r = _req.get("http://127.0.0.1:9222/json/version", timeout=3)
        checks["lightpanda"] = "✅ ok" if r.status_code == 200 else f"⚠️ {r.status_code}"
    except Exception:
        checks["lightpanda"] = "❌ down"

    # Ollama (local)
    try:
        r = _req.get("http://localhost:11434/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        checks["ollama_local"] = f"✅ ok ({len(models)} models)"
    except Exception:
        checks["ollama_local"] = "❌ down"

    # Spark
    try:
        r = _req.get("http://192.168.1.121:11434/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        checks["spark_ollama"] = f"✅ ok ({len(models)} models)"
    except Exception:
        checks["spark_ollama"] = "❌ unreachable"

    # ChromaDB
    try:
        from ouroboros.vector_memory import get_memory
        stats = get_memory().stats()
        checks["chromadb"] = f"✅ ok ({stats.get('total', 0)} memories)"
    except Exception:
        checks["chromadb"] = "❌ error"

    # Disk
    import shutil
    usage = shutil.disk_usage("/")
    free_gb = usage.free / (1024**3)
    checks["disk"] = f"{'✅' if free_gb > 10 else '⚠️'} {free_gb:.0f} GB free"

    all_ok = all("✅" in v for v in checks.values())
    return json.dumps({"status": "healthy" if all_ok else "issues_found", "checks": checks}, indent=2)


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("read_office", {
            "name": "read_office",
            "description": "Read Excel (.xlsx) or Word (.docx) files. Returns structured content.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Path to .xlsx or .docx file"},
            }, "required": ["path"]},
        }, _read_office),
        ToolEntry("cost_report", {
            "name": "cost_report",
            "description": "API cost report — budget, spent, remaining, requests by provider.",
            "parameters": {"type": "object", "properties": {}},
        }, _cost_report),
        ToolEntry("daily_rhythm", {
            "name": "daily_rhythm",
            "description": "Daily rhythm — today's activity, messages, memory stats, scratchpad.",
            "parameters": {"type": "object", "properties": {}},
        }, _daily_rhythm),
        ToolEntry("agent_doctor", {
            "name": "agent_doctor",
            "description": "Diagnose agent health — check all services (router, proxies, Spark, ChromaDB, disk).",
            "parameters": {"type": "object", "properties": {}},
        }, _agent_doctor),
    ]
