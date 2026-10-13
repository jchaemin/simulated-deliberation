import os
import threading
import time

from openai import OpenAI

NO_REASONING_FIELD = {"openai/gpt-4.1-mini"}
MINIMAL_REASONING = {"anthropic/claude-opus-5.5", "google/gemini-3.1-pro-preview"}


def _api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key and os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("OPENROUTER_API_KEY"):
                key = line.split("=", 1)[1].strip()
    return key or "set-OPENROUTER_API_KEY"


_client = None
_lock = threading.Lock()
usage = {"cost": 0.0, "calls": 0, "failures": 0}


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=_api_key(), timeout=120)
    return _client


def chat(model, messages, temperature, max_tokens, json_mode=True, seed=None, retries=5):
    extra = {"usage": {"include": True}}
    if model not in NO_REASONING_FIELD:
        extra["reasoning"] = {"effort": "minimal"} if model in MINIMAL_REASONING else {"enabled": False}
    kw = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, extra_body=extra)
    if json_mode:
        kw["response_format"] = {"type": "json_object"}
    if seed is not None:
        kw["seed"] = seed
    err = None
    for attempt in range(retries):
        try:
            r = _get_client().chat.completions.create(**kw)
            with _lock:
                usage["cost"] += float((getattr(r.usage, "model_extra", None) or {}).get("cost") or 0)
                usage["calls"] += 1
            return r.choices[0].message.content or ""
        except Exception as e:
            err = e
            time.sleep(3 * (attempt + 1))
    with _lock:
        usage["failures"] += 1
    print("FAILED", str(err)[:120], flush=True)
    return ""


def report():
    return f"cost ${usage['cost']:.2f}, calls {usage['calls']}, failures {usage['failures']}"
