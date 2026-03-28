"""
Integration tools — email, RSS, social media reading, CLI wrapping, markdown conversion.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import List

from ouroboros.tools.registry import ToolContext, ToolEntry


# ── Email ─────────────────────────────────────────────────────────────

def _send_email(ctx: ToolContext, to: str, subject: str, body: str,
                smtp_server: str = "", smtp_port: int = 587) -> str:
    """Send email via SMTP. Credentials from env: EMAIL_USER, EMAIL_PASSWORD, SMTP_SERVER."""
    import smtplib
    from email.mime.text import MIMEText

    user = os.environ.get("EMAIL_USER", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    server = smtp_server or os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", smtp_port))

    if not user or not password:
        return json.dumps({"error": "EMAIL_USER and EMAIL_PASSWORD env vars required"})

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to

        with smtplib.SMTP(server, port) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)

        return json.dumps({"status": "sent", "to": to, "subject": subject})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _read_email(ctx: ToolContext, folder: str = "INBOX", count: int = 5) -> str:
    """Read recent emails via IMAP. Credentials from env: EMAIL_USER, EMAIL_PASSWORD, IMAP_SERVER."""
    import imaplib
    import email as email_lib
    from email.header import decode_header

    user = os.environ.get("EMAIL_USER", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    server = os.environ.get("IMAP_SERVER", "imap.gmail.com")

    if not user or not password:
        return json.dumps({"error": "EMAIL_USER and EMAIL_PASSWORD env vars required"})

    try:
        with imaplib.IMAP4_SSL(server) as mail:
            mail.login(user, password)
            mail.select(folder)
            _, msg_ids = mail.search(None, "ALL")
            ids = msg_ids[0].split()[-count:]

            messages = []
            for mid in reversed(ids):
                _, data = mail.fetch(mid, "(RFC822)")
                msg = email_lib.message_from_bytes(data[0][1])
                subj = decode_header(msg["Subject"])[0]
                subject = subj[0].decode(subj[1] or "utf-8") if isinstance(subj[0], bytes) else str(subj[0])
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")[:500]
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:500]
                messages.append({"from": msg["From"], "subject": subject,
                                 "date": msg["Date"], "body": body})

        return json.dumps({"messages": messages, "count": len(messages)}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── RSS ───────────────────────────────────────────────────────────────

def _rss_read(ctx: ToolContext, url: str, count: int = 10) -> str:
    """Read RSS/Atom feed and return recent entries."""
    try:
        import feedparser
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "feedparser"])
            import feedparser
        except Exception:
            return json.dumps({"error": "Install feedparser: pip install feedparser"})

    try:
        feed = feedparser.parse(url)
        entries = []
        for entry in feed.entries[:count]:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:300],
            })
        return json.dumps({
            "feed_title": feed.feed.get("title", ""),
            "entries": entries,
            "count": len(entries),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Social media (read-only) ─────────────────────────────────────────

def _reddit_read(ctx: ToolContext, subreddit: str = "MachineLearning", sort: str = "hot",
                  count: int = 10) -> str:
    """Read Reddit posts (no auth, read-only via JSON API)."""
    import requests
    try:
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={count}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Ouroboros/1.0"})
        r.raise_for_status()
        posts = []
        for child in r.json().get("data", {}).get("children", []):
            d = child.get("data", {})
            posts.append({
                "title": d.get("title", ""),
                "score": d.get("score", 0),
                "url": d.get("url", ""),
                "selftext": d.get("selftext", "")[:200],
                "num_comments": d.get("num_comments", 0),
            })
        return json.dumps({"subreddit": subreddit, "posts": posts}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── CLI Wrap (meta-tool) ─────────────────────────────────────────────

def _cli_wrap(ctx: ToolContext, command: str, args: str = "", timeout_sec: int = 30) -> str:
    """Run any CLI tool and return output. Use for tools not covered by other tools.

    Safety: no sudo, no rm -rf, no pipe to shell.
    """
    forbidden = ["sudo", "rm -rf", "rm -r /", "mkfs", "> /dev/", "| sh", "| bash", "curl | "]
    for f in forbidden:
        if f in command.lower() or f in args.lower():
            return json.dumps({"error": f"Forbidden pattern: {f}"})

    cmd = f"{command} {args}".strip()
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout_sec)
        return json.dumps({
            "command": cmd,
            "stdout": r.stdout[:5000],
            "stderr": r.stderr[:1000] if r.returncode else "",
            "exit_code": r.returncode,
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Timeout after {timeout_sec}s", "command": cmd})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Markdown conversion ──────────────────────────────────────────────

def _markdown_convert(ctx: ToolContext, text: str, to_format: str = "html") -> str:
    """Convert Markdown to HTML or plain text."""
    if to_format == "html":
        try:
            import markdown
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "markdown"])
                import markdown
            except Exception:
                # Simple fallback
                html = text.replace("\n\n", "<br><br>")
                html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
                html = re.sub(r"\*(.+?)\*", r"<i>\1</i>", html)
                return json.dumps({"html": html, "fallback": True})

        html = markdown.markdown(text, extensions=["tables", "fenced_code"])
        return json.dumps({"html": html}, ensure_ascii=False)

    elif to_format == "plain":
        plain = re.sub(r"[#*_`~\[\]]", "", text)
        plain = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", plain)
        return json.dumps({"plain": plain}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown format: {to_format}. Use 'html' or 'plain'."})


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("send_email", {
            "name": "send_email",
            "description": "Send email via SMTP. Needs EMAIL_USER, EMAIL_PASSWORD env vars.",
            "parameters": {"type": "object", "properties": {
                "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"},
            }, "required": ["to", "subject", "body"]},
        }, _send_email),

        ToolEntry("read_email", {
            "name": "read_email",
            "description": "Read recent emails via IMAP. Needs EMAIL_USER, EMAIL_PASSWORD env vars.",
            "parameters": {"type": "object", "properties": {
                "folder": {"type": "string"}, "count": {"type": "integer"},
            }},
        }, _read_email),

        ToolEntry("rss_read", {
            "name": "rss_read",
            "description": "Read RSS/Atom feed. Returns titles, links, summaries.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "description": "RSS feed URL"},
                "count": {"type": "integer"},
            }, "required": ["url"]},
        }, _rss_read),

        ToolEntry("reddit_read", {
            "name": "reddit_read",
            "description": "Read Reddit posts (no auth needed). Default: r/MachineLearning hot.",
            "parameters": {"type": "object", "properties": {
                "subreddit": {"type": "string"}, "sort": {"type": "string"}, "count": {"type": "integer"},
            }},
        }, _reddit_read),

        ToolEntry("cli_wrap", {
            "name": "cli_wrap",
            "description": "Run any CLI command. Safety: no sudo, no rm -rf. Use for tools not covered by other tools.",
            "parameters": {"type": "object", "properties": {
                "command": {"type": "string"}, "args": {"type": "string"},
                "timeout_sec": {"type": "integer"},
            }, "required": ["command"]},
        }, _cli_wrap),

        ToolEntry("markdown_convert", {
            "name": "markdown_convert",
            "description": "Convert Markdown to HTML or plain text.",
            "parameters": {"type": "object", "properties": {
                "text": {"type": "string"}, "to_format": {"type": "string", "enum": ["html", "plain"]},
            }, "required": ["text"]},
        }, _markdown_convert),
    ]
