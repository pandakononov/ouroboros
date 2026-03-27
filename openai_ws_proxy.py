"""
OpenAI Codex Proxy — converts /v1/chat/completions to ChatGPT backend-api/codex/responses.
Reads credentials from ~/.codex/auth.json (Codex CLI OAuth).
"""

import os
import json
import logging
import time
import base64
from typing import Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("openai_codex_proxy")

app = FastAPI(title="OpenAI Codex Proxy")

AUTH_KEY = os.getenv("PROXY_AUTH_KEY", "sk-openai-proxy")
CODEX_AUTH_PATH = os.path.expanduser("~/.codex/auth.json")
CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex/responses"


def _load_auth() -> dict:
    try:
        with open(CODEX_AUTH_PATH) as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load auth: {e}")
        return {}


def _get_token() -> str:
    return _load_auth().get("tokens", {}).get("access_token", "")


def _get_account_id(token: str) -> str:
    """Extract chatgpt_account_id from JWT payload."""
    try:
        payload_b64 = token.split(".")[1]
        # Add padding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("https://api.openai.com/auth", {}).get("chatgpt_account_id", "")
    except Exception as e:
        log.error(f"Failed to extract account_id: {e}")
        return ""


def _convert_messages_to_input(messages: list) -> tuple:
    """Convert chat/completions messages to Responses API input format."""
    instructions = ""
    input_items = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            instructions = content
            continue

        if role == "tool":
            input_items.append({
                "type": "function_call_output",
                "call_id": msg.get("tool_call_id", ""),
                "output": content if isinstance(content, str) else json.dumps(content),
            })
            continue

        if role == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                input_items.append({
                    "type": "function_call",
                    "id": tc.get("id", ""),
                    "call_id": tc.get("id", ""),
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                })
            continue

        if isinstance(content, str):
            content_parts = [{"type": "input_text", "text": content}]
        elif isinstance(content, list):
            content_parts = content
        else:
            content_parts = [{"type": "input_text", "text": str(content)}]

        input_items.append({
            "type": "message",
            "role": role,
            "content": content_parts,
        })

    return instructions, input_items


def _convert_tools(tools: Optional[list]) -> list:
    if not tools:
        return []
    result = []
    for t in tools:
        if t.get("type") == "function":
            result.append({
                "type": "function",
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "parameters": t["function"].get("parameters", {}),
            })
    return result


async def _codex_request(model: str, instructions: str, input_items: list,
                          tools: list, max_tokens: int, tool_choice: str) -> dict:
    token = _get_token()
    if not token:
        return {"error": {"message": "No Codex token", "type": "auth_error"}}

    account_id = _get_account_id(token)
    if not account_id:
        return {"error": {"message": "Cannot extract account_id from token", "type": "auth_error"}}

    headers = {
        "Authorization": f"Bearer {token}",
        "chatgpt-account-id": account_id,
        "originator": "pi",
        "OpenAI-Beta": "responses=experimental",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "User-Agent": "pi (darwin; aarch64)",
    }

    body = {
        "model": model,
        "store": False,
        "stream": True,
        "input": input_items,
        "tool_choice": tool_choice if tools else "none",
        "parallel_tool_calls": True,
    }
    body["instructions"] = instructions or "You are a helpful assistant."
    # ChatGPT backend doesn't support max_output_tokens
    if tools:
        body["tools"] = tools

    try:
        log.info(f"[{model}] sending to ChatGPT backend-api")
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(CODEX_BASE_URL, json=body, headers=headers)

            if resp.status_code != 200:
                error_text = resp.text[:500]
                log.error(f"[{model}] {resp.status_code}: {error_text}")
                return {"error": {"message": error_text, "type": "api_error", "code": resp.status_code}}

            # Parse SSE stream
            full_text = ""
            tool_calls = []
            usage = {}
            response_id = ""
            finish_reason = "stop"

            for line in resp.text.split("\n"):
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    evt = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                evt_type = evt.get("type", "")

                if evt_type == "response.output_text.delta":
                    full_text += evt.get("delta", "")

                elif evt_type == "response.output_item.done":
                    item = evt.get("item", {})
                    if item.get("type") == "function_call":
                        tool_calls.append({
                            "id": item.get("call_id", item.get("id", "")),
                            "type": "function",
                            "function": {
                                "name": item.get("name", ""),
                                "arguments": item.get("arguments", "{}"),
                            }
                        })
                        finish_reason = "tool_calls"

                elif evt_type in ("response.completed", "response.done"):
                    resp_data = evt.get("response", {})
                    response_id = resp_data.get("id", "")
                    usage = resp_data.get("usage", {})

                elif evt_type == "response.failed":
                    error = evt.get("response", {}).get("error", {})
                    return {"error": {"message": error.get("message", "Failed"), "type": "api_error"}}

            message = {"role": "assistant", "content": full_text or None}
            if tool_calls:
                message["tool_calls"] = tool_calls

            return {
                "id": response_id or f"chatcmpl-codex-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": message,
                    "finish_reason": finish_reason,
                }],
                "usage": {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
            }

    except Exception as e:
        log.error(f"[{model}] error: {e}")
        return {"error": {"message": str(e), "type": "proxy_error"}}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {AUTH_KEY}":
        raise HTTPException(status_code=401, detail="Invalid auth key")

    body = await request.json()
    model = body.get("model", "gpt-5.4")
    messages = body.get("messages", [])
    tools = body.get("tools")
    max_tokens = body.get("max_tokens", 4096)
    tool_choice = body.get("tool_choice", "auto") if tools else "none"

    instructions, input_items = _convert_messages_to_input(messages)
    converted_tools = _convert_tools(tools)

    result = await _codex_request(model, instructions, input_items,
                                   converted_tools, max_tokens, tool_choice)

    if "error" in result and "choices" not in result:
        code = result["error"].get("code", 502)
        return JSONResponse(status_code=code if isinstance(code, int) else 502, content=result)

    return JSONResponse(content=result)


@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [
        {"id": "gpt-5.4", "object": "model"},
        {"id": "gpt-5.3-codex", "object": "model"},
        {"id": "gpt-4.1", "object": "model"},
        {"id": "o4-mini", "object": "model"},
        {"id": "o3", "object": "model"},
    ]}


@app.get("/health")
async def health():
    token = _get_token()
    account_id = _get_account_id(token) if token else ""
    return {"status": "ok" if token else "no_token", "has_token": bool(token), "account_id": account_id[:8] + "..."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PROXY_PORT", "8889"))
    uvicorn.run(app, host="127.0.0.1", port=port)
