import json
import random

QUESTION = {"topic": "신고리 5·6호기 건설 여부 (2017년 8월)",
            "poleA": "신고리 5·6호기 건설을 재개해야 한다",
            "poleB": "신고리 5·6호기 건설을 중단해야 한다"}
UNDECIDED = "판단을 유보한다"
REAL_SIDE = {"재개": 1, "중단": -1, "유보": None}
PANEL_FILE = "data/shinkori_panel_498.json"

RESUME = ("[건설 재개 측 자료] 공정률 28.8%, 이미 1조 6천억 원이 집행되었고 중단하면 보상까지 2조 8천억 원의 피해가 생긴다. "
 "총사업비는 8조 6천억 원이다. 신고리 5·6호기는 APR1400 노형으로 후쿠시마 이후 기준을 반영해 규모 7.0 내진 설계를 했다. "
 "원전을 줄이면 전력 예비율이 불안해지고 기저 전원이 흔들린다. 태양광·풍력은 날씨에 따라 출력이 변한다. "
 "원전을 줄이면 전기요금이 오르고 가계와 기업의 부담이 커진다. 국내에서 짓지 않으면 원전 수출 경쟁력을 잃는다. "
 "울주군 서생면은 주민 투표로 유치를 결정했고 지역 협력업체와 일자리가 걸려 있다. 석탄 화력보다 온실가스와 미세먼지가 적다.")
HALT = ("[건설 중단 측 자료] 2011년 후쿠시마 사고처럼 원전 사고는 한번 나면 되돌릴 수 없다. 2016년 경주에서 규모 5.8 지진이 났고 "
 "양산단층이 활성단층이라는 지적이 있다. 고리 지역은 반경 30km 안에 약 380만 명이 살아 세계에서 원전이 가장 밀집한 곳이며 "
 "사고 시 부산·울산의 대피 계획이 현실적이지 않다. 사용후핵연료 저장 시설은 곧 포화되는데 처분장은 정해지지 않았고 "
 "핵폐기물은 수십만 년간 관리해야 한다. 재생에너지 단가는 계속 내려가고 독일 등은 탈원전으로 가고 있다. "
 "한수원의 납품 비리와 부품 위조 전력이 있다. 두 기를 더 지으면 60년간 원전에 묶인다. 매몰비용보다 장기 위험이 크다.")


def load_panel():
    return json.load(open(PANEL_FILE, encoding="utf-8"))


def booklet(i):
    sides = [RESUME, HALT]
    random.Random(1000 + i).shuffle(sides)
    return sides[0] + "\n\n" + sides[1]


def options(agent):
    return (QUESTION["poleA"], QUESTION["poleB"]) if agent["poleA_first"] else (QUESTION["poleB"], QUESTION["poleA"])


def name(i):
    return f"참여자{i % 6 + 1}"


def system_prompt(agent, label=None):
    party = f"{agent['party']} 지지" if agent.get("party") else "지지 정당 없음"
    who = f"{label} · " if label else ""
    return (f"당신은 아래 프로필의 대한민국 시민입니다.\n[프로필] {who}{agent['age']}세 {'남자' if agent['sex'] == '남' else '여자'} · "
            f"{agent['area']} 거주 · 직업 {agent['occ']} · {party}\n\n답변은 항상 지정된 JSON 형식으로만 작성하세요.")


FICTIONAL = [("신고리 5·6호기", "가람 1·2호기"), ("울주군 서생면은", "부지 인근 마을은"), ("고리 지역은", "가람 부지는"),
             ("부산·울산의", "인근 대도시의"), (" (2017년 8월)", "")]


def fictional(text):
    for old, new in FICTIONAL:
        text = text.replace(old, new)
    return text
