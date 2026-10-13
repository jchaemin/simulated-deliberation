import collections
import json
import os

import numpy as np

from simdelib.stats import composition, n_changed, on_a, r1, read_json, read_jsonl, rint, rnd

MODELS = {"sol": "GPT-6-sol", "luna": "GPT-6-luna", "mini": "GPT-4.1-mini",
          "deepseek": "DeepSeek-V4.1", "haiku": "Claude-Haiku-5.5", "qwen": "Qwen-3.8-flash"}
rooms = {m: read_jsonl(f"results/debates/{m}.jsonl") for m in MODELS}


def key(r):
    return r["issue"], r["seed"]


rng = np.random.default_rng(0)


def interval(x, lo, hi):
    boot = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(4000)]
    return np.percentile(boot, lo), np.percentile(boot, hi)


def skip(x):
    interval(x, 2.5, 97.5)


print("Debate vs sealed monologue: final agents on A (debate minus monologue) with its 90% interval; % changing side")
print("in debate / monologue / re-ask")
for m, name in MODELS.items():
    R = rooms[m]
    reask = {key(x): x for x in read_jsonl(f"results/debates/{m}_reask.jsonl")}
    diff = np.array([on_a(r["debate"]["included"]) - on_a(r["mono"]["sides"]) for r in R])
    skip(diff)
    lo90, hi90 = interval(diff, 5, 95)
    by_q = collections.defaultdict(list)
    for r, x in zip(R, diff):
        by_q[r["issue"]].append(x)
    for xs in by_q.values():
        if len(xs) > 1:
            skip(np.array(xs))
    moved = [100 * np.mean([n_changed(f(r)) for r in R]) / 6 for f in
             (lambda r: r["debate"]["included"], lambda r: r["mono"]["sides"], lambda r: reask[key(r)]["sides"])]
    print(f"  {name:17} {len(R)} rooms, {len(by_q)} questions: {rnd(diff.mean(), 2, True)} [{rnd(lo90, 2, True)}, {rnd(hi90, 2, True)}];  "
          f"moved {rnd(moved[0], 0)} / {rnd(moved[1], 0)} / {rnd(moved[2], 0)}%")

print("\nPooled difference without questions that reuse minority-side personas:")
for m in MODELS:
    distinct = collections.defaultdict(lambda: [set(), set()])
    for r in rooms[m]:
        for i, u in enumerate(r["ids"]):
            distinct[r["issue"]][0 if r["debate"]["included"][str(i)][0] == 1 else 1].add(u)
    keep = {q for q, (a, b) in distinct.items() if min(len(a), len(b)) >= 30}
    print(f"  {m}: {rnd(np.mean([on_a(r['debate']['included']) - on_a(r['mono']['sides']) for r in rooms[m] if r['issue'] in keep]), 2, True)}")

print("\nFigure 3 and Table 17: final agents on A by question, debate / monologue")
for m, name in MODELS.items():
    by_q = collections.defaultdict(list)
    for r in rooms[m]:
        by_q[r["issue"]].append((on_a(r["debate"]["included"]), on_a(r["mono"]["sides"])))
    print(f"  {name:17} " + "  ".join(f"{q} {rnd(np.mean([d for d, _ in v]), 2)}/{rnd(np.mean([s for _, s in v]), 2)}" for q, v in by_q.items()))

rng_excess = np.random.default_rng(0)
excess = {}
print("\nExcess of debate-vs-monologue over monologue-vs-rerun differences:")
for m in MODELS:
    rerun = {key(x): x for x in read_jsonl(f"results/debates/{m}_monologue_rerun.jsonl")}
    by_q = collections.defaultdict(list)
    for r in rooms[m]:
        D, M, M2 = r["debate"]["included"], r["mono"]["sides"], rerun[key(r)]["mono"]["sides"]
        by_q[r["issue"]].append((abs(on_a(D) - on_a(M)) - abs(on_a(M) - on_a(M2)),
                                 np.mean([D[str(i)][-1] != M[str(i)][-1] for i in range(6)])
                                 - np.mean([M[str(i)][-1] != M2[str(i)][-1] for i in range(6)])))
    res = {}
    for q, v in list(by_q.items()) + [("pooled", [x for v in by_q.values() for x in v])]:
        v = np.array(v)
        boot = [v[rng_excess.integers(0, len(v), len(v))].mean(0) for _ in range(4000)]
        lo, hi = np.percentile(boot, 2.5, 0), np.percentile(boot, 97.5, 0)
        res[q] = dict(room=float(rnd(v[:, 0].mean(), 2)), room_ci=[float(rnd(lo[0], 2)), float(rnd(hi[0], 2))],
                      agent=float(rnd(100 * v[:, 1].mean(), 1)), agent_ci=[float(rnd(100 * lo[1], 1)), float(rnd(100 * hi[1], 1))], n=len(v))
    excess[m] = {q: {k: v for k, v in r.items() if not k.startswith("agent") or (m == "sol" and q == "pooled")} for q, r in res.items()}
    print(f"  {m}: room {res['pooled']['room']} {res['pooled']['room_ci']}"
          + (f", agent {res['pooled']['agent']} {res['pooled']['agent_ci']}" if m == "sol" else "")
          + f"; questions with room interval above 0: {[q for q in by_q if res[q]['room_ci'][0] > 0]}")
os.makedirs("results/derived", exist_ok=True)
json.dump(excess, open("results/derived/excess.json", "w"), indent=1)

print("\nStarting composition (agents on A of 6): population / personas / no persona / all-A / balanced / all-B")
for m, f in (("sol", "sol_figure2"), ("luna", "luna"), ("mini", "mini")):
    for q, s in composition(m, f"results/composition/{f}.json").items():
        print(f"  {f:11} {q:7} " + " / ".join(r1(s[k]) if k in s else "-" for k in ("population", "personas", "no_persona", "6A", "3-3", "6B")))

CELLS = [(p, c) for p in ("chosen", "matched") for c in ("none", "cue", "opening")]
lines = []
print("\nAnchoring grid: % changing side (rows: models; columns: chosen/matched x none/cue/opening; then own turns removed)")
for m, name in MODELS.items():
    inc, exc, n_rooms = collections.defaultdict(list), collections.defaultdict(list), collections.Counter()
    for r in read_jsonl(f"results/anchoring_grid/{m}.jsonl"):
        k = (r["pool"], r["conn"])
        n_rooms[k] += 1
        inc[k] += [r["included"][i][0] != r["included"][i][-1] for i in r["included"]]
        exc[k] += [r["excluded"][i][0] != r["excluded"][i][-1] for i in r["excluded"]]
    main = [rint(100 * np.mean(inc[k])) for k in CELLS]
    probe = [rint(100 * np.mean(exc[k])) for k in (("chosen", "cue"), ("chosen", "opening"), ("matched", "cue"), ("matched", "opening"))]
    line = f"{name} & {sum(n_rooms.values())} & " + " & ".join(map(str, main + probe)) + " \\\\"
    lines.append(line)
    print("  " + line)
os.makedirs("tables", exist_ok=True)
open("tables/anchoring_grid_rows.tex", "w").write("\n".join(lines) + "\n")

print("\nAnchoring decomposition (Appendix F): % ending on the side other than the assigned one")
moved = collections.defaultdict(list)
for r in read_json("results/anchoring_decomposition/sol.json"):
    moved[r["arm"]] += [s[-1] != r["assigned"][int(i)] for i, s in r["sides"].items()]
print("  " + ", ".join(f"{arm} {rnd(100 * np.mean(v), 0)}%" for arm, v in moved.items()))
