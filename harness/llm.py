"""Shared LLM runtime: the chat client, the persona system prompt, and the
JSON-constrained elicitation helper. Question definitions live in
questions_kr.py / questions_us.py; the engine in core.py."""

import json, re
from llm_client import chat

MODEL = "openai/gpt-4.1-mini"  # default; every runner sets this explicitly

def persona_system(p):
    # Minimal: persona only, plus the JSON-format requirement (needed to parse).
    return (
        f"당신은 아래 프로필의 대한민국 시민입니다.\n"
        f"[프로필] {p['age']}세 {p['sex']} · {p['province']} {p['district']} 거주 · "
        f"학력 {p['education_level']} · 직업 {p['occupation']} · {p['family_type']}\n"
        f"[배경] {p['persona']} {p.get('professional_persona','')} {p.get('family_persona','')}\n\n"
        f"답변은 항상 지정된 JSON 형식으로만 작성하세요."
    )

def _parse_json(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError(f"no json in: {txt[:200]}")
    return json.loads(m.group(0))

def ask_json(system, user, temperature=0.7, max_tokens=700, require_stance=False):
    txt = chat(MODEL, [{"role": "system", "content": system},
                       {"role": "user", "content": user}],
               temperature=temperature, max_tokens=max_tokens,
               response_format={"type": "json_object"})
    if not isinstance(txt, str) or not txt.strip():
        raise RuntimeError("empty content (reasoning model consuming all tokens?)")
    d = _parse_json(txt)
    if d.get("stance", 0) is None:
        d.pop("stance")
    if require_stance and "stance" not in d:
        raise ValueError(f"survey reply lacks stance: {txt[:120]}")
    d["stance"] = max(-2, min(2, int(round(float(d.get("stance", 0))))))
    d["confidence"] = max(0, min(100, int(round(float(d.get("confidence", 50))))))
    return d

def _agent_name(p, ai):
    """Speaker name for the conversation history. Nemotron narratives open with
    the persona's name ("X씨는 ..."); fall back to a neutral label."""
    m = re.match(r"\s*([가-힣]{2,4})\s*씨는", p.get("persona", ""))
    return m.group(1) if m else f"참여자{ai+1}"
