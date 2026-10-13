import json
import re

KR_POOL = "data/persona_pool.jsonl"
US_POOL = "data/persona_pool_usa.jsonl"


def load_pool(path=KR_POOL):
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def load_us_pool():
    return load_pool(US_POOL)


def system_prompt(p):
    return (
        f"당신은 아래 프로필의 대한민국 시민입니다.\n"
        f"[프로필] {p['age']}세 {p['sex']} · {p['province']} {p['district']} 거주 · "
        f"학력 {p['education_level']} · 직업 {p['occupation']} · {p['family_type']}\n"
        f"[배경] {p['persona']} {p.get('professional_persona','')} {p.get('family_persona','')}\n\n"
        f"답변은 항상 지정된 JSON 형식으로만 작성하세요."
    )


AGE_LABEL = {"20s": "20대", "30-44": "30~44세", "45-59": "45~59세", "60+": "60세 이상"}


def demographics_prompt(p):
    return (f"당신은 아래 인구통계 특성을 가진 대한민국 시민입니다.\n"
            f"성별: {p['sex']} · 연령대: {AGE_LABEL[p['age_band']]} · 학력: {p['edu4']} · 거주지역: {p['region_group']}\n"
            f"답변은 항상 지정된 JSON 형식으로만 작성하세요.")


CITIZEN_PROMPT = "당신은 대한민국 시민입니다. 답변은 항상 지정된 JSON 형식으로만 작성하세요."
NO_PERSONA_PROMPT = "답변은 항상 지정된 JSON 형식으로만 작성하세요."


def _pretty(s):
    return s.replace("_", " ")


def us_system_prompt(p):
    return (f"You are a citizen of the United States with the profile below.\n"
            f"[Profile] {p['age']}-year-old {p['sex']} · lives in {p['city']}, {p['state']} · "
            f"education: {_pretty(p['education_level'])} · occupation: {_pretty(p['occupation'])} · {_pretty(p['marital_status'])}\n"
            f"[Background] {p['persona']} {p.get('professional_persona','')}\n\n"
            f"Always answer only in the specified JSON format.")


def agent_name(p, i):
    m = re.match(r"\s*([가-힣]{2,4})\s*씨는", p.get("persona", ""))
    return m.group(1) if m else f"참여자{i+1}"


def room_names(panel):
    names, used = {}, set()
    for i, p in enumerate(panel):
        n = agent_name(p, i)
        if n in used:
            n = f"{n}({i+1})"
        used.add(n)
        names[i] = n
    return names


def _age_group_birth(age):
    return "20대" if 20 <= age <= 29 else "30대" if 30 <= age <= 39 else "40대" if 40 <= age <= 49 else None


def _marital_group(m):
    return "기혼" if m == "배우자있음" else "미혼" if m == "미혼" else None


def group_of(p, axis):
    return {"sex": p["sex"], "age_band": p["age_band"], "edu4": p["edu4"], "region_group": p["region_group"],
            "age_surv": _age_group_birth(p["age"]), "marital": _marital_group(p["marital_status"])}[axis]


def benchmark_axes(qid):
    return ["sex", "age_band", "edu4", "region_group"] if qid.startswith("env") else ["sex", "age_surv", "marital"]
