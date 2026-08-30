"""Thin OpenAI-compatible client for OpenRouter.

Key from env OPENROUTER_API_KEY (or project/.env). Endpoint is OpenAI-compatible,
so any model on OpenRouter works by its `provider/model` id. We keep separate
model ids for the debate AGENTS and the JUDGE so they can differ.
"""
import os, time, pathlib
from openai import OpenAI

def _load_env():
    envf = pathlib.Path(__file__).resolve().parents[1] / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_client = None

def client():
    global _client
    if _client is not None:
        return _client
    _load_env()
    # Prefer a direct OpenAI key; fall back to OpenRouter if that's what's set.
    if os.getenv("OPENAI_API_KEY"):
        _client = OpenAI(base_url="https://api.openai.com/v1",
                         api_key=os.getenv("OPENAI_API_KEY"))
        return _client
    if os.getenv("OPENROUTER_API_KEY"):
        _client = OpenAI(base_url="https://openrouter.ai/api/v1",
                         api_key=os.getenv("OPENROUTER_API_KEY"))
        return _client
    raise RuntimeError("no API key set (OPENAI_API_KEY or OPENROUTER_API_KEY in .env)")

def list_models(filter_str=None):
    ids = [m.id for m in client().models.list().data]
    if filter_str:
        ids = [m for m in ids if filter_str.lower() in m.lower()]
    return sorted(ids)

def chat(model, messages, temperature=0.7, seed=None, max_tokens=1024, retries=4,
         response_format=None):
    c = client()
    last = None
    for a in range(retries):
        try:
            kw = dict(model=model, messages=messages, temperature=temperature,
                      max_tokens=max_tokens)
            if seed is not None:
                kw["seed"] = seed
            if response_format is not None:
                kw["response_format"] = response_format
            r = c.chat.completions.create(**kw)
            return r.choices[0].message.content
        except Exception as e:
            last = e
            time.sleep(2 * (a + 1))
    raise last

if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen/qwen-2.5-72b-instruct"
    print("smoke model:", model)
    print(chat(model, [{"role": "user", "content": "한 문장으로 자기소개 해줘."}],
               max_tokens=120))
