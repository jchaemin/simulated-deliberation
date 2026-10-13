import argparse
import json

from simdelib import llm
from simdelib.deliberation import monologue, survey
from simdelib.personas import load_pool
from simdelib.questions import QUESTIONS
from experiments._common import MODELS, parallel, read_jsonl

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
ap.add_argument("--control", required=True, choices=["monologue_rerun", "reask"])
a = ap.parse_args()
M = MODELS[a.model]
byid = {p["uuid"]: p for p in load_pool()}
rooms = read_jsonl(f"results/debates/{a.model}.jsonl")
start = {i: (1 if i < 3 else -1) for i in range(6)}

if a.control == "monologue_rerun":
    out = parallel(lambda r: {"issue": r["issue"], "seed": r["seed"],
                              "mono": {"sides": monologue(M, [byid[u] for u in r["ids"]], QUESTIONS[r["issue"]], r["issue"], start)["sides"]}},
                   rooms, 10)
else:
    jobs = [(k, i) for k in range(len(rooms)) for i in range(6) for _ in range(3)]
    answers = parallel(lambda j: survey(M, byid[rooms[j[0]]["ids"][j[1]]], QUESTIONS[rooms[j[0]]["issue"]], rooms[j[0]]["issue"]), jobs)
    out = []
    for k, r in enumerate(rooms):
        sides = {str(i): [start[i]] + [s for (kk, ii), s in zip(jobs, answers) if (kk, ii) == (k, i)] for i in range(6)}
        out.append({"issue": r["issue"], "seed": r["seed"], "sides": sides})
path = f"results/debates/{a.model}_{a.control}.jsonl"
open(path, "w").write("\n".join(json.dumps(x, ensure_ascii=False) for x in out))
print(path, llm.report())
