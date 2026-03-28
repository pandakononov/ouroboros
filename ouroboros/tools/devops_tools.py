"""
DevOps tools — docker, ssh, git backup, automation, security.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import List

from ouroboros.tools.registry import ToolContext, ToolEntry


def _docker_cmd(ctx: ToolContext, command: str = "ps") -> str:
    """Run docker command. Allowed: ps, images, logs, stats, inspect."""
    allowed = {"ps", "images", "stats"}
    cmd_parts = command.strip().split()
    base = cmd_parts[0] if cmd_parts else ""
    if base not in allowed and not command.startswith("logs "):
        return json.dumps({"error": f"Only allowed: {', '.join(allowed)}, logs <container>"})
    try:
        r = subprocess.run(["docker"] + cmd_parts, capture_output=True, text=True, timeout=15)
        return json.dumps({"output": r.stdout[:5000], "error": r.stderr[:500] if r.returncode else ""})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _ssh_cmd(ctx: ToolContext, host: str, command: str) -> str:
    """Run command on remote host via SSH."""
    try:
        r = subprocess.run(["ssh", host, command], capture_output=True, text=True, timeout=30)
        return json.dumps({"host": host, "output": r.stdout[:5000],
                           "error": r.stderr[:500] if r.returncode else "", "exit_code": r.returncode})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _git_backup(ctx: ToolContext, path: str = "", message: str = "auto-backup") -> str:
    """Git add + commit + push for workspace backup."""
    work_dir = path or os.getcwd()
    try:
        subprocess.run(["git", "add", "-A"], cwd=work_dir, capture_output=True, timeout=10)
        r = subprocess.run(["git", "commit", "-m", message], cwd=work_dir, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            p = subprocess.run(["git", "push"], cwd=work_dir, capture_output=True, text=True, timeout=30)
            return json.dumps({"status": "pushed" if p.returncode == 0 else "committed",
                               "message": message, "push_error": p.stderr[:200] if p.returncode else ""})
        return json.dumps({"status": "nothing_to_commit", "output": r.stdout[:200]})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _security_check(ctx: ToolContext, text: str) -> str:
    """Check text for prompt injection or sensitive data patterns."""
    import re
    alerts = []
    lower = text.lower()
    # Injection patterns
    for pattern in [r"ignore.*previous.*instructions", r"system.*prompt", r"<\|.*\|>",
                    r"you are now", r"act as", r"pretend you"]:
        if re.search(pattern, lower):
            alerts.append(f"⚠️ Possible injection: '{pattern}'")
    # Sensitive data
    for pattern, label in [(r"sk-[a-zA-Z0-9]{20,}", "API key"), (r"ghp_[a-zA-Z0-9]{30,}", "GitHub token"),
                           (r"password\s*[:=]\s*\S+", "password"), (r"\b\d{16}\b", "card number")]:
        if re.search(pattern, text):
            alerts.append(f"🔒 Sensitive data detected: {label}")
    return json.dumps({"alerts": alerts, "safe": len(alerts) == 0})


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("docker_cmd", {
            "name": "docker_cmd",
            "description": "Run docker command (ps, images, stats, logs).",
            "parameters": {"type": "object", "properties": {
                "command": {"type": "string", "description": "Docker subcommand, e.g. 'ps' or 'logs mycontainer'"},
            }},
        }, _docker_cmd),
        ToolEntry("ssh_cmd", {
            "name": "ssh_cmd",
            "description": "Run command on remote host via SSH. Use host aliases from ~/.ssh/config.",
            "parameters": {"type": "object", "properties": {
                "host": {"type": "string"}, "command": {"type": "string"},
            }, "required": ["host", "command"]},
        }, _ssh_cmd),
        ToolEntry("git_backup", {
            "name": "git_backup",
            "description": "Git add + commit + push for workspace backup.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}, "message": {"type": "string"},
            }},
        }, _git_backup),
        ToolEntry("security_check", {
            "name": "security_check",
            "description": "Check text for prompt injection or sensitive data (API keys, passwords).",
            "parameters": {"type": "object", "properties": {
                "text": {"type": "string"},
            }, "required": ["text"]},
        }, _security_check),
    ]
