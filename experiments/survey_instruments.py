import argparse
import json
import os
import random

from simdelib import llm, prompts
from simdelib.personas import demographics_prompt, load_pool, system_prompt
from simdelib.questions import ISSUES, QUESTIONS
from simdelib.survey import ask, classify, field, first_position, ordered, stable_hash
from experiments._common import MODELS, parallel

ap = argparse.ArgumentParser()
ap.add_argument("--instrument", required=True,
                choices=["demographics", "neutral", "labeled", "labeled_swapped", "two_ratings", "temperature1"])
ap.add_argument("--model", default="sol", choices=MODELS)
a = ap.parse_args()
M = MODELS[a.model]
pool = load_pool()


def demographics(p, q, qid):
    first = random.Random(stable_hash(p["uuid"], qid, "bare")).choice(["A", "B"])
    text = ask(M, demographics_prompt(p), prompts.forced_choice(q["topic"], *ordered(q, first)), 0.7, 80)
    s = classify(field(text, "choice"), q, tie_unclassified=False)
    return None if s is None else {"uuid": p["uuid"], "qid": qid, "stance": s}


def neutral(p, q, qid):
    first = random.Random(stable_hash(p["uuid"], qid, "neutral")).choice(["A", "B"])
    choice = field(ask(M, system_prompt(p), prompts.neutral_option(q["topic"], *ordered(q, first)), 0.7, 80), "choice")
    s = classify(choice, q, neutral=("중립",), tie_unclassified=False)
    return None if s is None else {"uuid": p["uuid"], "qid": qid, "stance": s}


def labeled(p, q, qid, swapped=False):
    options = (q["poleB"], q["poleA"]) if swapped else (q["poleA"], q["poleB"])
    choice = field(ask(M, system_prompt(p), prompts.labeled_choice(q["topic"], *options), 0.7, 30), "choice", r'"?(A|B|중립)')
    return None if choice is None else {"uuid": p["uuid"], "qid": qid, "choice": choice}


def two_ratings(p, q, qid, side):
    position = q["poleA"] if side == "A" else q["poleB"]
    v = field(ask(M, system_prompt(p), prompts.support_rating(q["topic"], position), 0.7, 25), "support", r"([012])")
    return None if v is None else {"uuid": p["uuid"], "qid": qid, "side": side, "support": int(v)}


def temperature1(p, q, qid):
    text = ask(M, system_prompt(p), prompts.forced_choice(q["topic"], *ordered(q, first_position(p["uuid"], qid))), 1.0, 80)
    return {"uuid": p["uuid"], "qid": qid, "s": classify(field(text, "choice"), q)}


jobs = [(p, qid) for qid in ISSUES for p in pool]
if a.instrument == "demographics":
    rows = parallel(lambda j: demographics(j[0], QUESTIONS[j[1]], j[1]), jobs, 16)
elif a.instrument == "neutral":
    rows = parallel(lambda j: neutral(j[0], QUESTIONS[j[1]], j[1]), jobs, 16)
elif a.instrument in ("labeled", "labeled_swapped"):
    rows = parallel(lambda j: labeled(j[0], QUESTIONS[j[1]], j[1], a.instrument == "labeled_swapped"), jobs, 16)
elif a.instrument == "two_ratings":
    rows = parallel(lambda j: two_ratings(j[0], QUESTIONS[j[1]], j[1], j[2]), [(p, q, s) for p, q in jobs for s in "AB"], 16)
else:
    rows = parallel(lambda j: temperature1(j[0], QUESTIONS[j[1]], j[1]), [j for j in jobs for _ in range(5)], 16)
out = f"results/survey_instruments/{a.model}_{a.instrument}.jsonl"
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows if r is not None)
print(out, llm.report())
