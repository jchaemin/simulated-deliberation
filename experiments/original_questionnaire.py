import argparse

from simdelib import llm
from simdelib import questionnaire as OQ
from simdelib.personas import load_pool
from experiments._common import MODELS, parallel, write_json

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
a = ap.parse_args()
M = MODELS[a.model]
pool = load_pool()

jobs = []
for block in (OQ.ENV, OQ.BIRTH):
    for k, qid in enumerate(block):
        for ai, arm in enumerate("FR"):
            for i, p in enumerate(pool):
                jobs.append((qid, arm, p, 1 + k * 1_000_000 + ai * 100_000 + i))
if a.model == "mini":
    jobs = [j for j in jobs if j[0] in ("env2", "env3", "env4") and j[1] == "F"]


def run(job):
    qid, arm, p, seed = job
    body, meta = OQ.build(qid, arm, p["uuid"])
    for max_tokens in (300, 700):
        text = llm.chat(M, [{"role": "system", "content": OQ.system_prompt(p)}, {"role": "user", "content": body}],
                        0.0, max_tokens, seed=seed)
        try:
            answer = OQ.parse(qid, text, meta)
        except Exception:
            continue
        return {"qid": qid, "arm": arm, "uuid": p["uuid"], **answer}
    return None


records = parallel(run, jobs, 48)
write_json(f"results/original_questionnaire/{a.model}.json",
           {"model": M, "records": [r for r in records if r is not None], "failed": sum(r is None for r in records)})
print(llm.report())
