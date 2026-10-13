import argparse
import threading

from simdelib import llm
from simdelib.deliberation import debate, disjoint_rooms, matched_side
from simdelib.personas import load_pool
from simdelib.questions import ISSUES, QUESTIONS
from experiments._common import MODELS, append_jsonl, load_stances, parallel, read_jsonl

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
ap.add_argument("--threads", type=int, default=12)
a = ap.parse_args()
M = MODELS[a.model]
pool = load_pool()
byid = {p["uuid"]: p for p in pool}
stances = load_stances(f"results/survey/{a.model}.jsonl")
out = f"results/anchoring_grid/{a.model}.jsonl"
done = {(r["issue"], r["seed"], r["pool"], r["conn"]) for r in read_jsonl(out)}

jobs = []
for k, qid in enumerate(ISSUES):
    chosen = ([u for u in stances[qid] if stances[qid][u] == 1], [u for u in stances[qid] if stances[qid][u] == -1])
    matched = ([p["uuid"] for p in pool if matched_side(p, qid) > 0], [p["uuid"] for p in pool if matched_side(p, qid) < 0])
    for position, (side_a, side_b), base in (("chosen", chosen, 5000), ("matched", matched, 6000)):
        for ids, start, seed in disjoint_rooms(side_a, side_b, 6, base + k * 50):
            for conn in ("none", "cue", "opening"):
                if (qid, seed, position, conn) not in done:
                    jobs.append((qid, ids, start, seed, conn, position))
lock = threading.Lock()


def run(job):
    qid, ids, start, seed, conn, position = job
    d = debate(M, [byid[u] for u in ids], QUESTIONS[qid], qid, seed, start, {"none": "none", "cue": "side", "opening": "opening"}[conn], probe=True)
    append_jsonl(out, {"issue": qid, "seed": seed, "pool": position, "conn": conn, "ids": ids, **d}, lock)


parallel(run, jobs, a.threads)
print(out, llm.report())
