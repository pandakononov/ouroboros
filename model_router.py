"""
Model Router — lightweight OpenAI-compatible proxy with multi-provider routing and fallback.
Ouroboros sends requests here; the router picks the right provider based on model name.
"""

import os
import json
import time
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("model_router")

app = FastAPI(title="Model Router")

# === Provider configs ===
def _load_codex_token():
    """Load OpenAI access token from Codex CLI auth."""
    try:
        with open(os.path.expanduser("~/.codex/auth.json")) as f:
            data = json.load(f)
        return data.get("tokens", {}).get("access_token", "")
    except Exception:
        return ""

PROVIDERS = {
    "gemini": {
        "base_url": "http://localhost:8888/v1",
        "api_key": os.getenv("GEMINI_PROXY_KEY", "ouroboros123"),
    },
    "openai": {
        "base_url": "http://localhost:8889/v1",
        "api_key": "sk-openai-proxy",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": os.getenv("NVIDIA_API_KEY", ""),
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
    },
    "spark": {
        "base_url": "http://192.168.1.121:11434/v1",
        "api_key": "not-needed",
    },
}

# === Model → provider mapping with fallback chains ===
MODEL_ROUTES = {
    # Dialog (needs tool calling!)
    "dialog": [
        {"provider": "nvidia", "model": "moonshotai/kimi-k2.5"},
        {"provider": "openai", "model": "gpt-5.4"},
        {"provider": "spark", "model": "qwen3.5:27b"},
    ],
    # Coding — GPT-5.4 primary
    "coder": [
        {"provider": "openai", "model": "gpt-5.4"},
        {"provider": "nvidia", "model": "moonshotai/kimi-k2.5"},
        {"provider": "spark", "model": "qwen3.5:27b"},
    ],
    # Code review — Gemini Pro primary, GPT-5.4 fallback
    "reviewer": [
        {"provider": "gemini", "model": "gemini-2.5-pro"},
        {"provider": "openai", "model": "gpt-5.4"},
        {"provider": "nvidia", "model": "moonshotai/kimi-k2.5"},
        {"provider": "spark", "model": "qwen3.5:27b"},
    ],
    # Light / consciousness (speed matters)
    "light": [
        {"provider": "gemini", "model": "gemini-2.5-flash"},
        {"provider": "nvidia", "model": "moonshotai/kimi-k2.5"},
        {"provider": "spark", "model": "qwen3.5:27b"},
    ],
    # Direct model pass-through (for any model not in routes)
}

AUTH_KEY = os.getenv("ROUTER_AUTH_KEY", "sk-router-ouroboros")

# === Dedup: track recent requests to prevent duplicate sends ===
import hashlib
from collections import OrderedDict

_recent_requests: OrderedDict = OrderedDict()  # hash -> (timestamp, response)
_DEDUP_WINDOW_SEC = 30  # ignore identical requests within this window


def _request_hash(body: dict) -> str:
    """Hash model + last message content for dedup."""
    msgs = body.get("messages", [])
    last_msg = msgs[-1].get("content", "") if msgs else ""
    key = f"{body.get('model', '')}:{last_msg[:500]}"
    return hashlib.md5(key.encode()).hexdigest()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Auth check
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {AUTH_KEY}":
        raise HTTPException(status_code=401, detail="Invalid auth key")

    body = await request.json()
    requested_model = body.get("model", "dialog")

    # Dedup check
    req_hash = _request_hash(body)
    now = time.time()
    if req_hash in _recent_requests:
        prev_ts, prev_resp = _recent_requests[req_hash]
        if now - prev_ts < _DEDUP_WINDOW_SEC:
            log.info(f"[{requested_model}] dedup hit, returning cached response ({now - prev_ts:.1f}s ago)")
            return JSONResponse(content=prev_resp)

    # Clean old entries
    while _recent_requests:
        oldest_hash, (oldest_ts, _) = next(iter(_recent_requests.items()))
        if now - oldest_ts > _DEDUP_WINDOW_SEC * 2:
            _recent_requests.pop(oldest_hash)
        else:
            break

    # Get route chain
    chain = MODEL_ROUTES.get(requested_model)
    if not chain:
        # Try as direct provider/model format
        chain = [{"provider": "spark", "model": requested_model}]

    last_error = None
    for i, route in enumerate(chain):
        provider_name = route["provider"]
        provider = PROVIDERS.get(provider_name)
        if not provider or not provider["api_key"]:
            continue

        target_model = route["model"]
        target_url = f"{provider['base_url']}/chat/completions"

        # Build forwarded request
        forward_body = {**body, "model": target_model}

        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }

        try:
            log.info(f"[{requested_model}] trying {provider_name}/{target_model} ({i+1}/{len(chain)})")
            _timeout = 60 if provider_name == "gemini" else 120
            async with httpx.AsyncClient(timeout=_timeout) as client:
                resp = await client.post(target_url, json=forward_body, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                # Inject routing metadata
                data["_router"] = {
                    "provider": provider_name,
                    "model": target_model,
                    "attempt": i + 1,
                }
                log.info(f"[{requested_model}] success via {provider_name}/{target_model}")
                _recent_requests[req_hash] = (time.time(), data)
                return JSONResponse(content=data)

            if resp.status_code == 429:
                log.warning(f"[{requested_model}] rate limited on {provider_name}/{target_model}, trying next")
                last_error = f"{provider_name}: 429 rate limited"
                continue

            # Other errors
            log.warning(f"[{requested_model}] {provider_name} returned {resp.status_code}: {resp.text[:200]}")
            last_error = f"{provider_name}: {resp.status_code}"
            continue

        except Exception as e:
            log.warning(f"[{requested_model}] {provider_name} failed: {e}")
            last_error = f"{provider_name}: {str(e)[:100]}"
            continue

    # All providers failed
    return JSONResponse(
        status_code=503,
        content={"error": {"message": f"All providers failed. Last: {last_error}", "type": "router_error"}},
    )


@app.get("/v1/models")
async def list_models(request: Request):
    models = [{"id": name, "object": "model"} for name in MODEL_ROUTES]
    return {"object": "list", "data": models}


@app.get("/health")
async def health():
    return {"status": "ok", "models": list(MODEL_ROUTES.keys()), "providers": list(PROVIDERS.keys())}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ROUTER_PORT", "4000"))
    uvicorn.run(app, host="127.0.0.1", port=port)
