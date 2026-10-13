import argparse
import collections
import random

from simdelib import llm, judging
from simdelib.questions import QUESTIONS
from experiments._common import JUDGES, MODELS, parallel, read_jsonl, write_json

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="sol", choices=MODELS)
ap.add_argument("--judge", required=True, choices=JUDGES)
a = ap.parse_args()
J = JUDGES[a.judge]
by_question = collections.defaultdict(list)
for r in read_jsonl(f"results/debates/{a.model}.jsonl"):
    by_question[r["issue"]].append(r)
rooms = [r for qid in by_question for r in random.Random(1).sample(by_question[qid], min(5, len(by_question[qid])))]

jobs = []
for k, r in enumerate(rooms):
    transcript = r["debate"]["transcript"]
    for t, (name, utt) in enumerate(transcript):
        jobs.append(("dqi", "debate", k, t // 6 + 1, name, utt, "\n".join(f"{n}: {u}" for n, u in transcript[:t])))
    if a.judge != "sol":
        for seat, turns in r["mono"]["own"].items():
            for t, utt in enumerate(turns):
                jobs.append(("dqi", "mono", k, t + 1, f"agent{seat}", utt, "\n".join(turns[:t])))
    by_speaker = collections.defaultdict(list)
    for name, utt in transcript:
        by_speaker[name].append(utt)
    for name, utts in by_speaker.items():
        jobs += [("rep", "debate", k, "first", name, utts[:1], None), ("rep", "debate", k, "final", name, utts, None)]


def run(job):
    kind, cond, k, when, name, x, context = job
    q = QUESTIONS[rooms[k]["issue"]]
    if kind == "dqi":
        scores = judging.score_utterance(J, q, context, name, x)
        fields = judging.DQI_FIELDS if cond == "debate" else [f for f in judging.DQI_FIELDS if f != "reciprocity"]
        return {"kind": "dqi", "cond": cond, "room": k, "round": when, **{f: scores.get(f) for f in fields}}
    found = judging.reasons(J, q, str(name), x) or ([], [])
    return {"kind": "rep", "cond": cond, "room": k, "tp": when, "agent": str(name), "A": found[0], "B": found[1]}


write_json(f"results/discourse/{a.model}_{a.judge}.json", parallel(run, jobs, 10))
print(llm.report())
