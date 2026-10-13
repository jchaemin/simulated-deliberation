import argparse
import random

from simdelib import llm, prompts
from simdelib.deliberation import debate
from simdelib.personas import load_pool
from simdelib.questions import QUESTIONS
from simdelib.survey import classify, field, stable_hash
from experiments._common import MODELS, load_stances, parallel, write_json

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
ap.add_argument("--questions", required=True, choices=["figure2", "appendix"])
a = ap.parse_args()
M = MODELS[a.model]
APPENDIX = a.questions == "appendix"
qids = ["env4", "birth2", "birth4"] if APPENDIX else ["env1", "env2", "env3", "env4", "birth2", "birth3", "birth4"]
byid = {p["uuid"]: p for p in load_pool()}
stances = load_stances(f"results/survey/{a.model}.jsonl")

jobs = []
for qid in qids:
    for comp, side, base in (("6A", 1, 7000), ("6B", -1, 7100)):
        ids = [u for u in stances[qid] if stances[qid][u] == side]
        random.Random(stable_hash(qid, "6v0", a.model)).shuffle(ids)
        for d in range(min(4, len(ids) // 6)):
            jobs.append((qid, comp, ids[6 * d:6 * d + 6], base + d, side))


def room(job):
    qid, comp, ids, seed, side = job
    d = debate(M, [byid[u] for u in ids], QUESTIONS[qid], qid, seed, {i: side for i in range(6)})
    return {"issue": qid, "comp": comp, "ids": ids, "included": d["included"], "transcript": d["transcript"]}


def bare_model(job):
    qid, k = job
    q = QUESTIONS[qid]
    first, second = (q["poleA"], q["poleB"]) if k % 2 == 0 else (q["poleB"], q["poleA"])
    text = llm.chat(M, [{"role": "user", "content": prompts.forced_choice(q["topic"], first, second)}], 1.0, 80)
    return classify(field(text, "choice"), q)


rooms = parallel(room, jobs)
out = {"model": M, "rooms": rooms}
if APPENDIX:
    answers = parallel(bare_model, [(qid, k) for qid in qids for k in range(60)])
    out["no_persona"] = {qid: answers[60 * n:60 * n + 60] for n, qid in enumerate(qids)}
write_json(f"results/composition/{a.model}{'' if APPENDIX else '_figure2'}.json", out)
print(llm.report())
