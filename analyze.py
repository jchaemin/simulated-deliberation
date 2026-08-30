#!/usr/bin/env python3
# Recompute the paper's exhibits from the stored artifacts in data/ and runs/.
# No API calls. Usage: python3 analyze.py table2 | table3 | table6 | table7 | fig2 |
#                                        table20 | table21 | table24 | summaries
import json, sys, collections, statistics as st
sys.path.insert(0, "harness")
from questions_kr import QUESTIONS_KR, BENCH

ISSUES = ["env1", "env2", "env3", "env4", "birth1", "birth2", "birth3", "birth4"]
NAME = {"env1": "Env. priority", "env2": "Env. means", "env3": "Clim. strategy", "env4": "Clim. tech",
        "birth1": "Work-family", "birth2": "Educ.-care", "birth3": "Econ. support", "birth4": "Housing"}

def _agesurv(a): return "20대" if 20 <= a <= 29 else "30대" if 30 <= a <= 39 else "40대" if 40 <= a <= 49 else None
def _marital2(m): return "기혼" if m == "배우자있음" else "미혼" if m == "미혼" else None

def load_stances(path):
    out = collections.defaultdict(dict)
    for l in open(path):
        r = json.loads(l)
        if r.get("stance") in (1, -1): out[r["qid"]][r["uuid"]] = r["stance"]
    return out

def ashare(d):
    v = list(d.values()); return 100 * sum(1 for x in v if x == 1) / len(v) if v else float("nan")

def pool_map():
    return {p["uuid"]: p for p in (json.loads(l) for l in open("data/persona_pool.jsonl"))}

def group_members(p, qid):
    fam = "env" if qid.startswith("env") else "birth"
    if fam == "env":
        return [("sex", p["sex"]), ("age_band", p["age_band"]), ("edu4", p["edu4"]), ("region_group", p["region_group"])]
    return [("sex", p["sex"]), ("age_surv", _agesurv(p["age"])), ("marital", _marital2(p["marital_status"]))]

def table2():
    sv = load_stances("data/survey_main.jsonl"); pm = pool_map()
    gaps = []
    for qid in ISSUES:
        cells = collections.defaultdict(list)
        for u, s in sv[qid].items():
            for ax, lvl in group_members(pm[u], qid):
                if lvl: cells[(ax, lvl)].append(s)
        print(f"\n{NAME[qid]}  (persona overall {ashare(sv[qid]):.0f}%, population {BENCH[qid]['overall']}%)")
        for (ax, lvl), v in sorted(cells.items()):
            bench = BENCH[qid].get(ax, {}).get(lvl)
            if bench is None: continue
            llm = 100 * sum(1 for x in v if x == 1) / len(v)
            gaps.append(abs(llm - bench))
            print(f"  {ax:13} {lvl:8} LLM {llm:5.1f}  human {bench:5.1f}  gap {abs(llm-bench):4.1f}")
    print(f"\nmean absolute by-group gap: {st.mean(gaps):.1f} over {len(gaps)} cells")

def table3():
    sv = load_stances("data/survey_main.jsonl")
    bd = load_stances("data/survey_demographics.jsonl")
    mb = json.load(open("runs/controls_persona_free.json"))
    def mb_share(cond, qid):
        v = mb.get(f"{cond}|{qid}", [])
        return 100 * sum(1 for x in v if x == 1) / len(v) if v else float("nan")
    cols = {"Full persona": lambda q: ashare(sv[q]), "Demographics only": lambda q: ashare(bd[q]),
            "Korean citizen": lambda q: mb_share("korean_citizen", q), "No persona": lambda q: mb_share("no_persona", q)}
    print(f"{'Question':14}" + "".join(f"{c:>19}" for c in cols) + f"{'Human':>8}")
    gaps = {c: [] for c in cols}
    for qid in ISSUES:
        row = f"{NAME[qid]:14}"
        for c, f in cols.items():
            v = f(qid); gaps[c].append(abs(v - BENCH[qid]["overall"])); row += f"{v:19.0f}"
        print(row + f"{BENCH[qid]['overall']:8.0f}")
    print(f"{'Mean abs. gap':14}" + "".join(f"{st.mean(gaps[c]):19.1f}" for c in cols))

def _finals(path, want=None):
    out = collections.defaultdict(list)
    for l in open(path):
        if not l.strip(): continue
        r = json.loads(l)
        if want and r.get("cond") not in want: continue
        seqs = r["included"] if "included" in r else r["sides"]
        fin = [s[-1] for s in seqs.values() if s]
        start = [s[0] for s in seqs.values() if s]
        moved = sum(1 for s in seqs.values() if s and s[0] in (1, -1) and s[-1] in (1, -1) and s[0] != s[-1])
        out[(r["issue"], r.get("cond"))].append((sum(1 for s in fin if s == 1), moved, len(seqs),
                                                 sum(1 for s in start if s == 1)))
    return out

def _cell(recs):
    finalA = st.mean(r[0] for r in recs); moved = 100 * sum(r[1] for r in recs) / sum(r[2] for r in recs)
    return finalA, moved

def table6():
    nat = _finals("runs/debate_natural.jsonl"); mono = _finals("runs/debate_monologue.jsonl")
    print(f"{'Issue':14}{'Debate':>8}{'Monologue':>11}{'Diff':>7}")
    for qid in ISSUES:
        kn = [(k, v) for k, v in nat.items() if k[0] == qid]; km = [(k, v) for k, v in mono.items() if k[0] == qid]
        if not kn or not km: continue
        d, _ = _cell(kn[0][1]); m, _ = _cell(km[0][1])
        print(f"{NAME[qid]:14}{d:8.1f}{m:11.1f}{d-m:+7.1f}")

def table7():
    cells = {("survey", "none"): ("runs/debate_natural.jsonl", None),
             ("survey", "side"): ("runs/debate_sidecue.jsonl", {"survey_sidecue"}),
             ("survey", "opening"): ("runs/debate_protocols.jsonl", {"survey_opening"}),
             ("population", "label"): ("runs/debate_protocols.jsonl", {"population_label"}),
             ("population", "side"): ("runs/debate_sidecue.jsonl", {"population_sidecue"}),
             ("population", "opening"): ("runs/debate_injected.jsonl", None)}
    for (sides, cue), (path, want) in cells.items():
        data = _finals(path, want)
        print(f"\n[{sides} side, cue={cue}]  ({path})")
        for qid in ISSUES:
            recs = [v for k, v in data.items() if k[0] == qid]
            if not recs: continue
            f, m = _cell(recs[0])
            print(f"  {NAME[qid]:14} final A {f:4.1f}  moved {m:4.0f}%")

def fig2():
    sv = load_stances("data/survey_main.jsonl")
    mb = json.load(open("runs/controls_persona_free.json"))
    six = _finals("runs/debate_compositions.jsonl"); nat = _finals("runs/debate_natural.jsonl")
    for qid in ["env4", "birth2", "birth4"]:
        prior = mb.get(f"no_persona|{qid}", [])
        priorA = 6 * sum(1 for x in prior if x == 1) / len(prior)
        popA = 6 * BENCH[qid]["overall"] / 100; perA = 6 * ashare(sv[qid]) / 100
        rooms = {}
        for (iss, cond), recs in six.items():
            if iss != qid: continue
            for finA, _, _, startA in recs: rooms.setdefault("6-0" if startA >= 5 else "0-6", []).append(finA)
        bal = [v for k, v in nat.items() if k[0] == qid]
        b = st.mean(r[0] for r in bal[0]) if bal else float("nan")
        print(f"{NAME[qid]:14} pop {popA:.2f}  personas {perA:.2f}  prior {priorA:.2f}  |  "
              f"6-0 {st.mean(rooms.get('6-0', [float('nan')])):.2f}  3-3 {b:.2f}  0-6 {st.mean(rooms.get('0-6', [float('nan')])):.2f}")

def table20():
    files = {"GPT-4.1-mini": "data/xmodel_gpt41mini.jsonl", "GPT-5.5": "data/xmodel_gpt55.jsonl",
             "Llama-3.3-70B": "data/xmodel_llama33.jsonl", "Qwen-2.5-72B": "data/xmodel_qwen72.jsonl"}
    for m, f in files.items():
        sv = load_stances(f)
        gaps = [abs(ashare(sv[q]) - BENCH[q]["overall"]) for q in ISSUES if sv[q]]
        print(f"{m:14} mean gap {st.mean(gaps):5.1f}  " +
              " ".join(f"{q}:{ashare(sv[q]):3.0f}" for q in ISSUES if sv[q]))

def table21():
    from questions_us import BENCH_US
    cnt = collections.defaultdict(list)
    for l in open("data/survey_us.jsonl"):
        r = json.loads(l)
        if r.get("stance") in (1, -1): cnt[r["qid"]].append(r["stance"])
    for qid, v in sorted(cnt.items()):
        a = 100 * sum(1 for x in v if x == 1) / len(v)
        bench = BENCH_US.get(qid, {}).get("overall")
        print(f"{qid:6} A-share {a:5.1f}" + (f"  Pew {bench}  gap {abs(a-bench):.1f}" if bench is not None else ""))

def table24():
    inj = _finals("runs/debate_injected.jsonl"); nat = _finals("runs/debate_natural.jsonl")
    mv_i, mv_n = [], []
    print(f"{'Question':14}{'Injected pre>fin (moved)':>26}{'Natural pre>fin (moved)':>26}")
    for qid in ISSUES:
        ki = [v for k, v in inj.items() if k[0] == qid]; kn = [v for k, v in nat.items() if k[0] == qid]
        si = f"3.0->{_cell(ki[0])[0]:.1f} ({_cell(ki[0])[1]:.0f}%)" if ki else "-"
        sn = f"3.0->{_cell(kn[0])[0]:.1f} ({_cell(kn[0])[1]:.0f}%)" if kn else "-"
        if ki: mv_i.append(_cell(ki[0])[1])
        if kn: mv_n.append(_cell(kn[0])[1])
        print(f"{NAME[qid]:14}{si:>26}{sn:>26}")
    print(f"{'All (mean)':14}{st.mean(mv_i):>24.0f}%{st.mean(mv_n):>25.0f}%")

def _group_gap_map(stance_by_uuid):
    # mean absolute by-group gap (the 88 groups of Section 4) for a {qid: {uuid: ±1}} map
    pm = pool_map(); gaps = []
    for qid in ISSUES:
        cells = collections.defaultdict(list)
        for u, s in stance_by_uuid.get(qid, {}).items():
            for ax, lvl in group_members(pm[u], qid):
                if lvl: cells[(ax, lvl)].append(s)
        for (ax, lvl), v in cells.items():
            bench = BENCH[qid].get(ax, {}).get(lvl)
            if bench is None: continue
            gaps.append(abs(100 * sum(1 for x in v if x == 1) / len(v) - bench))
    return st.mean(gaps)

def table16():
    # Instrument comparison at the protocol temperature: mean absolute by-group gap
    # under one metric for all four instruments (directional responses only).
    nat = collections.defaultdict(dict)
    for l in open("data/survey_main.jsonl"):
        r = json.loads(l)
        if r["stance"] in (1, -1): nat[r["qid"]][r["uuid"]] = r["stance"]
    bi = collections.defaultdict(dict)
    for l in open("data/instrument_bipolar.jsonl"):
        r = json.loads(l)
        if r.get("stance") not in (None, 0): bi[r["qid"]][r["uuid"]] = 1 if r["stance"] > 0 else -1
    ab = collections.defaultdict(dict); ba = collections.defaultdict(dict)
    for path, d in (("data/instrument_labeled_AB.jsonl", ab), ("data/instrument_labeled_BA.jsonl", ba)):
        for l in open(path):
            r = json.loads(l)
            if r["stance"] in (1, -1): d[r["qid"]][r["uuid"]] = r["stance"]
    # counterbalanced: group share = mean of the two arms' shares
    pm = pool_map(); gaps = []; order = {}
    for qid in ISSUES:
        c1 = collections.defaultdict(list); c2 = collections.defaultdict(list)
        for d, c in ((ab, c1), (ba, c2)):
            for u, s in d[qid].items():
                for ax, lvl in group_members(pm[u], qid):
                    if lvl: c[(ax, lvl)].append(s)
        order[qid] = (100 * sum(1 for s in ab[qid].values() if s == 1) / len(ab[qid])
                      - 100 * sum(1 for s in ba[qid].values() if s == 1) / len(ba[qid]))
        for k in c1:
            bench = BENCH[qid].get(k[0], {}).get(k[1])
            if bench is None: continue
            a1 = 100 * sum(1 for x in c1[k] if x == 1) / len(c1[k])
            a2 = 100 * sum(1 for x in c2[k] if x == 1) / len(c2[k])
            gaps.append(abs((a1 + a2) / 2 - bench))
    tm = collections.defaultdict(lambda: collections.defaultdict(dict))
    for l in open("data/instrument_two_ratings.jsonl"):
        r = json.loads(l); tm[r["qid"]][r["uuid"]][r["side"]] = r["support"]
    tr = collections.defaultdict(dict); acq = {}
    for qid in tm:
        both = tot = 0
        for u, d in tm[qid].items():
            if "A" in d and "B" in d:
                tot += 1; both += (d["A"] >= 1 and d["B"] >= 1)
                if d["A"] > d["B"]: tr[qid][u] = 1
                elif d["B"] > d["A"]: tr[qid][u] = -1
        acq[qid] = 100 * both / tot
    print(f"{'Signed bipolar scale':38}{_group_gap_map(bi):6.1f}")
    print(f"{'Labeled forced choice (counterbal.)':38}{st.mean(gaps):6.1f}   order effect mean {st.mean(abs(v) for v in order.values()):.1f}, max {max(order.items(), key=lambda x: abs(x[1]))}")
    print(f"{'Two independent ratings':38}{_group_gap_map(tr):6.1f}   both-sides>=1 per q: " + " ".join(f"{q}:{acq[q]:.0f}" for q in sorted(acq)))
    print(f"{'Natural forced choice (main)':38}{_group_gap_map(nat):6.1f}")
    try:
        fac = json.load(open("runs/factorial.json"))
        print("factorial sign effect (mean |pts|): personas "
              f"{fac['sign_mean_abs']['PE|sign']:.1f}, no persona {fac['sign_mean_abs']['NP|sign']:.1f}")
    except FileNotFoundError:
        print("runs/factorial.json missing (run run_factorial.py)")

def _rooms(path):
    for l in open(path):
        if l.strip(): yield json.loads(l)

def _lever_stats(path):
    import re as _re
    IDRE = _re.compile(r"여성|여자|남성|남자|대졸|고졸|중졸|대학원|초졸|20대|30대|40대|50대|60대|기혼|미혼|세대|연령|성별|학력")
    moved = tot = 0; c0 = []; c3 = []; fa = []; idr = []
    for r in _rooms(path):
        seqs = list(r["included"].values())
        for s in seqs:
            if s and s[0] in (1, -1) and s[-1] in (1, -1):
                tot += 1; moved += (s[0] != s[-1])
        for idx, acc in ((0, c0), (-1, c3)):
            v = [s[idx] for s in seqs if s and s[idx] in (1, -1)]
            a = sum(1 for x in v if x == 1)
            if v: acc.append(max(a, len(v) - a) / len(v))
        fa.append(sum(1 for s in seqs if s and s[-1] == 1))
        utts = r.get("transcript", [])
        if utts: idr.append(sum(len(IDRE.findall(u)) for _, u in utts) / len(utts))
    return {"moved": 100 * moved / tot, "c0": st.mean(c0), "c3": st.mean(c3),
            "finalA": st.mean(fa), "idr": st.mean(idr) if idr else None, "rooms": len(c0)}

def table23():
    rows = [("Disclosure", "anonymous name (baseline)", "runs/levers_baseline.jsonl"),
            ("", "demographics shown", "runs/levers_demo.jsonl"),
            ("First speaker", "a side-A holder opens", "runs/levers_openA.jsonl"),
            ("", "a side-B holder opens", "runs/levers_openB.jsonl"),
            ("Room size", "4 agents", "runs/levers_n4.jsonl"),
            ("", "6 agents (baseline)", "runs/levers_baseline.jsonl"),
            ("", "8 agents", "runs/levers_n8.jsonl"),
            ("Turns", "sequential (baseline)", "runs/levers_baseline.jsonl"),
            ("", "simultaneous", "runs/levers_sim.jsonl")]
    print(f"{'Lever':14}{'Condition':28}{'Moved':>7}{'Convergence':>16}{'Final A':>9}{'IdRefs/utt':>11}")
    for lever, cond, path in rows:
        s = _lever_stats(path)
        idr = f"{s['idr']:.2f}" if s["idr"] is not None else "-"
        print(f"{lever:14}{cond:28}{s['moved']:>6.0f}%{s['c0']:>8.2f} -> {s['c3']:.2f}{s['finalA']:>9.1f}{idr:>11}")

def table25():
    # Decomposition of the round-0 injection, all under the main protocol:
    # hold and hide-own are the two stored survey views of the released injected
    # debates; hide-peer re-asks the round-3 survey on the same debates with peers
    # hidden (run_probe.py); label-only is the population_label arm of debate_protocols; natural is the
    # survey-side debate run.
    def pooled(path, cond=None, key="included"):
        m = t = 0
        for r in _rooms(path):
            if cond and r.get("cond") != cond: continue
            for s in (r.get(key) or r["sides"]).values():
                if s and s[0] in (1, -1) and s[-1] in (1, -1):
                    t += 1; m += (s[0] != s[-1])
        return 100 * m / t
    probe = json.load(open("runs/probe_hidepeer.json"))
    ok = [o for o in probe if o["probe"] in (1, -1) and o["r0"] in (1, -1)]
    hp = 100 * sum(1 for o in ok if o["probe"] != o["r0"]) / len(ok)
    print(f"{'Assigned side stated and carried (the hold)':52}{pooled('runs/debate_injected.jsonl'):>5.0f}%")
    print(f"{'  hide a same-side peer turns from the survey':52}{hp:>5.0f}%")
    print(f"{'  hide the agent own turns from the survey (probe)':52}{pooled('runs/debate_injected.jsonl', key='excluded'):>5.0f}%")
    print(f"{'Assigned side recorded but not argued (label only)':52}{pooled('runs/debate_protocols.jsonl', 'population_label'):>5.0f}%")
    print(f"{'Natural (free opening)':52}{pooled('runs/debate_natural.jsonl'):>5.0f}%")

def summaries():
    for f in ["runs/probe_hidepeer.json"]:
        try: print(f"\n== {f} ==\n{json.dumps(json.load(open(f)), ensure_ascii=False)[:600]}")
        except FileNotFoundError: print(f"missing {f}")

if __name__ == "__main__":
    cmds = {"table2": table2, "table3": table3, "table6": table6, "table7": table7, "fig2": fig2,
            "table16": table16, "table20": table20, "table21": table21, "table23": table23,
            "table24": table24, "table25": table25, "summaries": summaries}
    for a in (sys.argv[1:] or ["table3"]):
        print(f"\n===== {a} ====="); cmds[a]()
