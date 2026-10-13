import argparse
import json
import os

from simdelib import llm, prompts
from simdelib.personas import load_us_pool, us_system_prompt
from simdelib.questions import QUESTIONS_USA
from simdelib.survey import ask, classify, field, first_position, ordered
from experiments._common import MODELS, parallel

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
a = ap.parse_args()


def run(job):
    p, q = job
    first = first_position(p["uuid"], q["id"])
    text = ask(MODELS[a.model], us_system_prompt(p), prompts.forced_choice_us(q["topic"], *ordered(q, first)), 0.0, 80)
    s = classify(field(text, "choice"), q)
    return None if s is None else {"uuid": p["uuid"], "qid": q["id"], "stance": s}


rows = parallel(run, [(p, q) for q in QUESTIONS_USA.values() for p in load_us_pool()])
out = f"results/survey_us/{a.model}.jsonl"
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as f:
    f.writelines(json.dumps(r) + "\n" for r in rows if r is not None)
print(out, llm.report())
