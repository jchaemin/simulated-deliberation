#!/usr/bin/env python3
# Table 25 hide-peer arm under the main protocol, as an offline counterfactual probe:
# re-ask the round-3 stance survey on the released injection debates with a view of
# the agent's OWN turns only (peers hidden). Survey wording/temp identical to protocol.
import json, sys, threading, queue
sys.path.insert(0, "harness")
import llm
from core import load_pool, load_survey, make_names, stance_survey, QUESTIONS_KR

pool, byid = load_pool()
SV, FIRST = load_survey()

rooms = [json.loads(l) for l in open("runs/debate_injected.jsonl")]
jobs = queue.Queue()
for ri, r in enumerate(rooms):
    panel = [byid[u] for u in r["ids"]]
    names = make_names(panel)
    own = {i: [] for i in range(len(panel))}
    for nm, utt in r["transcript"]:
        idx = [i for i in names if names[i] == nm]
        if len(idx) == 1: own[idx[0]].append((nm, utt))
    for i in range(len(panel)):
        vis = "\n".join(f"{a}: {u}" for a, u in own[i])
        r0 = r["included"][str(i)][0]
        jobs.put((ri, i, panel[i], r["issue"], vis, r0))

out = []
lock = threading.Lock()
def work():
    while True:
        try: ri, i, p, qid, vis, r0 = jobs.get_nowait()
        except queue.Empty: return
        try:
            st = stance_survey(p, QUESTIONS_KR[qid], qid, vis, FIRST)
            with lock: out.append({"room": ri, "agent": i, "issue": qid, "r0": r0, "probe": st})
        except Exception as e:
            with lock: print("ERR", ri, i, str(e)[:60], flush=True)

ts = [threading.Thread(target=work) for _ in range(12)]
[t.start() for t in ts]; [t.join() for t in ts]
json.dump(out, open("runs/probe_hidepeer.json", "w"), ensure_ascii=False)
ok = [o for o in out if o["probe"] in (1, -1) and o["r0"] in (1, -1)]
mv = sum(1 for o in ok if o["probe"] != o["r0"])
print(f"hide-peer probe: {len(out)} answers, moved {100*mv/len(ok):.1f}%", flush=True)
