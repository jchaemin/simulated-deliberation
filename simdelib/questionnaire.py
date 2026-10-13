import hashlib
import json
import random
import re

ITEMS_FILE = "data/original_items_kr.json"
_RAW = {it["id"]: it for it in json.load(open(ITEMS_FILE, encoding="utf-8"))["items"]}

SPEC = {
    "env1": dict(orig="D2", kind="scale5",
                 ask="환경보전과 경제성장의 우선순위에 대한 의견으로 다음 중 어디에 가깝습니까?"),
    "env2": dict(orig="D6", kind="pick2", n_opt=9, a=4, b=9,
                 ask="환경문제 해결을 위해 가장 효과적인 방법 2개를 효과적인 순서대로 선택해 주십시오."),
    "env3": dict(orig="E10", kind="pick2", n_opt=8, a=3, b=2,
                 ask="기후위기에 효과적으로 대응하기 위해 정부가 우선적으로 추진해야 할 정책 2개를 "
                     "우선순위대로 선택해 주십시오."),
    "env4": dict(orig="E13", kind="pick2", n_opt=8, a=1, b=3,
                 ask="기후변화 대응을 위해 우선적으로 육성해야 하는 기후테크 분야 2개를 "
                     "우선순위대로 선택해 주십시오."),
    "birth1": dict(orig="LB1", kind="pick2", n_opt=5, a=2, b=1, renorm=True,
                   ask="다음은 일·가정양립 분야의 향후 정책과제입니다. 저출생 문제 해결을 위해 "
                       "강화·확대되거나 추가될 필요가 있는 정책과제를 우선순위대로 두 개 "
                       "선택해 주십시오."),
    "birth2": dict(orig="LB2", kind="pick2", n_opt=6, a=1, b=2, renorm=True,
                   ask="다음은 교육·돌봄 분야의 향후 정책과제입니다. 저출생 문제 해결을 위해 "
                       "강화·확대되거나 추가될 필요가 있는 정책과제를 우선순위대로 두 개 "
                       "선택해 주십시오."),
    "birth3": dict(orig="LB3", kind="pick2", n_opt=6, a=1, b=2, renorm=True,
                   ask="다음은 결혼·출산·양육 분야의 향후 정책과제입니다. 저출생 문제 해결을 "
                       "위해 강화·확대되거나 추가될 필요가 있는 정책과제를 우선순위대로 두 개 "
                       "선택해 주십시오."),
    "birth4": dict(orig="LB4", kind="pick2", n_opt=6, a=1, b=3, renorm=True,
                   ask="다음은 주거 분야의 향후 정책과제입니다. 저출생 문제 해결을 위해 "
                       "강화·확대되거나 추가될 필요가 있는 정책과제를 우선순위대로 두 개 "
                       "선택해 주십시오."),
}
ENV, BIRTH = ["env1", "env2", "env3", "env4"], ["birth1", "birth2", "birth3", "birth4"]
HUMAN_BIRTH = {"birth1": 60.8, "birth2": 58.4, "birth3": 56.4, "birth4": 53.3}

_SCALE = _RAW["D2"]["question"]["format"]["scale"]["anchors"]
SCALE_LOW, SCALE_HIGH = _SCALE["1"], _SCALE["5"]


def options(qid):
    return [v["label"] for v in _RAW[SPEC[qid]["orig"]]["result"]["values"]]


def human_option_shares(qid):
    return [v["value"] for v in _RAW[SPEC[qid]["orig"]]["result"]["values"]]


def system_prompt(p):
    return (f"당신은 아래 프로필의 대한민국 시민입니다.\n"
            f"[프로필] {p['age']}세 {p['sex']} · {p['district']} 거주 · "
            f"학력 {p['education_level']} · 직업 {p['occupation']} · {p['family_type']}\n"
            f"[배경] {p['persona']} {p.get('professional_persona','')} {p.get('family_persona','')}\n\n"
            f"답변은 항상 지정된 JSON 형식으로만 작성하세요.")


def _rotation(qid, uuid, n):
    order = list(range(1, n + 1))
    random.Random(int(hashlib.md5(f"{qid}|{uuid}|rot".encode()).hexdigest()[:12], 16)).shuffle(order)
    return order


def build(qid, arm, uuid):
    s = SPEC[qid]
    if s["kind"] == "scale5":
        low, high = (SCALE_LOW, SCALE_HIGH) if arm == "F" else (SCALE_HIGH, SCALE_LOW)
        body = (f"[문항] {s['ask']}\n"
                f"1 — {low}\n5 — {high}\n"
                f"1에서 5 사이의 정수 하나로 답하세요. 3은 중립입니다.\n\n"
                f'JSON으로만 답하세요. 예: {{"scale": <1~5 정수>, "reason": "한 문장"}}')
        return body, {"flip": arm == "R"}
    opts = options(qid)
    order = list(range(1, len(opts) + 1)) if arm == "F" else _rotation(qid, uuid, len(opts))
    lines = "\n".join(f"{k}. {opts[o - 1]}" for k, o in enumerate(order, 1))
    body = (f"[문항] {s['ask']}\n{lines}\n\n"
            f"1순위와 2순위를 보기 번호로 답하세요. 서로 다른 번호여야 합니다.\n"
            f'JSON으로만 답하세요. 예: {{"first": <번호>, "second": <번호>, "reason": "한 문장"}}')
    return body, {"order": order}


def parse(qid, text, meta):
    m = re.search(r"\{.*\}", text or "", re.S)
    d = json.loads(m.group(0)) if m else {}
    if SPEC[qid]["kind"] == "scale5":
        v = int(d["scale"])
        if not 1 <= v <= 5:
            raise ValueError(f"scale out of range: {v}")
        return {"scale": 6 - v if meta["flip"] else v}
    order = meta["order"]
    first, second = int(d["first"]), int(d["second"])
    if not (1 <= first <= len(order) and 1 <= second <= len(order)) or first == second:
        raise ValueError(f"invalid picks: {first}, {second}")
    return {"first": order[first - 1], "second": order[second - 1]}


def recode(qid, answer):
    s = SPEC[qid]
    if s["kind"] == "scale5":
        v = answer["scale"]
        return "A" if v <= 2 else ("B" if v >= 4 else "mid")
    picks = (answer["first"], answer["second"])
    in_a, in_b = s["a"] in picks, s["b"] in picks
    if in_a and in_b:
        return "A" if answer["first"] == s["a"] else "B"
    return "A" if in_a else "B" if in_b else "neither"


def renorm_share(share_a, share_b):
    total = share_a + share_b
    return None if total == 0 else share_a / total * 100
