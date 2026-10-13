import collections
import json

import numpy as np

from simdelib import questionnaire as OQ
from simdelib.kei import age_band, respondents
from simdelib.personas import load_pool
from simdelib.stats import read_json, read_jsonl, rnd

pool = {p["uuid"]: p for p in load_pool()}
humans = respondents()


def persona_records(model, arm):
    out = collections.defaultdict(dict)
    for r in read_json(f"results/original_questionnaire/{model}.json")["records"]:
        if r["arm"] == arm:
            out[r["uuid"]][r["qid"]] = r
    return out


def share_recoded(codes):
    v = [c for c in codes if c in ("A", "B")]
    return 100 * sum(c == "A" for c in v) / len(v) if v else None


def share_renormalized(picks, qid):
    s = OQ.SPEC[qid]
    return OQ.renorm_share(100 * np.mean([s["a"] in p for p in picks]), 100 * np.mean([s["b"] in p for p in picks]))


def a_share(records, qid):
    rows = [qs[qid] for qs in records.values() if qid in qs]
    if OQ.SPEC[qid].get("renorm"):
        return share_renormalized([(r["first"], r["second"]) for r in rows], qid)
    return share_recoded([OQ.recode(qid, r) for r in rows])


def same_pair(items):
    cells = collections.defaultdict(list)
    for cell, pair in items:
        cells[cell].append(pair)
    num = den = 0
    for pairs in cells.values():
        n = len(pairs)
        if n >= 2:
            num += sum(k * (k - 1) / 2 for k in collections.Counter(pairs).values())
            den += n * (n - 1) / 2
    used = collections.Counter(p for _, p in items)
    return {"same_pair_pct": 100 * num / den, "pairs_used": len(used)}


def persona_cell(p):
    return (p["sex"], age_band(p["age"]), p["edu4"], p["region_group"])


def top_two(records, qid):
    picks = [frozenset((qs[qid]["first"], qs[qid]["second"])) for qs in records.values() if qid in qs]
    s = OQ.SPEC[qid]
    profile = {i: 100 * sum(i in p for p in picks) / len(picks) for i in range(1, s["n_opt"] + 1)}
    either = 100 * sum(s["a"] in p or s["b"] in p for p in picks) / len(picks)
    return profile, either


out = {}
for model in ("sol", "mini"):
    F = persona_records(model, "F")
    R = persona_records(model, "R") if model == "sol" else None
    res = {"within_cell": {}, "top_two": {}} if model == "sol" else {"within_cell": {}}
    if model == "sol":
        forced = collections.defaultdict(dict)
        for r in read_jsonl("results/survey/sol.jsonl"):
            forced[r["qid"]][r["uuid"]] = "A" if r["stance"] == 1 else "B"
        table = {}
        for q in OQ.ENV + OQ.BIRTH:
            human = share_recoded([h[q] for h in humans]) if q in OQ.ENV else OQ.HUMAN_BIRTH[q]
            table[q] = {"human": human, "forced_choice": share_recoded(forced[q].values()),
                        "original_order": a_share(F, q), "shuffled": a_share(R, q)}
        items = [q for q in OQ.ENV + OQ.BIRTH if q != "birth4"]
        table["mean_gap_7_items"] = {k: float(np.mean([abs(table[q][k] - table[q]["human"]) for q in items]))
                                     for k in ("forced_choice", "original_order", "shuffled")}
        res["a_shares"] = table
    for q in ("env2", "env3", "env4"):
        res["within_cell"][q] = {"persona": same_pair([(persona_cell(pool[u]), frozenset((qs[q]["first"], qs[q]["second"])))
                                                       for u, qs in F.items() if q in qs]),
                                 "human": same_pair([((h["sex"], h["age_band"], h["edu4"], h["region7"]), frozenset(h[q + "_picks"]))
                                                     for h in humans])}
    if model == "sol":
        profile, either = top_two(F, "birth4")
        res["top_two"]["birth4"] = {"either_position_pct": either,
                                    "dedicated_supply_pct": {"persona": profile[5], "human": OQ.human_option_shares("birth4")[4]}}
    out[model] = res
json.dump(out, open("results/derived/original_questionnaire.json", "w"), ensure_ascii=False, indent=1)
t = out["sol"]["a_shares"]
print("A-share (%): human / forced choice / original order / shuffled")
for q in OQ.ENV + OQ.BIRTH:
    print(f"  {q:7} " + " / ".join(f"{rnd(t[q][k], 0)}" for k in ("human", "forced_choice", "original_order", "shuffled")))
print("  mean absolute gap, 7 items: " + ", ".join(f"{k} {rnd(v, 1)}" for k, v in t["mean_gap_7_items"].items()))
for m in out:
    print(f"Same pair within a cell ({m}): " + ", ".join(
        f"{q} persona {rnd(v['persona']['same_pair_pct'], 1)}% human {rnd(v['human']['same_pair_pct'], 1)}% "
        f"(pairs {v['persona']['pairs_used']}/{v['human']['pairs_used']})" for q, v in out[m]["within_cell"].items()))
hous = out["sol"]["top_two"]["birth4"]
print(f"Housing: personas with a benchmark position in their top two {rnd(hous['either_position_pct'], 1)}%; "
      f"dedicated housing supply in the top two, personas {rnd(hous['dedicated_supply_pct']['persona'], 1)}% / humans {rnd(hous['dedicated_supply_pct']['human'], 1)}%")
