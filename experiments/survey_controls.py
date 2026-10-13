import argparse
import random

from simdelib import llm, prompts
from simdelib.personas import CITIZEN_PROMPT, NO_PERSONA_PROMPT
from simdelib.questions import ISSUES, QUESTIONS
from simdelib.survey import ask, classify, field, ordered, stable_hash
from experiments._common import MODELS, parallel, write_json

SYSTEMS = {"korean_citizen": CITIZEN_PROMPT, "no_persona": NO_PERSONA_PROMPT}
SAMPLES = 80

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=MODELS)
a = ap.parse_args()
jobs = [(cond, qid, k) for cond in SYSTEMS for qid in ISSUES for k in range(SAMPLES)]


def run(job):
    cond, qid, k = job
    q = QUESTIONS[qid]
    first = "A" if random.Random(stable_hash(cond, qid, k)).random() < 0.5 else "B"
    text = ask(MODELS[a.model], SYSTEMS[cond], prompts.forced_choice(q["topic"], *ordered(q, first)), 1.0, 80)
    return classify(field(text, "choice"), q)


answers = parallel(run, jobs)
out = {f"{c}|{q}": [s for (cc, qq, _), s in zip(jobs, answers) if (cc, qq) == (c, q) and s in (1, -1)]
       for c in SYSTEMS for q in ISSUES}
write_json(f"results/survey_controls/{a.model}.json", out)
print(llm.report())
