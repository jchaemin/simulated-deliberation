import itertools
import json
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from .personas import group_of
from .questions import BENCH, ISSUES


def rnd(x, nd=0, sign=False):
    d = Decimal(repr(round(float(x), 9))).quantize(Decimal(1).scaleb(-nd), ROUND_HALF_UP)
    d = abs(d) if d == 0 else d
    return f"{d:+}" if sign else str(d)


def rint(x):
    return int(rnd(x))


def r1(x):
    return rnd(x, 1)


def read_jsonl(path):
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def read_json(path):
    return json.load(open(path, encoding="utf-8"))


def on_a(seats):
    return sum(1 for i in range(6) if seats[str(i)][-1] == 1)


def n_changed(seats):
    return sum(1 for i in range(6) if seats[str(i)][-1] != seats[str(i)][0])


def a_share(stances):
    v = [s for s in stances if s in (1, -1)]
    return 100 * sum(s == 1 for s in v) / len(v) if v else None


def benchmark_groups(qid):
    return [(axis, level) for axis in BENCH[qid] if axis != "overall" for level in BENCH[qid][axis]]


def group_shares(rows, byid, value=lambda r: r["stance"]):
    by_q = {}
    for r in rows:
        v = value(r)
        if v is not None:
            by_q.setdefault(r["qid"], []).append((r["uuid"], v))
    out = {}
    for qid in ISSUES:
        vals = by_q.get(qid, [])
        out[(qid, "overall")] = 100 * np.mean([w for _, w in vals])
        for axis, level in benchmark_groups(qid):
            g = [w for u, w in vals if group_of(byid[u], axis) == level]
            if g:
                out[(qid, axis, level)] = 100 * np.mean(g)
    return out


def survey_fit(shares):
    gaps, matched, reversed_, compared = [], 0, 0, 0
    for qid in ISSUES:
        for axis in [a for a in BENCH[qid] if a != "overall"]:
            levels = [lv for lv in BENCH[qid][axis] if (qid, axis, lv) in shares]
            gaps += [abs(shares[(qid, axis, lv)] - BENCH[qid][axis][lv]) for lv in levels]
            for x, y in itertools.combinations(levels, 2):
                hd = BENCH[qid][axis][x] - BENCH[qid][axis][y]
                if hd == 0:
                    continue
                pd = shares[(qid, axis, x)] - shares[(qid, axis, y)]
                compared += 1
                matched += pd * hd > 0
                reversed_ += pd * hd < 0
    return np.mean(gaps), matched, reversed_, compared


def question_gap(shares):
    return np.mean([abs(shares[(q, "overall")] - BENCH[q]["overall"]) for q in ISSUES])


def composition(model, path):
    run = read_json(path)
    stances = {}
    for r in read_jsonl(f"results/survey/{model}.jsonl"):
        stances.setdefault(r["qid"], []).append(r["stance"])
    balanced = read_jsonl(f"results/debates/{model}.jsonl")
    out = {}
    for qid in dict.fromkeys(r["issue"] for r in run["rooms"]):
        s = {"population": 6 * BENCH[qid]["overall"] / 100, "personas": 6 * stances[qid].count(1) / len(stances[qid])}
        if "no_persona" in run:
            v = [x for x in run["no_persona"][qid] if x in (1, -1)]
            s["no_persona"] = 6 * v.count(1) / len(v)
        for comp in ("6A", "6B"):
            rr = [r for r in run["rooms"] if r["issue"] == qid and r["comp"] == comp]
            if rr:
                s[comp] = sum(on_a(r["included"]) for r in rr) / len(rr)
        bb = [r for r in balanced if r["issue"] == qid]
        if bb:
            s["3-3"] = sum(on_a(r["debate"]["included"]) for r in bb) / len(bb)
        out[qid] = s
    return out
