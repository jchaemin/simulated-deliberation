#!/usr/bin/env python3
# One deliberation pipeline; every debate condition in the paper is a flag combination.
#   Table 6 (debate vs monologue):  --sides survey --cue none --interaction debate | monologue
#   Table 7 (six protocols):        --sides survey|population  x  --cue none|side|opening
#   Figure 2 (compositions):        --composition 6-0 | 3-3 | 0-6
#   Table 24 (injection):           --sides population --cue opening
#   Table 25 (label only):          --sides population --cue label
#   Table 23 (levers):              --disclosure demographics | --turns simultaneous | --size 4|8 | --opener A|B
import argparse, json, sys, threading, queue
sys.path.insert(0, "harness")
import llm
from core import (QUESTIONS_KR, ISSUES, load_pool, load_survey, inj_side,
                  build_rooms, debate, monologue)

MODELS = {"mini": "openai/gpt-4.1-mini", "gpt41": "openai/gpt-4.1"}

ap = argparse.ArgumentParser(description="Unified deliberation runner")
ap.add_argument("--questions", default="all", help="comma-separated question ids, or 'all'")
ap.add_argument("--rooms", type=int, default=6, help="rooms per question")
ap.add_argument("--composition", choices=["3-3", "6-0", "0-6"], default="3-3")
ap.add_argument("--sides", choices=["survey", "population"], default="survey",
                help="side source: the agent's own survey answer, or population-matched assignment")
ap.add_argument("--cue", choices=["none", "side", "opening", "label"], default="none",
                help="how the side enters the debate: not at all; a one-line round-1 cue; an argued "
                     "round-0 opening; or recorded only (label), which behaves like none in the debate")
ap.add_argument("--interaction", choices=["debate", "monologue"], default="debate")
ap.add_argument("--rounds", type=int, default=3)
ap.add_argument("--size", type=int, default=6, help="agents per room")
ap.add_argument("--disclosure", choices=["name", "demographics"], default="name")
ap.add_argument("--turns", choices=["sequential", "simultaneous"], default="sequential")
ap.add_argument("--opener", choices=["none", "A", "B"], default="none",
                help="move an agent holding this side to the front of round 1")
ap.add_argument("--panels", choices=["pooled", "random"], default="pooled",
                help="pooled: draw sides from the A/B pools per --composition; "
                     "random: draw --rooms panels of --size personas per question, round-0 sides from the survey")
ap.add_argument("--panel-seed", type=int, default=1000,
                help="random panels: the same seed gives identical (paired) panels across condition runs")
ap.add_argument("--speech-temp", type=float, default=1.0)
ap.add_argument("--model", choices=list(MODELS), default="mini")
ap.add_argument("--seed", type=int, default=5000)
ap.add_argument("--threads", type=int, default=12)
ap.add_argument("--out", default=None)
args = ap.parse_args()

if args.interaction == "monologue" and args.cue not in ("none", "label"):
    sys.exit("monologue rooms take no cue: use --cue none")
llm.MODEL = MODELS[args.model]
pool, byid = load_pool()
SV, FIRST = load_survey()
qids = ISSUES if args.questions == "all" else args.questions.split(",")
cue_engine = "none" if args.cue == "label" else args.cue
tag = f"{args.sides}_{args.cue}_{args.composition}" + ("_mono" if args.interaction == "monologue" else "")
out = args.out or f"runs/debate_{tag}.jsonl"

JOBS = []
for qi, qid in enumerate(qids):
    if args.panels == "random":
        # paired panels: same --panel-seed reproduces the same draws across condition runs
        import random as _rnd
        answered = [u for u in SV[qid]]
        rng = _rnd.Random(args.panel_seed + qi * 97)
        for pi in range(args.rooms):
            draw = rng.sample(answered, max(args.size, 8))  # nested: size-4/6/8 share one draw
            ids = draw[:args.size]
            r0 = {i: SV[qid][ids[i]] for i in range(args.size)}
            JOBS.append((qid, ids, r0, args.seed + qi * 50 + pi))
        print(f"  {qid}: {args.rooms} random panels of {args.size}", flush=True)
        continue
    if args.sides == "survey":
        A = [u for u in SV[qid] if SV[qid][u] == 1]; B = [u for u in SV[qid] if SV[qid][u] == -1]
    else:
        A = [p["uuid"] for p in pool if inj_side(p, qid) > 0]
        B = [p["uuid"] for p in pool if inj_side(p, qid) < 0]
    base = args.seed + qi * 50
    for ids, r0, seed in build_rooms(A, B, args.composition, args.rooms, base, args.size):
        JOBS.append((qid, ids, r0, seed))
    print(f"  {qid}: pools A {len(A)} / B {len(B)}", flush=True)

print(f"{len(JOBS)} rooms ({tag}) -> {out}", flush=True)
lock = threading.Lock(); jobs = queue.Queue(); done = [0]
for J in JOBS: jobs.put(J)

def work():
    while True:
        try: qid, ids, r0, seed = jobs.get_nowait()
        except queue.Empty: return
        try:
            panel = [byid[u] for u in ids]
            if args.interaction == "monologue":
                rec = monologue(panel, ids, qid, seed, r0, FIRST, args.rounds, args.speech_temp)
            else:
                rec = debate(panel, ids, qid, seed, r0, FIRST, cue_engine, args.rounds,
                             args.disclosure, args.turns, args.speech_temp, cond=tag,
                             opener=(None if args.opener == "none" else args.opener))
            with lock:
                open(out, "a").write(json.dumps(rec, ensure_ascii=False) + "\n")
                done[0] += 1
                if done[0] % 6 == 0: print(f"  {done[0]}/{len(JOBS)}", flush=True)
        except Exception as e:
            with lock: print("ERR", qid, str(e)[:70], flush=True)

ts = [threading.Thread(target=work) for _ in range(args.threads)]
[t.start() for t in ts]; [t.join() for t in ts]
print(f"done {done[0]} rooms -> {out}", flush=True)
