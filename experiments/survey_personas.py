import argparse
import json
import os

from simdelib import llm
from simdelib.deliberation import survey
from simdelib.personas import load_pool
from simdelib.questions import ISSUES, QUESTIONS
from experiments._common import MODELS, load_stances, parallel

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
ap.add_argument("--threads", type=int, default=10)
a = ap.parse_args()
out = f"results/survey/{a.model}.jsonl"
done = load_stances(out)
todo = [(p, qid) for qid in ISSUES for p in load_pool() if p["uuid"] not in done.get(qid, {})]
answers = parallel(lambda job: survey(MODELS[a.model], job[0], QUESTIONS[job[1]], job[1]), todo, a.threads)
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "a") as f:
    f.writelines(json.dumps({"uuid": p["uuid"], "qid": qid, "stance": s}) + "\n" for (p, qid), s in zip(todo, answers) if s is not None)
print(out, llm.report())
