import collections
import itertools
import json

import numpy as np

from simdelib.kei import respondents
from simdelib.personas import load_pool
from simdelib.questions import BENCH
from simdelib.stats import read_jsonl

QUESTIONS = ["env1", "env2", "env3", "env4"]
AXES = ["sex", "age_band", "edu4", "region_group"]
pool = {p["uuid"]: p for p in load_pool()}
cell_of = lambda rec: tuple(rec[a] for a in AXES)
humans = respondents()
personas = collections.defaultdict(dict)
for r in read_jsonl("results/survey/sol.jsonl"):
    if r["qid"] in QUESTIONS:
        personas[r["qid"]][r["uuid"]] = 1.0 if r["stance"] == 1 else 0.0

rows = []
for q in QUESTIONS:
    h_n, h_a, p_n, p_a = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    for h in humans:
        if h[q] in ("A", "B"):
            h_n[cell_of(h)] += 1
            h_a[cell_of(h)] += h[q] == "A"
    for u, v in personas[q].items():
        p_n[cell_of(pool[u])] += 1
        p_a[cell_of(pool[u])] += v
    for k, axis in enumerate(AXES):
        for level in BENCH["env1"][axis]:
            h_cells = [c for c in h_n if c[k] == level]
            p_cells = [c for c in p_n if c[k] == level]
            weight = {c: h_n[c] for c in h_cells if c in p_n}
            total = sum(weight.values())
            rows.append(dict(q=q, axis=axis, level=level, bench=BENCH[q][axis][level],
                             human=100 * sum(h_a[c] for c in h_cells) / sum(h_n[c] for c in h_cells),
                             persona_raw=100 * sum(p_a[c] for c in p_cells) / sum(p_n[c] for c in p_cells),
                             persona_reweighted=100 * sum(w / total * p_a[c] / p_n[c] for c, w in weight.items()),
                             dropped_human_weight=1 - total / sum(h_n[c] for c in h_cells)))


def directions(col):
    sign = lambda x: (x > 1e-9) - (x < -1e-9)
    out = collections.Counter()
    for q, axis in itertools.product(QUESTIONS, AXES):
        for x, y in itertools.combinations([r for r in rows if r["q"] == q and r["axis"] == axis], 2):
            dh = sign(x["human"] - y["human"])
            if dh:
                dp = sign(x[col] - y[col])
                out["tie" if dp == 0 else "match" if dp == dh else "reverse"] += 1
    return dict(out)


summary = {"groups": len(rows),
           "gap_raw": float(np.mean([abs(r["persona_raw"] - r["human"]) for r in rows])),
           "gap_reweighted": float(np.mean([abs(r["persona_reweighted"] - r["human"]) for r in rows])),
           "directions_raw": {k: v for k, v in directions("persona_raw").items() if k != "tie"},
           "directions_reweighted": {k: v for k, v in directions("persona_reweighted").items() if k != "tie"}}
json.dump({"summary": summary}, open("results/derived/reweighting.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
