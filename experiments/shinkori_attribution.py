import argparse
import json
import random

from simdelib import llm, prompts, shinkori as SK
from simdelib.survey import classify, field
from experiments._common import MODELS, parallel, write_json

LABELS = {"self": "당신(지난 차례): ", "none": "", "expert": "이 문제를 연구한 전문가: ", "peer": "같은 모둠의 다른 참여자: "}

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
a = ap.parse_args()
M = MODELS[a.model]
Q = SK.QUESTION
P = SK.load_panel()
inputs = json.load(open("results/shinkori/attribution_inputs.json", encoding="utf-8"))

statements = {1: [], -1: []}
after_round1 = inputs["source_round1"]
for k, turns in inputs["source_transcripts"].items():
    for name, utt in turns:
        j = int(k) * 6 + int(name.replace("참여자", "")) - 1
        if after_round1[j] in (1, -1) and "참여자" not in utt and len(utt) > 30:
            statements[after_round1[j]].append(utt)
booklet_answer = inputs["booklet_stage"][a.model]
target = [(-booklet_answer[i] if booklet_answer[i] in (1, -1) else random.Random(5 + i).choice([1, -1])) for i in range(len(P))]
argument = [random.Random(9 + i).choice(statements[target[i]]) for i in range(len(P))]


def survey(i, shown):
    user = prompts.forced_choice(Q["topic"], *SK.options(P[i]), shown, SK.booklet(i))
    text = llm.chat(M, [{"role": "system", "content": SK.system_prompt(P[i])}, {"role": "user", "content": user}], 0.0, 80)
    return classify(field(text, "choice"), Q)


moved = {}
for label, prefix in LABELS.items():
    answers = parallel(lambda i: survey(i, prefix + argument[i]), range(len(P)), 20)
    moved[label] = 100 * sum(answers[i] == target[i] for i in range(len(P))) / len(P)
write_json(f"results/shinkori/attribution_{a.model}.json", {"model": M, "moved_pct": moved,
                                                           "statements": {str(k): len(v) for k, v in statements.items()}})
print(a.model, moved, llm.report())
