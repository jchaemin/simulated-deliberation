import collections
import os

import numpy as np

from simdelib.personas import load_pool
from simdelib.questions import BENCH, BENCH_USA, ISSUES
from simdelib.stats import a_share, group_shares, question_gap, read_json, read_jsonl, rint, rnd, survey_fit

MODELS = ["sol", "luna", "mini", "deepseek", "haiku", "qwen"]
byid = {p["uuid"]: p for p in load_pool()}
binary = lambda r: None if r["stance"] not in (1, -1) else float(r["stance"] == 1)


def report(name, shares):
    gap, matched, reversed_, compared = survey_fit(shares)
    print(f"{name:30} gap by group {rnd(gap, 1)}  by question {rnd(question_gap(shares), 1)}  "
          f"directions {matched}/{reversed_} of {compared}  A-shares {[rint(shares[(q, 'overall')]) for q in ISSUES]}")


print("Six models (temperature 0):")
for m in MODELS:
    report(m, group_shares(read_jsonl(f"results/survey/{m}.jsonl"), byid, binary))

print("\nGPT-6-sol under alternative instruments:")
inst = "results/survey_instruments/sol_"
report("demographics only", group_shares(read_jsonl(inst + "demographics.jsonl"), byid, binary))
report("neutral option", group_shares(read_jsonl(inst + "neutral.jsonl"), byid, binary))
labeled = ([{**r, "w": None if r["choice"] not in "AB" else float(r["choice"] == "A")} for r in read_jsonl(inst + "labeled.jsonl")]
           + [{**r, "w": None if r["choice"] not in "AB" else float(r["choice"] == "B")} for r in read_jsonl(inst + "labeled_swapped.jsonl")])
report("labeled, counterbalanced", group_shares(labeled, byid, lambda r: r["w"]))
ratings = {}
for r in read_jsonl(inst + "two_ratings.jsonl"):
    ratings.setdefault((r["uuid"], r["qid"]), {})[r["side"]] = r["support"]
two = [{"uuid": u, "qid": q, "w": 1.0 if s["A"] > s["B"] else 0.0 if s["A"] < s["B"] else None}
       for (u, q), s in ratings.items() if "A" in s and "B" in s]
report("two ratings", group_shares(two, byid, lambda r: r["w"]))
both_rated = sum(1 for q in ISSUES if np.mean([s["A"] >= 1 and s["B"] >= 1 for (u, qq), s in ratings.items() if qq == q and len(s) == 2]) > .99)
print(f"{'':30} questions where >99% rate both positions 1 or higher: {both_rated}")
samples = collections.defaultdict(list)
for r in read_jsonl(inst + "temperature1.jsonl"):
    samples[(r["uuid"], r["qid"])].append(r["s"])
t1 = [{"uuid": u, "qid": q, "w": np.mean([x == 1 for x in v if x in (1, -1)]) if any(x in (1, -1) for x in v) else None}
      for (u, q), v in samples.items()]
report("temperature 1", group_shares(t1, byid, lambda r: r["w"]))

print("\nTable 2 (A-share, %; mean absolute gap by question):")
sol = group_shares(read_jsonl("results/survey/sol.jsonl"), byid, binary)
demo = group_shares(read_jsonl(inst + "demographics.jsonl"), byid, binary)
controls = read_json("results/survey_controls/sol.json")
columns = {"full persona": [sol[(q, "overall")] for q in ISSUES], "demographics only": [demo[(q, "overall")] for q in ISSUES],
           "Korean citizen": [a_share(controls[f"korean_citizen|{q}"]) for q in ISSUES],
           "no persona": [a_share(controls[f"no_persona|{q}"]) for q in ISSUES]}
for name, col in columns.items():
    print(f"  {name:18} {[rint(x) for x in col]}  gap {rnd(np.mean([abs(x - BENCH[q]['overall']) for x, q in zip(col, ISSUES)]), 0)}")
print(f"  {'human survey':18} {[BENCH[q]['overall'] for q in ISSUES]}")

print("\nU.S. pool (A-share vs Pew):")
for m in ("sol", "mini"):
    rows = read_jsonl(f"results/survey_us/{m}.jsonl")
    shares = {q: a_share([r["stance"] for r in rows if r["qid"] == q]) for q in BENCH_USA}
    print(f"  {m:5} {[rint(shares[q]) for q in BENCH_USA]}  mean gap {rnd(np.mean([abs(shares[q] - BENCH_USA[q]['overall']) for q in BENCH_USA]), 0)}")

LABELS = {"sex": {"남자": "Male", "여자": "Female"}, "age_band": {"20s": "19--29", "30-44": "30--44", "45-59": "45--59", "60+": "60+"},
          "edu4": {"≤중졸": "$\\leq$ Middle", "고졸": "High school", "대졸": "College", "대학원": "Graduate"},
          "region_group": {"수도권": "Capital area", "영남": "Yeongnam", "호남": "Honam", "충청": "Chung\\-cheong", "강원·제주": "Gangwon--Jeju"},
          "age_surv": {"20대": "20s", "30대": "30s", "40대": "40s"}, "marital": {"미혼": "Single", "기혼": "Married"}}
AXIS = {"sex": "Sex", "age_band": "Age", "edu4": "Education", "region_group": "Region", "age_surv": "Age", "marital": "Marital status"}
lines = []
for panel in (ISSUES[:4], ISSUES[4:]):
    column_gaps = collections.defaultdict(list)
    for axis in [a for a in BENCH[panel[0]] if a != "overall"]:
        levels = list(BENCH[panel[0]][axis])
        for k, lv in enumerate(levels):
            cells = [(sol[(q, axis, lv)], BENCH[q][axis][lv]) for q in panel]
            for q, (p, h) in zip(panel, cells):
                column_gaps[q].append(abs(p - h))
            head = f"\\multirow{{{len(levels)}}}{{=}}{{{AXIS[axis]}}}" if k == 0 else ""
            lines.append(f"{head}\n& {LABELS[axis][lv]}\n& " + " & ".join(f"{rnd(p, 0)} / {rnd(h, 0)}" for p, h in cells)
                         + f" & \\textbf{{{rnd(np.mean([abs(p - h) for p, h in cells]), 0)}}} \\\\")
    every = [g for q in panel for g in column_gaps[q]]
    lines.append("\\midrule\n\\multicolumn{2}{@{}l}{\\textbf{Mean absolute gap}}\n& "
                 + " & ".join(f"\\textbf{{{rnd(np.mean(column_gaps[q]), 0)}}}" for q in panel) + f" & \\textbf{{{rnd(np.mean(every), 0)}}} \\\\")
os.makedirs("tables", exist_ok=True)
open("tables/bygroup_rows.tex", "w").write("\n".join(lines) + "\n")
print("\nwrote tables/bygroup_rows.tex")
