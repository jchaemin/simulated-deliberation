#!/usr/bin/env python3
# Presentational-factor factorial for the signed bipolar scale (Appendix B).
# One factor changes at a time against the base presentation: option order in the
# text, the answer letter, the scale sign (which position is +2), and the scale
# direction. Effects are shifts in the share choosing position A's content.
import json, sys, random, statistics as st, argparse
sys.path.insert(0, "harness")
import llm
from llm import persona_system, ask_json
from core import QUESTIONS_KR, ISSUES, load_pool

ap = argparse.ArgumentParser()
ap.add_argument("--temperature", type=float, default=0.0)
ap.add_argument("--out", default="runs/factorial.json")
args = ap.parse_args()
llm.MODEL = "openai/gpt-4.1-mini"

pool, _ = load_pool()
random.seed(1); random.shuffle(pool); sub240 = pool[:240]
from collections import defaultdict
cells = defaultdict(list)
for p in sub240: cells[(p["sex"], p["age_band"])].append(p)
rng = random.Random(5); personas = []
for k in sorted(cells): rng.shuffle(cells[k]); personas += cells[k][:3]   # 24 balanced

def build(q, letterA, first, plus, sdir):
    cA, cB = q["poleA"], q["poleB"]
    tagA = cA if letterA == "cA" else cB
    letter = lambda c: "A" if c == tagA else "B"
    fC, sC = (cA, cB) if first == "cA" else (cB, cA)
    opt = f"({letter(fC)}) {fC}   vs   ({letter(sC)}) {sC}"
    plusC = cA if plus == "cA" else cB
    pL = letter(plusC); mL = "B" if pL == "A" else "A"
    pm = f"+2 {pL}를 매우 지지 · +1 {pL}를 지지 · 0 중립·유보 · -1 {mL}를 지지 · -2 {mL}를 매우 지지"
    mp = f"-2 {mL}를 매우 지지 · -1 {mL}를 지지 · 0 중립·유보 · +1 {pL}를 지지 · +2 {pL}를 매우 지지"
    sc = pm if sdir == "pm" else mp
    return f"[쟁점] {q['topic']}\n[선택지] {opt}\n[질문] 당신은 A와 B 중 어느 쪽에 더 가깝습니까?\n[척도] {sc}"

CONDS = {"base": ("cA", "cA", "cA", "pm"), "optorder": ("cA", "cB", "cA", "pm"),
         "label": ("cB", "cA", "cA", "pm"), "sign": ("cA", "cA", "cB", "pm"),
         "scaleorder": ("cA", "cA", "cA", "mp")}

def choose_cA(stance, plus):
    if stance == 0: return None
    return (stance > 0) if plus == "cA" else (stance < 0)

def cell(q, cond, agents, sysfn):
    from concurrent.futures import ThreadPoolExecutor
    la, fi, pl, sd = CONDS[cond]; blk = build(q, la, fi, pl, sd)
    u = blk + '\n\n현재 당신의 입장을 JSON으로. 예: {"stance": <-2~2 정수>}'
    def one(a):
        try:
            s = ask_json(sysfn(a), u, args.temperature, 120, require_stance=True)["stance"]
            return choose_cA(s, pl)
        except Exception:
            return None
    with ThreadPoolExecutor(12) as ex:
        picks = [c for c in ex.map(one, agents) if c is not None]
    return 100 * sum(picks) / len(picks) if picks else float("nan")

NP = [None] * 20
npsys = lambda a: "당신은 일반적인 성인입니다. 설문에 JSON으로만 답하세요."
out = {"temperature": args.temperature, "cells": {}, "sign_mean_abs": {}}
agg = {"NP": defaultdict(list), "PE": defaultdict(list)}
for qid in ISSUES:
    q = QUESTIONS_KR[qid]
    for grp, agents, sysfn in [("NP", NP, npsys), ("PE", personas, persona_system)]:
        base = cell(q, "base", agents, sysfn)
        out["cells"][f"{grp}|{qid}|base"] = base
        for cond in ("optorder", "label", "sign", "scaleorder"):
            v = cell(q, cond, agents, sysfn)
            out["cells"][f"{grp}|{qid}|{cond}"] = v
            agg[grp][cond].append(base - v)
        print(f"{qid} {grp} done", flush=True)
for grp in ("NP", "PE"):
    for cond in ("optorder", "label", "sign", "scaleorder"):
        out["sign_mean_abs"][f"{grp}|{cond}"] = st.mean(abs(x) for x in agg[grp][cond] if x == x)
json.dump(out, open(args.out, "w"), ensure_ascii=False, indent=1)
print({k: round(v, 1) for k, v in out["sign_mean_abs"].items()}, flush=True)
