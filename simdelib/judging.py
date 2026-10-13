import json
import re

from . import llm

DQI_FIELDS = ["justification", "common_good", "respect", "reciprocity"]
REASONING_JUDGES = {"anthropic/claude-opus-5.5", "google/gemini-3.1-pro-preview"}
EXTRA_TOKENS = 1500

DQI_SYSTEM = ("You are an expert coder applying the Discourse Quality Index (DQI, Steenbergen et al. 2003) "
              "to a Korean deliberation transcript. Score ONLY the target utterance. Respond in JSON.")
REPERTOIRE_SYSTEM = "You extract distinct, non-redundant argument reasons from a participant's statements. Respond in JSON."


def dqi_prompt(q, ctx, name, utt):
    return (f"[Issue] {q['topic']}\n[Position 1] {q['poleA']}\n[Position 2] {q['poleB']}\n"
            f"[Prior discussion]\n{ctx if ctx else '(none)'}\n[TARGET utterance by {name}]\n{utt}\n\n"
            "Score the TARGET only:\n"
            "- justification: 0 no reason, 1 one incomplete reason, 2 one complete reason with linkage, 3 sophisticated/multiple\n"
            "- common_good: 0 self or group interest, 1 neutral, 2 explicit common good / society\n"
            "- respect: 0 dismissive of others, 1 neutral, 2 explicit respect for others or counterarguments\n"
            "- reciprocity: 0 ignores others, 1 engages a specific prior point\n"
            '- novelty: "new" introduces a new argument, "build" elaborates a prior one, "repeat" restates\n'
            'JSON: {"justification":0,"common_good":0,"respect":0,"reciprocity":0,"novelty":"new"}')


def repertoire_prompt(q, name, utts):
    body = "\n".join(f"- {u}" for u in utts)
    return (f"[Issue] {q['topic']}\n[Position A] {q['poleA']}\n[Position B] {q['poleB']}\n"
            f"[Statements by {name}]\n{body}\n\n"
            "List the DISTINCT reasons this participant articulated supporting Position A, and supporting Position B. "
            "Count a reason once even if repeated; do not invent reasons not stated.\n"
            'JSON: {"for_A":["..."],"for_B":["..."]}')


def _json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


def _budget(judge, base):
    return base + (EXTRA_TOKENS if judge in REASONING_JUDGES else 0)


def score_utterance(judge, q, context, name, utterance, max_tokens=200):
    d = _json(llm.chat(judge, [{"role": "system", "content": DQI_SYSTEM},
                               {"role": "user", "content": dqi_prompt(q, context, name, utterance)}],
                       0.0, _budget(judge, max_tokens)))
    return {k: d.get(k) for k in DQI_FIELDS} if d else {}


def reasons(judge, q, name, utterances, max_tokens=400):
    d = _json(llm.chat(judge, [{"role": "system", "content": REPERTOIRE_SYSTEM},
                               {"role": "user", "content": repertoire_prompt(q, name, utterances)}],
                       0.0, _budget(judge, max_tokens)))
    return (d.get("for_A", []) or [], d.get("for_B", []) or []) if d else None
