#!/usr/bin/env python3
# One survey pipeline; every survey table in the paper is a flag combination.
#   Table 2 / Tables 8-15:  --pool kr --persona full --instrument natural
#   Table 3 columns:        --persona full | demographics | citizen | none
#   Table 16 rows:          --instrument natural | bipolar | labeled | two-ratings  (labeled: run --order AB and --order BA)
#   Table 20 columns:       --model mini | gpt55 | llama33 | qwen72
#   Table 21 (US pool):     --pool us
#   Noise floor (App. E):   --resurvey 2
import argparse, json, os, sys, random, threading, queue
sys.path.insert(0, "harness")
import llm
from core import (QUESTIONS_KR, ISSUES, dh, classify, load_pool, ask_natural, ask_labeled,
                  ask_two_ratings, ask_bipolar, system_prompt)

MODELS = {"mini": "openai/gpt-4.1-mini", "gpt41": "openai/gpt-4.1", "gpt55": "openai/gpt-5.5",
          "llama33": "meta-llama/llama-3.3-70b-instruct", "qwen72": "qwen/qwen-2.5-72b-instruct"}

ap = argparse.ArgumentParser(description="Unified persona survey runner")
ap.add_argument("--pool", choices=["kr", "us"], default="kr")
ap.add_argument("--persona", choices=["full", "demographics", "citizen", "none"], default="full")
ap.add_argument("--instrument", choices=["natural", "labeled", "two-ratings", "bipolar"], default="natural")
ap.add_argument("--order", choices=["AB", "BA"], default="AB", help="labeled instrument: option order arm")
ap.add_argument("--model", choices=list(MODELS), default="mini")
ap.add_argument("--questions", default="all", help="comma-separated question ids, or 'all'")
ap.add_argument("--temperature", type=float, default=None, help="override the instrument's default temperature")
ap.add_argument("--subsample", type=int, default=0, help="use only the first N personas (deterministic)")
ap.add_argument("--personas-from", default=None,
                help="restrict to the personas appearing in this released data file (e.g. the GPT-5.5 subsample)")
ap.add_argument("--resurvey", type=int, default=1, help="ask each persona this many times (noise floor)")
ap.add_argument("--reps", type=int, default=80, help="citizen/none variants: repetitions per question")
ap.add_argument("--threads", type=int, default=12)
ap.add_argument("--out", default=None)
args = ap.parse_args()

llm.MODEL = MODELS[args.model]

if args.pool == "us":
    # US control pool (Table 21): the same natural forced choice, in English, temperature 0.
    import re as _re
    from core import dh as _dh, classify as _classify
    from questions_us import QUESTIONS_US
    upool = [json.loads(l) for l in open("data/persona_pool_us.jsonl")]
    random.seed(1); random.shuffle(upool); sub = upool[:256]
    out = args.out or "data/survey_us.jsonl"
    have = set()
    if os.path.exists(out):
        for l in open(out):
            r = json.loads(l); have.add((r["uuid"], r["qid"]))
    def pretty(s): return s.replace("_", " ")
    def system_en(p):
        return (f"You are a citizen of the United States with the profile below.\n"
                f"[Profile] {p['age']}-year-old {p['sex']} · lives in {p['city']}, {p['state']} · "
                f"education: {pretty(p['education_level'])} · occupation: {pretty(p['occupation'])} · {pretty(p['marital_status'])}\n"
                f"[Background] {p['persona']} {p.get('professional_persona','')}\n\n"
                f"Always answer only in the specified JSON format.")
    V = {"id": "us2v", "topic": "America's energy priority",
         "poleA": "Developing alternative sources, such as wind, solar and hydrogen technology",
         "poleB": "Expanding exploration and production of oil, coal and natural gas"}
    QS = [QUESTIONS_US["us1"], QUESTIONS_US["us2"], QUESTIONS_US["us3"],
          QUESTIONS_US["us4"], V, QUESTIONS_US["us5"]]
    jobs = queue.Queue()
    for q in QS:
        for p in sub:
            if (p["uuid"], q["id"]) not in have: jobs.put((p, q))
    tot = jobs.qsize(); print(f"US jobs {tot} -> {out}", flush=True)
    lock = threading.Lock(); done = [0]; fails = [0]
    def uswork():
        while True:
            try: p, q = jobs.get_nowait()
            except queue.Empty: return
            fp = random.Random(_dh(p["uuid"], q["id"], "nn")).choice(["A", "B"])
            a, b = (q["poleA"], q["poleB"]) if fp == "A" else (q["poleB"], q["poleA"])
            u = (f"[Issue] {q['topic']}\n"
                 f"Which of the following two positions is closer to your view? You must choose one.\n"
                 f"· {a}\n· {b}\n"
                 'Answer in JSON only, copying one of the two positions verbatim: {"choice": "..."}')
            try:
                t = llm.chat(llm.MODEL, [{"role": "system", "content": system_en(p)},
                                                      {"role": "user", "content": u}],
                                   temperature=args.temperature if args.temperature is not None else 0.0,
                                   max_tokens=80, response_format={"type": "json_object"})
                m = _re.search(r'"choice"\s*:\s*"([^"]*)"', t or "")
                stc = _classify(m.group(1) if m else None, q)
                with lock:
                    if stc is None: fails[0] += 1
                    else:
                        with open(out, "a") as f:
                            f.write(json.dumps({"uuid": p["uuid"], "qid": q["id"], "first": fp, "stance": stc}) + "\n")
                        done[0] += 1
                        if done[0] % 200 == 0: print(f"{done[0]}/{tot}", flush=True)
            except Exception:
                with lock: fails[0] += 1
    ts = [threading.Thread(target=uswork) for _ in range(args.threads)]
    [t.start() for t in ts]; [t.join() for t in ts]
    print(f"collected {done[0]}, unparsed {fails[0]} -> {out}", flush=True)
    sys.exit(0)

pool, _ = load_pool()
if args.personas_from:
    keep = {json.loads(l)["uuid"] for l in open(args.personas_from)}
    pool = [p for p in pool if p["uuid"] in keep]
elif args.subsample:
    pool = pool[:args.subsample]
qids = ISSUES if args.questions == "all" else args.questions.split(",")
out = args.out or f"data/survey_{args.pool}_{args.instrument}_{args.persona}_{args.model}.jsonl"

have = set()
if os.path.exists(out):
    for l in open(out):
        r = json.loads(l); have.add((r.get("uuid"), r["qid"], r.get("rep", 0), r.get("side")))

jobs = queue.Queue()
if args.persona in ("citizen", "none"):
    # persona-free controls: repeated draws per question (Table 3, right columns)
    for qid in qids:
        for rep in range(args.reps):
            if (None, qid, rep, None) not in have: jobs.put((None, qid, rep, None))
elif args.instrument == "two-ratings":
    for qid in qids:
        q = QUESTIONS_KR[qid]
        for p in pool:
            for side in ("A", "B"):
                if (p["uuid"], qid, 0, side) not in have: jobs.put((p, qid, 0, side))
else:
    for qid in qids:
        for p in pool:
            for rep in range(args.resurvey):
                if (p["uuid"], qid, rep, None) not in have: jobs.put((p, qid, rep, None))

tot = jobs.qsize(); print(f"jobs {tot} -> {out}", flush=True)
lock = threading.Lock(); done = [0]; bad = [0]

def work():
    while True:
        try: p, qid, rep, side = jobs.get_nowait()
        except queue.Empty: return
        q = QUESTIONS_KR[qid]
        rec = {"qid": qid}
        if args.persona in ("citizen", "none"):
            import re as _re
            firstA = random.Random(dh(args.persona, qid, rep)).random() < 0.5
            u_first = "A" if firstA else "B"
            t = args.temperature if args.temperature is not None else 1.0
            a, b = (q["poleA"], q["poleB"]) if u_first == "A" else (q["poleB"], q["poleA"])
            u = (f"[쟁점] {q['topic']}\n다음 두 입장 중 당신의 생각에 더 가까운 것은 무엇입니까? 반드시 하나를 선택하세요.\n"
                 f"· {a}\n· {b}\nJSON으로만, 위 두 입장 중 하나를 그대로 적으세요: {{\"choice\": \"...\"}}")
            txt = llm.chat(llm.MODEL, [{"role": "system", "content": system_prompt({}, args.persona)},
                                                    {"role": "user", "content": u}],
                                 temperature=t, max_tokens=80, response_format={"type": "json_object"})
            m = _re.search(r'"choice"\s*:\s*"([^"]*)"', txt or "")
            st = classify(m.group(1) if m else None, q)
            rec.update({"variant": args.persona, "rep": rep, "first": u_first, "stance": st})
        elif args.instrument == "natural":
            fp = random.Random(dh(p["uuid"], qid, "nn")).choice(["A", "B"])  # order fixed per agent, also across resurveys
            t = args.temperature if args.temperature is not None else (0.0 if args.persona == "full" else 0.7)
            ch = ask_natural(p, q, fp, args.persona, t)
            st = classify(ch, q)
            rec.update({"uuid": p["uuid"], "rep": rep, "first": fp, "choice": ch, "stance": st})
        elif args.instrument == "labeled":
            ch = ask_labeled(p, q, swap=(args.order == "BA"),
                             temperature=args.temperature if args.temperature is not None else 0.7)
            st = {"A": 1, "B": -1, "중립": 0}.get(ch)
            if args.order == "BA" and st in (1, -1): st = -st
            rec.update({"uuid": p["uuid"], "order": args.order, "choice": ch, "stance": st})
        elif args.instrument == "bipolar":
            r = ask_bipolar(p, q, args.temperature if args.temperature is not None else 0.0)
            st = r
            rec.update({"uuid": p["uuid"], "stance": r})
        else:  # two-ratings
            pole = q["poleA"] if side == "A" else q["poleB"]
            r = ask_two_ratings(p, q, pole, args.temperature if args.temperature is not None else 0.7)
            st = r
            rec.update({"uuid": p["uuid"], "side": side, "support": r})
        with lock:
            if st is None:
                bad[0] += 1
            else:
                with open(out, "a") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                done[0] += 1
                if done[0] % 800 == 0: print(f"{done[0]}/{tot} (unparsed {bad[0]})", flush=True)

ts = [threading.Thread(target=work) for _ in range(args.threads)]
[t.start() for t in ts]; [t.join() for t in ts]
print(f"collected {done[0]}, unparsed {bad[0]} -> {out}", flush=True)
