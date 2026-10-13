import itertools

import numpy as np

from simdelib.stats import read_json, read_jsonl, rnd

DIMS = ["justification", "common_good", "respect", "reciprocity"]
CATEGORIES = {"justification": 4, "common_good": 3, "respect": 3, "reciprocity": 2}
J = {j: read_json(f"results/discourse/sol_{j}.json") for j in ("opus", "gemini", "sol")}


def mean(judge, cond, dim, rnd=None):
    return np.mean([x[dim] for x in J[judge] if x["kind"] == "dqi" and x["cond"] == cond
                    and (rnd is None or x["round"] == rnd) and isinstance(x.get(dim), (int, float))])


def reasons(judge, cond, when):
    return np.mean([len(x["A"]) + len(x["B"]) for x in J[judge] if x["kind"] == "rep" and x["cond"] == cond and x["tp"] == when])


def both_sides(judge):
    return np.mean([bool(x["A"]) and bool(x["B"]) for x in J[judge] if x["kind"] == "rep" and x["cond"] == "debate" and x["tp"] == "final"])


def weighted_kappa(a, b, k):
    observed = np.zeros((k, k))
    for x, y in zip(a, b):
        observed[x, y] += 1
    w = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)]) / (k - 1) ** 2
    expected = np.outer(observed.sum(1), observed.sum(0)) / observed.sum()
    return 1 - (w * observed).sum() / (w * expected).sum()


print("Table 3: DQI of GPT-6-sol debates by round, mean of Claude-Opus-5.5 and Gemini-3.1-pro")
for d in DIMS:
    print(f"  {d:14} " + "  ".join(f"{rnd((mean('opus', 'debate', d, r) + mean('gemini', 'debate', d, r)) / 2, 2)}" for r in (1, 2, 3)))
print("\nAppendix G, by judge (round 1 / round 3):")
for j in J:
    print(f"  {j:7} " + "  ".join(f"{d[:5]} {rnd(mean(j, 'debate', d, 1), 2)}/{rnd(mean(j, 'debate', d, 3), 2)}" for d in DIMS)
          + f"  reasons {rnd(reasons(j, 'debate', 'first'), 1)}/{rnd(reasons(j, 'debate', 'final'), 1)}  both sides {rnd(100 * both_sides(j), 0)}%")
print(f"  GPT-6-sol on its own justification (all rounds) {rnd(mean('sol', 'debate', 'justification'), 2)}; "
      f"independent judges {rnd((mean('opus', 'debate', 'justification') + mean('gemini', 'debate', 'justification')) / 2, 2)}")
print("  Debate / monologue, all rounds:")
for j in ("opus", "gemini"):
    print(f"    {j:7} " + "  ".join(f"{d[:5]} {rnd(mean(j, 'debate', d), 2)}/{rnd(mean(j, 'mono', d), 2)}" for d in DIMS[:3]))
print("    mean    " + "  ".join(f"{d[:5]} {rnd((mean('opus', 'debate', d) + mean('gemini', 'debate', d)) / 2, 2)}/"
                               f"{rnd((mean('opus', 'mono', d) + mean('gemini', 'mono', d)) / 2, 2)}" for d in DIMS[:3]))
print("  Weighted kappa on debate turns:")
scored = {j: [x for x in J[j] if x["kind"] == "dqi" and x["cond"] == "debate"] for j in J}
for a, b in itertools.combinations(J, 2):
    ks = []
    for d in DIMS:
        pairs = [(x[d], y[d]) for x, y in zip(scored[a], scored[b]) if isinstance(x.get(d), int) and isinstance(y.get(d), int)]
        ks.append(weighted_kappa([p for p, _ in pairs], [q for _, q in pairs], CATEGORIES[d]))
    print(f"    {a}-{b}: " + "  ".join(f"{d[:5]} {rnd(k, 2)}" for d, k in zip(DIMS, ks)))

print("\nTable 4 and Appendix H: live and frozen rooms (mean of the two judges; DQI over rounds 1-3)")
for room in ("natural", "opening_matched", "cue_chosen", "cue_matched"):
    judged = {j: read_json(f"results/frozen_rooms/{room}_{j}.json") for j in ("opus", "gemini")}
    dqi = [np.mean([np.mean([x[d] for x in judged[j]["dqi"] if isinstance(x.get(d), (int, float))])
                    for j in judged]) for d in DIMS]
    first = np.mean([np.mean([x["nA"] + x["nB"] for x in judged[j]["repertoire"] if x["tp"] == "first"]) for j in judged])
    final = np.mean([np.mean([x["nA"] + x["nB"] for x in judged[j]["repertoire"] if x["tp"] == "final"]) for j in judged])
    both = np.mean([np.mean([x["nA"] > 0 and x["nB"] > 0 for x in judged[j]["repertoire"] if x["tp"] == "final"]) for j in judged])
    rooms = read_jsonl(f"results/frozen_rooms/{room}.jsonl")
    moved = np.mean([s[0] != s[-1] for r in rooms for s in r["included"].values()])
    print(f"  {room:16} moved {rnd(100 * moved, 0)}%  " + "  ".join(f"{d[:5]} {rnd(v, 2)}" for d, v in zip(DIMS, dqi))
          + f"  reasons {rnd(first, 1)}->{rnd(final, 1)}  both sides {rnd(100 * both, 0)}%")
