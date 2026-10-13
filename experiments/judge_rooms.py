import argparse

from simdelib import llm, judging
from simdelib.questions import QUESTIONS
from experiments._common import JUDGES, parallel, read_jsonl, write_json

ap = argparse.ArgumentParser()
ap.add_argument("--rooms", required=True)
ap.add_argument("--judge", required=True, choices=JUDGES)
a = ap.parse_args()
J = JUDGES[a.judge]
rooms = read_jsonl(a.rooms)


def round_offset(room):
    return 0 if len(room["transcript"]) > 18 else 1


utterances = [(k, t, name, utt) for k, r in enumerate(rooms) for t, (name, utt) in enumerate(r["transcript"])
              if t // 6 + round_offset(r) >= 1]
speakers = []
for k, r in enumerate(rooms):
    by_speaker = {}
    for name, utt in r["transcript"]:
        by_speaker.setdefault(name, []).append(utt)
    speakers += [(k, name, utts[:1], "first") for name, utts in by_speaker.items()]
    speakers += [(k, name, utts, "final") for name, utts in by_speaker.items()]


def dqi(job):
    k, t, name, utt = job
    r = rooms[k]
    context = "\n".join(f"{n}: {u}" for n, u in r["transcript"][:t])
    scores = judging.score_utterance(J, QUESTIONS[r["issue"]], context, name, utt)
    return scores and {"room": k, "issue": r["issue"], "round": t // 6 + round_offset(r), **scores}


def repertoire(job):
    k, name, utts, when = job
    found = judging.reasons(J, QUESTIONS[rooms[k]["issue"]], name, utts, max_tokens=300)
    return found and {"room": k, "issue": rooms[k]["issue"], "agent": name, "tp": when, "nA": len(found[0]), "nB": len(found[1])}


write_json(a.rooms.replace(".jsonl", f"_{a.judge}.json"),
           {"dqi": [x for x in parallel(dqi, utterances) if x], "repertoire": [x for x in parallel(repertoire, speakers) if x]})
print(llm.report())
