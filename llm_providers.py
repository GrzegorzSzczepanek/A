"""
LLM Provider abstraction — supports Claude, Gemini, and Kimi (Moonshot AI).

Each provider implements the same interface: send a system prompt + user message,
get back a text response. Provider is auto-detected from the model name or can
be set explicitly via --provider flag.

Environment variables:
    ANTHROPIC_API_KEY   — for Claude models
    GEMINI_API_KEY      — for Gemini models
    KIMI_API_KEY        — for Kimi / Moonshot models (moonshot.cn)
"""

import json
import os
import random
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


# ── HTTP with retry/backoff ──────────────────────────────────────────────────

RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}
MAX_RETRIES = 4
BACKOFF_BASE = 1.8
BACKOFF_CAP = 30.0
# Minimum sleep when server says rate-limit (429). Free-tier Gemini windows
# are per-minute, so we need to wait out the window.
RATE_LIMIT_MIN_SLEEP = 12.0
# Minimum gap between successive successful calls. Lower = faster but more
# 429s. 0.5s is enough headroom for 20 RPM (=3s/call) since calls usually
# take 5-15s anyway, naturally spacing them out.
MIN_INTER_CALL_GAP = 0.5
_last_call_ts = 0.0
import threading
_call_lock = threading.Lock()

# Gemini error body pattern: "Please retry in 9.4s." or "...12.34s..."
_GEMINI_RETRY_RE = re.compile(r"retry in\s+([\d.]+)s", re.IGNORECASE)


def _post_json(url: str, payload: bytes, headers: dict,
               timeout: int = 60, context=None) -> dict:
    """POST JSON with exponential backoff + jitter on retryable HTTP errors.

    Retries on: 408/425/429/5xx, URLError (network/DNS), socket timeouts.
    Honors Retry-After header on 429/503 when present.
    Throttles to MIN_INTER_CALL_GAP between successful calls (free-tier RPM safety).
    """
    global _last_call_ts
    # Throttle: respect minimum gap from previous successful call across all
    # threads. Lock-protected so parallel callers stagger correctly.
    with _call_lock:
        elapsed = time.monotonic() - _last_call_ts
        if elapsed < MIN_INTER_CALL_GAP:
            time.sleep(MIN_INTER_CALL_GAP - elapsed)
        _last_call_ts = time.monotonic()  # reserve slot before HTTP

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url, data=payload, headers=headers, method="POST"
            )
            kwargs = {"timeout": timeout}
            if context is not None:
                kwargs["context"] = context
            with urllib.request.urlopen(req, **kwargs) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code not in RETRY_STATUSES or attempt == MAX_RETRIES - 1:
                raise
            # Some APIs (Gemini) embed retry-in-Ns in the body, not the header.
            body_hint = None
            try:
                err_body = e.read().decode(errors="replace")
                m = _GEMINI_RETRY_RE.search(err_body)
                if m:
                    body_hint = m.group(1)
            except Exception:
                pass
            sleep_s = _retry_delay(
                attempt,
                e.headers.get("Retry-After") or body_hint,
                is_rate_limit=(e.code == 429),
            )
            time.sleep(sleep_s)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_error = e
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(_retry_delay(attempt, None))
    if last_error:
        raise last_error
    raise RuntimeError("retry loop exited without result")


def _retry_delay(attempt: int, retry_after_header: Optional[str],
                 is_rate_limit: bool = False) -> float:
    """Backoff: server-suggested Retry-After (s) if present, else exponential w/ jitter.

    For 429 rate-limit errors, enforce a minimum sleep so we wait out the rate-limit
    window (typically 60s) instead of burning retries.
    """
    if retry_after_header:
        try:
            return min(max(float(retry_after_header), 1.0), BACKOFF_CAP)
        except (TypeError, ValueError):
            pass
    base = min(BACKOFF_BASE ** attempt, BACKOFF_CAP)
    delay = base + random.uniform(0, base * 0.3)
    if is_rate_limit:
        delay = max(delay, RATE_LIMIT_MIN_SLEEP)
    return delay

# Load .env file if present (python-dotenv optional)
try:
    from dotenv import load_dotenv

    # Walk up from this file to find .env
    _env = Path(__file__).resolve().parent / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    # No python-dotenv — fall back to manual parsing
    _env = Path(__file__).resolve().parent / ".env"
    if _env.exists():
        for line in _env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


# ── Provider registry ────────────────────────────────────────────────────────

PROVIDERS = {
    "claude": {
        "env_key": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
        "models": [
            "claude-sonnet-4-20250514",
            "claude-haiku-4-5-20251001",
        ],
    },
    "gemini": {
        "env_key": "GEMINI_API_KEY",
        # 3.1 Flash with thinking disabled — fastest path that still produces
        # valid structured DITA. Pro thinking dominated wall-clock (~86s/topic).
        "default_model": "gemini-3.1-flash",
        "models": [
            "gemini-3.1-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ],
    },
    "kimi": {
        "env_key": "KIMI_API_KEY",
        "default_model": "kimi-k2.6",
        "models": [
            "kimi-k2.6",
            "kimi-k2.5",
            "kimi-latest",
            "moonshot-v1-auto",
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        ],
    },
}


def detect_provider(model: str) -> str:
    """Auto-detect provider from model name."""
    m = model.lower()
    if "claude" in m:
        return "claude"
    elif "gemini" in m:
        return "gemini"
    elif "moonshot" in m or "kimi" in m:
        return "kimi"
    else:
        # Prefer Gemini first (Flash is fastest at comparable quality).
        # Fall back to other providers only if their key is set AND no Gemini key.
        if os.environ.get("GEMINI_API_KEY"):
            return "gemini"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            return "claude"
        elif os.environ.get("KIMI_API_KEY"):
            return "kimi"
    return "gemini"  # default


def get_api_key(provider: str, explicit_key: str = None) -> Optional[str]:
    """Get API key from explicit argument or environment."""
    if explicit_key:
        return explicit_key
    env_var = PROVIDERS.get(provider, {}).get("env_key", "")
    return os.environ.get(env_var)


def get_default_model(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("default_model", "gemini-3.1-flash")


# ── API callers ──────────────────────────────────────────────────────────────


def _call_claude(system: str, user: str, api_key: str, model: str) -> str:
    """Call Anthropic Messages API."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 16384,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    ).encode()

    data = _post_json(url, payload, headers)

    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    return ""


# Process-local Gemini context cache: SHA-256(system_prompt + model) -> cachedContents/name
# The cache TTL is 5 minutes, plenty for a single PDF batch. Cached entries
# survive across calls within one process, so the 16K system prompt is sent
# to Google only ONCE per process, not once per LLM call.
import hashlib as _hashlib_lp
_GEMINI_CACHE: dict[tuple, tuple[str, float]] = {}
_GEMINI_CACHE_LOCK = threading.Lock()
GEMINI_CACHE_TTL_SECONDS = 300  # 5 min, max Gemini allows is 1h


def _get_or_create_gemini_cache(system: str, api_key: str, model: str) -> Optional[str]:
    """Return a `cachedContents/<id>` name for the given system prompt, creating
    it on first use within a process. Returns None on failure (caller falls back
    to inline system_instruction).
    """
    key = (model, _hashlib_lp.sha256(system.encode()).hexdigest())
    now = time.monotonic()
    with _GEMINI_CACHE_LOCK:
        cached = _GEMINI_CACHE.get(key)
        if cached and now < cached[1]:
            return cached[0]

    url = (
        "https://generativelanguage.googleapis.com/v1beta/cachedContents"
        f"?key={api_key}"
    )
    headers = {"Content-Type": "application/json"}
    payload = json.dumps({
        "model": f"models/{model}",
        "systemInstruction": {"parts": [{"text": system}]},
        # Need a non-empty contents to satisfy min-token requirement.
        "contents": [{"role": "user", "parts": [{"text": "_warmup"}]}],
        "ttl": f"{GEMINI_CACHE_TTL_SECONDS}s",
    }).encode()
    try:
        data = _post_json(url, payload, headers)
        name = data.get("name") if isinstance(data, dict) else None
        if name:
            with _GEMINI_CACHE_LOCK:
                _GEMINI_CACHE[key] = (name, now + GEMINI_CACHE_TTL_SECONDS - 10)
            return name
    except Exception:
        return None
    return None


GEMINI_STREAM_PROGRESS = os.environ.get("GEMINI_STREAM_PROGRESS", "1") not in ("0", "false", "")


def _call_gemini(system: str, user: str, api_key: str, model: str) -> str:
    """Call Google Gemini API via streaming endpoint (streamGenerateContent + SSE).

    Streams chunks as they arrive so the caller sees progress instead of a
    single 60–90s stall. Also disables "thinking" (thinkingBudget=0) on
    reasoning-capable Flash/Pro models — for structural DITA conversion the
    model doesn't need to deliberate, and thinking dominates wall-clock.

    Uses context caching for the system instruction when available so the
    ~16K-char system prompt is only processed once per process.
    """
    headers = {"Content-Type": "application/json"}
    cached_name = _get_or_create_gemini_cache(system, api_key, model)

    body = {
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": 8192,
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    if cached_name:
        body["cachedContent"] = cached_name
    else:
        body["system_instruction"] = {"parts": [{"text": system}]}

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":streamGenerateContent?alt=sse&key={api_key}"
    )
    payload = json.dumps(body).encode()

    chunks: list[str] = []
    err: Optional[dict] = None

    def _consume(line: str) -> None:
        nonlocal err
        if not line.startswith("data:"):
            return
        data_str = line[5:].strip()
        if not data_str:
            return
        try:
            evt = json.loads(data_str)
        except json.JSONDecodeError:
            return
        if isinstance(evt, dict) and "error" in evt:
            err = evt["error"]
            return
        for cand in evt.get("candidates", []) or []:
            for part in cand.get("content", {}).get("parts", []) or []:
                text = part.get("text")
                if text:
                    chunks.append(text)
                    if GEMINI_STREAM_PROGRESS:
                        # Single dot per chunk — flushes so terminal shows live progress.
                        print(".", end="", flush=True)

    _stream_post_sse(url, payload, headers, on_line=_consume)

    if GEMINI_STREAM_PROGRESS and chunks:
        print(flush=True)

    if err:
        raise RuntimeError(f"Gemini API error: {err.get('message', err)}")

    return "".join(chunks)


def _stream_post_sse(url: str, payload: bytes, headers: dict, on_line,
                     timeout: int = 120) -> None:
    """POST and consume an SSE stream line-by-line, with retry/backoff
    semantics mirroring `_post_json`. Calls `on_line(str)` for each line."""
    global _last_call_ts
    with _call_lock:
        elapsed = time.monotonic() - _last_call_ts
        if elapsed < MIN_INTER_CALL_GAP:
            time.sleep(MIN_INTER_CALL_GAP - elapsed)
        _last_call_ts = time.monotonic()

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url, data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        on_line(line)
            return
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code not in RETRY_STATUSES or attempt == MAX_RETRIES - 1:
                raise
            body_hint = None
            try:
                err_body = e.read().decode(errors="replace")
                m = _GEMINI_RETRY_RE.search(err_body)
                if m:
                    body_hint = m.group(1)
            except Exception:
                pass
            time.sleep(_retry_delay(
                attempt,
                e.headers.get("Retry-After") or body_hint,
                is_rate_limit=(e.code == 429),
            ))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_error = e
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(_retry_delay(attempt, None))
    if last_error:
        raise last_error
    raise RuntimeError("retry loop exited without result")


def _call_kimi(system: str, user: str, api_key: str, model: str) -> str:
    """Call Moonshot AI / Kimi API (OpenAI-compatible chat completions).
    Tries global endpoint first (api.moonshot.ai), falls back to CN (api.moonshot.cn).
    """
    endpoints = [
        "https://api.moonshot.ai/v1/chat/completions",  # global (international keys)
        "https://api.moonshot.cn/v1/chat/completions",  # china (CN keys)
    ]
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 16384,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode()

    last_error = None
    ctx = ssl.create_default_context()
    for url in endpoints:
        try:
            data = _post_json(url, payload, headers, context=ctx)
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 401:
                last_error = e
                continue  # try next endpoint
            raise
        except (urllib.error.URLError, KeyError, IndexError, TypeError) as e:
            last_error = e
            continue

    if last_error:
        raise last_error
    return ""


# ── Unified caller ───────────────────────────────────────────────────────────

CALLERS = {
    "claude": _call_claude,
    "gemini": _call_gemini,
    "kimi": _call_kimi,
}


def call_llm(
    system: str, user: str, api_key: str, model: str, provider: str = None
) -> str:
    """
    Call an LLM with the given system prompt and user message.
    Provider is auto-detected from the model name if not specified.

    Returns the model's text response.
    Raises RuntimeError on API errors.
    """
    if provider is None:
        provider = detect_provider(model)

    caller = CALLERS.get(provider)
    if caller is None:
        raise ValueError(
            f"Unknown provider: {provider}. " f"Supported: {', '.join(CALLERS.keys())}"
        )

    return caller(system, user, api_key, model)


# ── Convenience ──────────────────────────────────────────────────────────────


def resolve_config(
    api_key: str = None, model: str = None, provider: str = None
) -> dict:
    """
    Resolve provider/model/key configuration from explicit args + environment.

    Returns: {"provider": str, "model": str, "api_key": str | None}

    Priority:
    1. Explicit --provider + --model + --api-key flags
    2. Auto-detect provider from model name
    3. Fall back to whichever env var is set (ANTHROPIC > GEMINI > KIMI)
    """
    # Determine provider
    if provider:
        prov = provider
    elif model:
        prov = detect_provider(model)
    else:
        # Prefer Gemini first (default for this project per user directive).
        for p in ["gemini", "claude", "kimi"]:
            if os.environ.get(PROVIDERS[p]["env_key"]):
                prov = p
                break
        else:
            prov = "gemini"

    # Determine model
    if model is None:
        model = get_default_model(prov)

    # Determine API key
    key = get_api_key(prov, api_key)

    return {"provider": prov, "model": model, "api_key": key}


def print_provider_info(config: dict):
    """Print provider configuration for the user."""
    prov = config["provider"]
    model = config["model"]
    has_key = bool(config["api_key"])

    provider_names = {
        "claude": "Anthropic Claude",
        "gemini": "Google Gemini",
        "kimi": "Moonshot Kimi",
    }

    name = provider_names.get(prov, prov)
    status = "✓ key found" if has_key else "✗ no key"
    print(f"  Provider: {name}")
    print(f"  Model:    {model}")
    print(f"  API key:  {status}")

    if not has_key:
        env_var = PROVIDERS.get(prov, {}).get("env_key", "?")
        print(f"  → Set {env_var} or use --api-key to enable LLM mode")


def test_connection(
    api_key: str = None, model: str = None, provider: str = None
) -> bool:
    """Quick connectivity test — sends 'Say OK' and checks for a response."""
    config = resolve_config(api_key, model, provider)
    if not config["api_key"]:
        print("✗ No API key configured")
        return False

    print_provider_info(config)
    print("  Testing...")

    try:
        resp = call_llm(
            system="Reply with exactly: OK",
            user="Test",
            api_key=config["api_key"],
            model=config["model"],
            provider=config["provider"],
        )
        ok = "ok" in resp.lower()
        print(f"  {'✓' if ok else '~'} Response: {resp.strip()[:60]}")
        return ok
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


if __name__ == "__main__":
    import sys

    print("Testing LLM connection...\n")
    success = test_connection()
    sys.exit(0 if success else 1)
