#!/usr/bin/env python3
# LLM-judge scoring of debate transcripts: Discourse Quality Index per utterance and
# per-agent argument repertoire (Tables 5 and 22). Judge = gpt-4.1, rubric as in Appendix E.
import argparse, json, sys, threading, queue
sys.path.insert(0, "harness")
import llm
from questions_kr import QUESTIONS_KR

ap = argparse.ArgumentParser(description="Judge scoring for deliberation runs")
ap.add_argument("--input", required=True, help="a runs/*.jsonl deliberation file")
ap.add_argument("--metrics", default="dqi,repertoire")
ap.add_argument("--opening-block", choices=["auto", "yes", "no"], default="auto",
                help="whether transcripts start with a round-0 opening block (argued openings)")
ap.add_argument("--judge", default="openai/gpt-4.1")
ap.add_argument("--size", type=int, default=6)
ap.add_argument("--threads", type=int, default=12)
ap.add_argument("--out-prefix", default=None)
args = ap.parse_args()

JUDGE = args.judge
D = [json.loads(l) for l in open(args.input) if l.strip()]
prefix = args.out_prefix or args.input.rsplit("/", 1)[-1].replace(".jsonl", "")
print(f"loaded {len(D)} transcripts from {args.input}", flush=True)

def call(system, user, mx=200):
    return llm.chat(JUDGE, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                          temperature=0.0, max_tokens=mx, response_format={"type": "json_object"})

def jload(t):
    try: return json.loads(t)
    except Exception: return {}

def has_opening(rec):
    if args.opening_block != "auto": return args.opening_block == "yes"
    # an argued-opening room has one extra block of turns before round 1
    return len(rec["transcript"]) > 3 * args.size

DQI_SYS = ("You are an expert coder applying the Discourse Quality Index (DQI, Steenbergen et al. 2003) "
           "to a Korean deliberation transcript. Score ONLY the target utterance. Respond in JSON.")

def dqi_user(q, ctx, name, utt):
    return (f"[Issue] {q['topic']}\n[Position 1] {q['poleA']}\n[Position 2] {q['poleB']}\n"
            f"[Prior discussion]\n{ctx if ctx else '(none)'}\n[TARGET utterance by {name}]\n{utt}\n\n"
            "Score the TARGET only:\n"
            "- justification: 0 no reason, 1 one incomplete reason, 2 one complete reason with linkage, 3 sophisticated/multiple\n"
            "- common_good: 0 self or group interest, 1 neutral, 2 explicit common good / society\n"
            "- respect: 0 dismissive of others, 1 neutral, 2 explicit respect for others or counterarguments\n"
            "- reciprocity: 0 ignores others, 1 engages a specific prior point\n"
            '- novelty: "new" introduces a new argument, "build" elaborates a prior one, "repeat" restates\n'
            'JSON: {"justification":0,"common_good":0,"respect":0,"reciprocity":0,"novelty":"new"}')

REP_SYS = "You extract distinct, non-redundant argument reasons from a participant's statements. Respond in JSON."

def rep_user(q, name, utts):
    body = "\n".join(f"- {u}" for u in utts)
    return (f"[Issue] {q['topic']}\n[Position A] {q['poleA']}\n[Position B] {q['poleB']}\n"
            f"[Statements by {name}]\n{body}\n\n"
            "List the DISTINCT reasons this participant articulated supporting Position A, and supporting Position B. "
            "Count a reason once even if repeated; do not invent reasons not stated.\n"
            'JSON: {"for_A":["..."],"for_B":["..."]}')

lock = threading.Lock()

if "dqi" in args.metrics:
    dqi = []; jobs = queue.Queue()
    for di, r in enumerate(D):
        tr = r["transcript"]; off = 0 if has_opening(r) else 1
        for idx, (name, utt) in enumerate(tr):
            ctx = "\n".join(f"{n}: {u}" for n, u in tr[:idx])
            jobs.put((di, r["issue"], r.get("cond"), idx // args.size + off, name, utt, ctx))
    tot = jobs.qsize(); done = [0]; print(f"[DQI] {tot} utterances", flush=True)

    def wk_dqi():
        while True:
            try: di, iss, cond, rnd, name, utt, ctx = jobs.get_nowait()
            except queue.Empty: return
            q = QUESTIONS_KR[iss]; d = jload(call(DQI_SYS, dqi_user(q, ctx, name, utt)))
            if d:
                with lock:
                    dqi.append({"debate": di, "issue": iss, "cond": cond, "turn_block": rnd,
                                **{k: d.get(k) for k in ["justification", "common_good", "respect", "reciprocity", "novelty"]}})
                    done[0] += 1
                    if done[0] % 150 == 0: print(f"  dqi {done[0]}/{tot}", flush=True)
    ts = [threading.Thread(target=wk_dqi) for _ in range(args.threads)]
    [t.start() for t in ts]; [t.join() for t in ts]
    json.dump(dqi, open(f"runs/judge_dqi_{prefix}.json", "w"), ensure_ascii=False)
    print(f"saved runs/judge_dqi_{prefix}.json", flush=True)

if "repertoire" in args.metrics:
    rep = []; jobs2 = queue.Queue(); repfail = [0]
    for di, r in enumerate(D):
        byname = {}
        for name, utt in r["transcript"]: byname.setdefault(name, []).append(utt)
        for name, utts in byname.items():
            jobs2.put((di, r["issue"], r.get("cond"), name, utts[:1], "first"))
            jobs2.put((di, r["issue"], r.get("cond"), name, utts, "final"))
    tot2 = jobs2.qsize(); done2 = [0]; print(f"[REPERTOIRE] {tot2} agent-timepoints", flush=True)

    def wk_rep():
        while True:
            try: di, iss, cond, name, utts, tp = jobs2.get_nowait()
            except queue.Empty: return
            q = QUESTIONS_KR[iss]; d = jload(call(REP_SYS, rep_user(q, name, utts), 300))
            with lock:
                done2[0] += 1
                if not d:
                    repfail[0] += 1  # failed judge parse: skip rather than record a spurious zero count
                else:
                    rep.append({"debate": di, "issue": iss, "cond": cond, "agent": name, "tp": tp,
                                "nA": len(d.get("for_A", [])), "nB": len(d.get("for_B", []))})
                if done2[0] % 150 == 0: print(f"  rep {done2[0]}/{tot2}", flush=True)
    ts = [threading.Thread(target=wk_rep) for _ in range(args.threads)]
    [t.start() for t in ts]; [t.join() for t in ts]
    json.dump(rep, open(f"runs/judge_repertoire_{prefix}.json", "w"), ensure_ascii=False)
    print(f"saved runs/judge_repertoire_{prefix}.json (judge-parse failures skipped: {repfail[0]})", flush=True)
