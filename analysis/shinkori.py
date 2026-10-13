import collections
import itertools
import os

import numpy as np

from simdelib.shinkori import load_panel
from simdelib.stats import a_share, read_json, rnd

MODELS = {"sol": "GPT-6-sol", "luna": "GPT-6-luna", "mini": "GPT-4.1-mini",
          "deepseek": "DeepSeek-V4.1", "haiku": "Claude-Haiku-5.5", "qwen": "Qwen-3.8-flash"}
CONDITIONS = {"debate": "Debate", "monologue": "Monologue", "restated": "Restated", "fictional": "Fictional names"}
PANEL3 = {"S0": (36.6, 27.6, 35.8), "S1": (44.7, 30.7, 24.6), "R3": (57.2, 39.4, 3.3)}
PANEL = {"S0": 36.6 / 64.2 * 100, "S1": 44.7 / 75.4 * 100, "R3": 57.2 / 96.6 * 100}
WAVE1 = {"재개": 1, "중단": -1}
runs = {m: {c: read_json(f"results/shinkori/{m}_{c}.json") for c in CONDITIONS} for m in MODELS}
people = load_panel()


def three_way(v):
    c, n = collections.Counter(v), len(v)
    return 100 * c[1] / n, 100 * c[-1] / n, 100 * (n - c[1] - c[-1]) / n


def tvd(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / 200


print("Resume share: wave 1 / booklet / after round 3 (debate); monologue, restated, fictional after round 3")
for m, name in MODELS.items():
    st = runs[m]["debate"]["stages"]
    print(f"  {name:17} {rnd(a_share(st['S0']), 1)} / {rnd(a_share(st['S1']), 1)} / {rnd(a_share(st['R3']), 1)}   "
          + "  ".join(f"{c} {rnd(a_share(runs[m][c]['stages']['R3']), 1)}" for c in ("monologue", "restated", "fictional")))
    change = {c: a_share(runs[m][c]["stages"]["R3"]) - a_share(runs[m][c]["stages"]["S1"]) for c in ("debate", "monologue")}
    print("    change booklet -> round 3: " + ", ".join(f"{c} {rnd(v, 1, True)}" for c, v in change.items()) + "  (panel -0.1)")
    th = runs[m]["debate"]["three"]
    print(f"    three-way: undecided at wave 1 {rnd(three_way(th['S0'])[2], 0)}%, after the debate {rnd(three_way(th['R3'])[2], 0)}%; "
          f"distance from the panel after the debate {rnd(tvd(three_way(th['R3']), PANEL3['R3']), 2)}, "
          f"after the monologue {rnd(tvd(three_way(runs[m]['monologue']['three']['R3']), PANEL3['R3']), 2)}")
    s1, r3 = runs[m]["restated"]["stages"]["S1"], runs[m]["restated"]["stages"]["R3"]
    cued = [i for i, p in enumerate(people) if p["truth"] in WAVE1]
    differ = [i for i in cued if s1[i] != WAVE1[people[i]["truth"]]]
    print(f"    restated: cue differs from booklet answer {rnd(100 * len(differ) / len(cued), 0)}%, of those ending on the cued side "
          f"{rnd(100 * sum(r3[i] == WAVE1[people[i]['truth']] for i in differ) / max(1, len(differ)), 0)}%")
    s0 = st["S0"]
    result, gaps = collections.Counter(), []
    for axis in ("sex", "age_band", "area", "party"):
        members = collections.defaultdict(list)
        for i, p in enumerate(people):
            members[p.get(axis) or "none"].append(i)
        shares = {}
        for k, ii in members.items():
            human = [WAVE1[people[i]["truth"]] for i in ii if people[i]["truth"] in WAVE1]
            agents = [s0[i] for i in ii if s0[i] in (1, -1)]
            if len(human) >= 20 and agents:
                shares[k] = (100 * np.mean([x == 1 for x in human]), 100 * np.mean([x == 1 for x in agents]))
        for x, y in itertools.combinations(shares, 2):
            hd, pd = shares[x][0] - shares[y][0], shares[x][1] - shares[y][1]
            if abs(hd) > 5:
                result["match" if hd * pd > 0 else "reversed"] += 1
        gaps += [abs(h - a) for h, a in shares.values()]
    print(f"    group differences over 5 points: {dict(result)}; group gap {rnd(np.mean(gaps), 0)}")

print("\nFigure 5: resume share by stage (wave 1 / booklet / rounds 1-3)")
for m, name in MODELS.items():
    print(f"  {name:17} " + "   ".join(f"{c} " + " ".join(f"{rnd(a_share(runs[m][c]['stages'][k]), 1)}" for k in ("S0", "S1", "R1", "R2", "R3"))
                                       for c in ("debate", "monologue", "restated")))

print("\nAttribution (share moving to the argued side, %): own last turn / no source / expert / fellow participant")
for m, name in MODELS.items():
    v = read_json(f"results/shinkori/attribution_{m}.json")["moved_pct"]
    print(f"  {name:17} " + " / ".join(f"{rnd(v[k], 1)}" for k in ("self", "none", "expert", "peer")))
knowledge = read_json("results/shinkori/knowledge.json")
print("\nModels naming resume as the panel's recommendation in all ten answers:",
      sum(all("재개" in a for a in v) for v in knowledge.values()), "of", len(knowledge))

rng = np.random.default_rng(0)


def interval(v, real, draws=2000):
    rooms, out = len(v) // 6, []
    for _ in range(draws):
        g = rng.integers(0, rooms, rooms)
        out.append(a_share([v[k * 6 + j] for k in g for j in range(6)]) - 100 * rng.binomial(471, real / 100) / 471)
    return a_share(v) - real, np.percentile(out, 2.5), np.percentile(out, 97.5)


def skip(v, real):
    interval(v, real)


def fmt(iv):
    return f"${rnd(iv[0], 1, True)}$ [${rnd(iv[1], 1, True)}$, ${rnd(iv[2], 1, True)}$]"


def bold(v, iv):
    return f"\\textbf{{{rnd(a_share(v), 1)}}}" if iv[1] <= 0 <= iv[2] else f"{rnd(a_share(v), 1)}"


main, full = [], []
for m, name in MODELS.items():
    st = {c: runs[m][c]["stages"] for c in CONDITIONS}
    for c, s in (("debate", "S0"), ("debate", "S1"), ("debate", "R3"), ("monologue", "R3"), ("restated", "R3")):
        skip(st[c][s], PANEL[s])
    iv, rows = {}, []
    for c, label in CONDITIONS.items():
        iv[c] = {s: interval(st[c][s], PANEL[s]) for s in ("S0", "S1", "R3")}
        changed = 100 * np.mean([x != y for x, y in zip(st[c]["S1"], st[c]["R3"])])
        rows.append(f" & {label} & " + " & ".join(f"{rnd(a_share(st[c][s]), 1)} ({fmt(iv[c][s])})" for s in ("S0", "S1", "R3"))
                    + f" & {rnd(changed, 0)} \\\\")
    rows[0] = name + rows[0]
    full += rows + ["\\midrule"]
    main.append(f"{name} & {bold(st['debate']['S0'], iv['debate']['S0'])} & {bold(st['debate']['S1'], iv['debate']['S1'])} & "
                f"{bold(st['debate']['R3'], iv['debate']['R3'])} & {bold(st['monologue']['R3'], iv['monologue']['R3'])} & "
                f"{bold(st['restated']['R3'], iv['restated']['R3'])} \\\\")
os.makedirs("tables", exist_ok=True)
open("tables/shinkori_main_rows.tex", "w").write("\n".join(main) + "\n")
open("tables/shinkori_interval_rows.tex", "w").write("\n".join(full[:-1]) + "\n")
print("\nTable 5 rows (bold: 95% interval of the difference from the panel includes zero):")
print("\n".join("  " + r for r in main))
