import difflib
import hashlib
import json
import random
import re

from . import llm, prompts


def stable_hash(*parts):
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def first_position(uuid, qid, salt="nn"):
    return random.Random(stable_hash(uuid, qid, salt)).choice(["A", "B"])


def ordered(q, first):
    return (q["poleA"], q["poleB"]) if first == "A" else (q["poleB"], q["poleA"])


def classify(choice, q, neutral=("중립", "모르"), tie_unclassified=True):
    if choice is None:
        return None
    if any(w in choice for w in neutral):
        return 0
    head_a, head_b = q["poleA"].split("(")[0].strip(), q["poleB"].split("(")[0].strip()
    ra = difflib.SequenceMatcher(None, choice, q["poleA"]).ratio() + difflib.SequenceMatcher(None, choice, head_a).ratio()
    rb = difflib.SequenceMatcher(None, choice, q["poleB"]).ratio() + difflib.SequenceMatcher(None, choice, head_b).ratio()
    if max(ra, rb) < 0.4 or (tie_unclassified and ra == rb):
        return None
    return 1 if ra > rb else -1


def field(text, key, pattern=r'"([^"]*)"'):
    m = re.search(rf'"{key}"\s*:\s*' + pattern, text or "")
    return m.group(1) if m else None


def public_text(text):
    try:
        return json.loads(text).get("public", "")
    except Exception:
        m = re.search(r'"public"\s*:\s*"(.*?)"', text or "", re.S)
        return m.group(1) if m else "..."


def ask(model, system, user, temperature, max_tokens):
    return llm.chat(model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    temperature, max_tokens)


def stance(model, system, q, first, transcript=None, temperature=0.0):
    a, b = ordered(q, first)
    text = ask(model, system, prompts.forced_choice(q["topic"], a, b, transcript), temperature, 80)
    return classify(field(text, "choice"), q)
