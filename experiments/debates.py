import argparse
import threading

from simdelib import llm
from simdelib.deliberation import balanced_rooms, debate, monologue
from simdelib.personas import load_pool
from simdelib.questions import ISSUES, QUESTIONS
from experiments._common import MODELS, append_jsonl, load_stances, parallel, read_jsonl

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
ap.add_argument("--rooms", type=int, default=20)
ap.add_argument("--threads", type=int, default=5)
a = ap.parse_args()
M = MODELS[a.model]
byid = {p["uuid"]: p for p in load_pool()}
stances = load_stances(f"results/survey/{a.model}.jsonl")
out = f"results/debates/{a.model}.jsonl"
done = {(r["issue"], r["seed"]) for r in read_jsonl(out)}

jobs = []
for k, qid in enumerate(ISSUES):
    side_a = [u for u, s in stances[qid].items() if s == 1]
    side_b = [u for u, s in stances[qid].items() if s == -1]
    if len(side_a) < 3 or len(side_b) < 3:
        continue
    for d, ids in enumerate(balanced_rooms(side_a, side_b, a.rooms, 7000 + k)):
        if (qid, 7000 + k * 100 + d) not in done:
            jobs.append((qid, ids, 7000 + k * 100 + d))
lock = threading.Lock()
start = {i: (1 if i < 3 else -1) for i in range(6)}


def run(job):
    qid, ids, seed = job
    panel, q = [byid[u] for u in ids], QUESTIONS[qid]
    append_jsonl(out, {"issue": qid, "seed": seed, "ids": ids, "model": M,
                       "debate": debate(M, panel, q, qid, seed, start), "mono": monologue(M, panel, q, qid, start)}, lock)


parallel(run, jobs, a.threads)
print(out, llm.report())
