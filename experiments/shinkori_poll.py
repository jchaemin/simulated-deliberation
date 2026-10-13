import argparse
import collections
import random

from simdelib import llm, prompts, shinkori as SK
from simdelib.survey import classify, field, public_text
from experiments._common import MODELS, parallel, write_json

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
ap.add_argument("--condition", required=True, choices=["debate", "monologue", "restated", "fictional"])
ap.add_argument("--threads", type=int, default=20)
a = ap.parse_args()
M = MODELS[a.model]
Q = SK.QUESTION
P = SK.load_panel()
ROOMS = [list(range(k, k + 6)) for k in range(0, len(P), 6)]
MONO = a.condition == "monologue"
SYSTEM = [SK.system_prompt(p, SK.name(i)) for i, p in enumerate(P)]
BOOKLET = [SK.booklet(i) for i in range(len(P))]


def call(i, user, temperature, max_tokens):
    msgs = [{"role": "system", "content": SYSTEM[i]}, {"role": "user", "content": user}]
    if a.condition == "fictional":
        msgs = [{**m, "content": SK.fictional(m["content"])} for m in msgs]
    return llm.chat(M, msgs, temperature, max_tokens)


def survey(i, transcript, with_booklet):
    text = call(i, prompts.forced_choice(Q["topic"], *SK.options(P[i]), transcript, BOOKLET[i] if with_booklet else None), 0.0, 80)
    return classify(field(text, "choice"), Q)


def survey3(i, transcript, with_booklet):
    text = call(i, prompts.three_way(Q["topic"], *SK.options(P[i]), SK.UNDECIDED, transcript, BOOKLET[i] if with_booklet else None), 0.0, 80)
    choice = field(text, "choice")
    if choice and ("유보" in choice or "모르" in choice):
        return 0
    return classify(choice, Q)


def speak(i, transcript, side=None):
    cue = (Q["poleA"] if side > 0 else Q["poleB"]) if side in (1, -1) else None
    return public_text(call(i, prompts.speaking_turn(Q, SK.name(i), transcript, cue, BOOKLET[i]), 1.0, 400))


THREE_WAY = a.condition in ("debate", "monologue")
out = {"model": M, "condition": a.condition, "rooms": ROOMS, "stages": {}}
everyone = range(len(P))
out["stages"]["S0"] = parallel(lambda i: survey(i, "", False), everyone, a.threads)
out["stages"]["S1"] = parallel(lambda i: survey(i, "", True), everyone, a.threads)
if THREE_WAY:
    out["three"] = {"S0": parallel(lambda i: survey3(i, "", False), everyone, a.threads)} if a.condition == "debate" else {}
log = {k: [] for k in range(len(ROOMS))}
own = {i: [] for i in everyone}


def run_round(k, r):
    order = ROOMS[k][:]
    random.Random(7000 + k * 10 + r).shuffle(order)
    for i in order:
        side = SK.REAL_SIDE[P[i]["truth"]] if (a.condition == "restated" and r == 0) else None
        if MONO:
            own[i].append(speak(i, "\n".join(own[i]), side))
        else:
            log[k].append((i, speak(i, "\n".join(f"{SK.name(j)}: {u}" for j, u in log[k]), side)))


def view(i):
    return "\n".join(own[i]) if MONO else "\n".join(f"{SK.name(j)}: {u}" for j, u in log[i // 6])


for r in range(3):
    parallel(lambda k: run_round(k, r), range(len(ROOMS)), min(a.threads, 40))
    out["stages"][f"R{r + 1}"] = parallel(lambda i: survey(i, view(i), True), everyone, a.threads)
    c = collections.Counter(out["stages"][f"R{r + 1}"])
    print(f"round {r + 1}: resume {c[1]}, halt {c[-1]}", flush=True)
if THREE_WAY:
    out["three"]["R3"] = parallel(lambda i: survey3(i, view(i), True), everyone, a.threads)
out["transcripts"] = ({str(i): own[i] for i in own} if MONO else
                      {str(k): [[SK.name(j), u] for j, u in log[k]] for k in log})
write_json(f"results/shinkori/{a.model}_{a.condition}.json", out)
print(llm.report())
