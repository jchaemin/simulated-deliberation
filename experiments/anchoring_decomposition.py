import random

from simdelib import llm, prompts
from simdelib.deliberation import benchmark_probability
from simdelib.personas import agent_name, load_pool, system_prompt
from simdelib.questions import QUESTIONS
from simdelib.survey import ask, classify, field, ordered, public_text, stable_hash
from experiments._common import MODELS, parallel, write_json

M = MODELS["sol"]
QIDS = ["birth2", "birth4", "env1"]
ARMS = ["natural", "label_only", "argued", "own_hidden", "peer_hidden"]


def private_survey(p, q, transcript):
    first = random.Random(stable_hash(p["uuid"], "ord")).choice(["A", "B"])
    text = ask(M, system_prompt(p), prompts.forced_choice(q["topic"], *ordered(q, first), transcript, private=True), 0.0, 80)
    return classify(field(text, "choice"), q, neutral=("중립",), tie_unclassified=False)


def say(p, user):
    return public_text(ask(M, system_prompt(p), user, 0.7, 400))


def room(panel, q, seed, assigned, arm):
    rng = random.Random(seed)
    names = {i: agent_name(panel[i], i) for i in range(6)}
    if arm == "natural":
        sides = {i: [private_survey(panel[i], q, "")] for i in range(6)}
    else:
        sides = {i: [assigned[i]] for i in range(6)}
    hidden = {i: (None if arm != "peer_hidden" else next(j for j in range(6) if j != i and assigned[j] == assigned[i]))
              for i in range(6)}
    turns = []
    order = list(range(6)); rng.shuffle(order)
    for i in order:
        if arm in ("argued", "own_hidden", "peer_hidden"):
            turns.append((i, say(panel[i], prompts.argued_opening(q, names[i], q["poleA"] if assigned[i] > 0 else q["poleB"]))))
        else:
            turns.append((i, say(panel[i], prompts.free_opening(q, names[i]))))
    for r in range(3):
        order = list(range(6)); rng.shuffle(order)
        for i in order:
            log = "\n".join(f"{names[j]}: {u}" for j, u in turns)
            turns.append((i, say(panel[i], prompts.speaking_turn(q, names[i], log))))
        for i in range(6):
            skip = i if arm == "own_hidden" else hidden[i]
            sides[i].append(private_survey(panel[i], q, "\n".join(f"{names[j]}: {u}" for j, u in turns if j != skip)))
    return sides


pool = load_pool()
rooms = []
for qid in QIDS:
    for d in range(5):
        panel = random.Random(770 + d).sample(pool, 6)
        ranked = sorted(range(6), key=lambda i: benchmark_probability(panel[i], qid), reverse=True)
        assigned = {i: (1 if ranked.index(i) < 3 else -1) for i in range(6)}
        rooms.append((qid, panel, assigned, 870 + d))
jobs = [(r, arm) for r in rooms for arm in ARMS]
results = parallel(lambda j: {"issue": j[0][0], "seed": j[0][3], "arm": j[1],
                              "sides": room(j[0][1], QUESTIONS[j[0][0]], j[0][3], j[0][2], j[1]),
                              "assigned": [j[0][2][i] for i in range(6)]}, jobs)
write_json("results/anchoring_decomposition/sol.json", results)
print(llm.report())
