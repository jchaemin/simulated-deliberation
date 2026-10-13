import sys

from simdelib import llm
from experiments._common import MODELS, write_json

QUESTION = "2017년 신고리 5·6호기 공론화에서 시민참여단은 최종적으로 건설 재개와 건설 중단 중 어느 쪽을 권고했는가? 그리고 그 비율은? 한 줄로 답한다."
answers = {}
for tag in sys.argv[1:]:
    answers[MODELS[tag]] = [llm.chat(MODELS[tag], [{"role": "user", "content": QUESTION}], 1.0, 80, json_mode=False) for _ in range(10)]
    print(tag, answers[MODELS[tag]][0][:100])
write_json("results/shinkori/knowledge.json", answers)
