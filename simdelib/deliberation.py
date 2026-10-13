import math
import random

from . import prompts
from .personas import benchmark_axes, group_of, room_names, system_prompt
from .questions import BENCH
from .survey import ask, first_position, public_text, stable_hash, stance


def _log(names, turns, skip=None):
    return "\n".join(f"{names[i]}: {u}" for i, u in turns if i != skip)


def speak(model, p, q, name, transcript=None, side_cue=None, temperature=1.0):
    return public_text(ask(model, system_prompt(p), prompts.speaking_turn(q, name, transcript, side_cue), temperature, 400))


def survey(model, p, q, qid, transcript=None):
    return stance(model, system_prompt(p), q, first_position(p["uuid"], qid), transcript)


def debate(model, panel, q, qid, seed, start, cue="none", probe=False):
    rng = random.Random(seed)
    names = room_names(panel)
    seats = range(len(panel))
    included = {i: [start[i]] for i in seats}
    excluded = {i: [start[i]] for i in seats}
    turns = []
    if cue == "opening":
        order = list(seats); rng.shuffle(order)
        for i in order:
            position = q["poleA"] if start[i] > 0 else q["poleB"]
            turns.append((i, public_text(ask(model, system_prompt(panel[i]), prompts.argued_opening(q, names[i], position), 1.0, 400))))
    for r in range(1, 4):
        order = list(seats); rng.shuffle(order)
        for i in order:
            restate = (q["poleA"] if start[i] > 0 else q["poleB"]) if (cue == "side" and r == 1) else None
            turns.append((i, speak(model, panel[i], q, names[i], _log(names, turns), restate)))
        for i in seats:
            included[i].append(survey(model, panel[i], q, qid, _log(names, turns)))
            if probe:
                excluded[i].append(survey(model, panel[i], q, qid, _log(names, turns, skip=i)))
    room = {"included": included, "transcript": [[names[i], u] for i, u in turns]}
    if probe:
        room["excluded"] = excluded
    return room


def monologue(model, panel, q, qid, start):
    names = room_names(panel)
    seats = range(len(panel))
    sides = {i: [start[i]] for i in seats}
    own = {i: [] for i in seats}
    for r in range(3):
        for i in seats:
            own[i].append(speak(model, panel[i], q, names[i], "\n".join(own[i])))
        for i in seats:
            sides[i].append(survey(model, panel[i], q, qid, "\n".join(own[i])))
    return {"sides": sides, "own": own}


def balanced_rooms(supporters_a, supporters_b, n_rooms, seed):
    rng = random.Random(seed)
    a, b, rooms = [], [], []
    for _ in range(n_rooms):
        if len(a) < 3:
            a = supporters_a[:]; rng.shuffle(a)
        if len(b) < 3:
            b = supporters_b[:]; rng.shuffle(b)
        rooms.append(a[:3] + b[:3])
        del a[:3]; del b[:3]
    return rooms


def disjoint_rooms(supporters_a, supporters_b, max_rooms, seed):
    rng = random.Random(seed)
    a, b = supporters_a[:], supporters_b[:]
    rng.shuffle(a); rng.shuffle(b)
    rooms = []
    for d in range(max_rooms):
        if len(a) >= 3 and len(b) >= 3:
            rooms.append((a[:3] + b[:3], {i: (1 if i < 3 else -1) for i in range(6)}, seed + d))
            del a[:3]; del b[:3]
    return rooms


def _logit(x):
    x = min(max(x, 0.02), 0.98)
    return math.log(x / (1 - x))


def benchmark_probability(p, qid):
    base = BENCH[qid]["overall"] / 100
    lo = _logit(base)
    for axis in benchmark_axes(qid):
        share = BENCH[qid].get(axis, {}).get(group_of(p, axis))
        if share is not None:
            lo += _logit(share / 100) - _logit(base)
    return min(max(1 / (1 + math.exp(-lo)), 0.05), 0.95)


def matched_side(p, qid):
    return 1 if random.Random(stable_hash(p["uuid"], qid, "inj")).random() < benchmark_probability(p, qid) else -1
