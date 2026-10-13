import json
import os
from concurrent.futures import ThreadPoolExecutor

MODELS = {"sol": "openai/gpt-6-sol", "luna": "openai/gpt-6-luna", "mini": "openai/gpt-4.1-mini",
          "deepseek": "deepseek/deepseek-v4.1-flash", "haiku": "anthropic/claude-haiku-5.5", "qwen": "qwen/qwen3.8-flash"}
JUDGES = {"opus": "anthropic/claude-opus-5.5", "gemini": "google/gemini-3.1-pro-preview", "sol": "openai/gpt-6-sol"}


def parallel(fn, items, threads=12):
    with ThreadPoolExecutor(threads) as ex:
        return list(ex.map(fn, items))


def read_jsonl(path):
    return [json.loads(line) for line in open(path, encoding="utf-8")] if os.path.exists(path) else []


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False)


def append_jsonl(path, rec, lock):
    with lock:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_stances(path):
    out = {}
    for r in read_jsonl(path):
        out.setdefault(r["qid"], {})[r["uuid"]] = r["stance"]
    return out
