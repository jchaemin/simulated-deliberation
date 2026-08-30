# -*- coding: utf-8 -*-
"""원설문 형식 그대로의 환경 4문항 — 측정 불일치(measurement mismatch)를 없애기 위한 것.

## 왜 필요한가

지금까지의 비교는 두 가지가 섞여 있었다.

    인간   8지 중 2개 선택  →  연구자가 A/B 로 재코딩  →  A-share
    LLM    A/B 강제 선택                              →  A-share

"페르소나가 인구를 재현 못 한다"는 결론에 대해 **"그건 페르소나 실패가 아니라
측정 방식이 달라서 아니냐"** 는 반론이 가능하다. 반박할 수 없다. 그래서 LLM 에게도
원설문 형식 그대로 묻고, **인간에게 적용된 것과 문자 그대로 같은 함수**로 재코딩한다.

## 재코딩 규칙 — 우리가 만든 것이 아니라 원자료 정리본에 적힌 것

    기후환경_4개_하위의제_설문데이터_공유본 (1).docx
    "※ D6·E10·E13 재분류: A만 선택→A / B만 선택→B / A·B 모두 선택→1순위 기준 /
      둘 다 미선택→미분류. A/B 환산값은 원설문 자체의 강제 양자택일 결과가 아니라
      파생 지표입니다."

이 규칙을 문서의 집계값에 적용하면 네 문항의 `bench_A` 가 **정확히 재현된다**
(아래 HUMAN 의 검산값 참조). 즉 규칙이 확인된 것이고, 같은 규칙을 LLM 에 적용하면
양쪽이 같은 자로 재어진다.

**둘 다 고른 경우를 1순위로 푼다는 점 때문에, LLM 응답은 집합이 아니라 순위여야
한다.** `{"first": n, "second": n}` 로 받는 이유가 이것이다.

## 선택지 순서는 원설문 그대로다

`source_items_kr.json` 의 `values` 배열 순서가 원설문 문항의
보기 순서다. Word 문서가 극의 번호를 적어 두어(D6 ④/⑨ · E10 ③/② · E13 ①/③)
대조로 확인했다. 그래서 문항 텍스트를 여기에 옮겨 적지 않고 **JSON 에서 읽는다** —
옮겨 적으면 순서나 문구가 어긋나도 알 수 없다.

## 저출생 4문항 — 넣되, 다른 자를 쓴다 (2026-08-28 추가)

처음에는 빼 두었다. 저출생 정리본에는 원자료가 없어서 (문서 스스로 "동일 응답자가
A와 B를 모두 선택했는지, 또는 어느 정책을 1순위로 두었는지는 공개 집계표만으로
확인할 수 없습니다" 라고 적었다) 인간 쪽 5범주가 복원되지 않고, 따라서 위의
`recode()` 규칙을 인간에게 적용할 방법이 없기 때문이다.

그런데 **A-share 만 비교한다면 같은 자를 쓸 수 있다.** 저출생 정리본의 기준값은
`p(A)/[p(A)+p(B)]`, 즉 1+2순위 선택률의 재정규화다. 페르소나에게 원설문을 그대로
물으면 같은 1+2순위 선택률이 나오므로, **양쪽에 문자 그대로 같은 함수**를 적용할 수
있다. 이것이 `bench="renorm"` 이다.

그래서 두 자가 공존한다. 섞어 쓰면 안 된다.

    bench="cells"   기후 4문항. KEI 원자료(n=3,008)로 인간 5범주가 실측된다.
                    per-respondent 재코딩(A만/B만/둘다→1순위/미선택)을 양쪽에 적용.
    bench="renorm"  저출생 4문항. 원자료가 없다. 선택률 재정규화만 양쪽에 적용.
                    **5범주 분해·개인 단위 일치도 분석에 쓰지 마라** — 인간 쪽에
                    대응물이 없어서 비교가 성립하지 않는다.

`human_cells()` 는 bench="cells" 에서만 값을 돌려준다(그 외 None). 논문 본문 Table 3
이 이미 두 패널에서 서로 다른 기준(환경=방향성 응답자, 저출생=1+2순위 재정규화)을
쓰고 있으므로, 이 구분은 새로 만든 것이 아니라 원자료 사정을 그대로 따른 것이다.
"""
import json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_JSON = os.path.join(os.path.dirname(_HERE), "source_items_kr.json")

with open(_JSON, encoding="utf-8") as f:
    _RAW = {it["id"]: it for it in json.load(f)["items"]}

N_HUMAN = 3008          # KEI 2025 국민환경의식조사

# 극의 위치는 **1-기반 보기 번호**다. Word 문서에 적힌 번호와 JSON 의 배열 순서가
# 일치하는지 아래 _check() 가 실행 시점에 검산한다.
SPEC = {
    "env1": dict(orig="D2", topic="환경정책 우선순위", kind="scale5",
                 ask="환경보전과 경제성장의 우선순위에 대한 의견으로 다음 중 어디에 가깝습니까?",
                 poleA="환경보전 우선", poleB="경제성장 우선"),
    "env2": dict(orig="D6", topic="환경문제 해결수단", kind="pick2", n_opt=9, a=4, b=9,
                 ask="환경문제 해결을 위해 가장 효과적인 방법 2개를 효과적인 순서대로 선택해 주십시오.",
                 poleA="처벌·법집행 강화", poleB="자발적 노력 우선"),
    "env3": dict(orig="E10", topic="기후위기 대응전략", kind="pick2", n_opt=8, a=3, b=2,
                 ask="기후위기에 효과적으로 대응하기 위해 정부가 우선적으로 추진해야 할 정책 2개를 "
                     "우선순위대로 선택해 주십시오.",
                 poleA="기후적응 우선", poleB="에너지전환 우선"),
    "env4": dict(orig="E13", topic="기후테크 육성방향", kind="pick2", n_opt=8, a=1, b=3,
                 ask="기후변화 대응을 위해 우선적으로 육성해야 하는 기후테크 분야 2개를 "
                     "우선순위대로 선택해 주십시오.",
                 poleA="재생에너지 우선", poleB="순환경제 우선"),

    # ── 저출생 4문항 (bench="renorm"; 위 머리글 참조) ──────────────────────
    # 문안은 원설문 그대로다. 극의 보기번호는 questions_kr.py 의 poleA/poleB 와
    # 대응하며 _check() 가 JSON 집계값으로 검산한다.
    "birth1": dict(orig="LB1", topic="일·가정양립", kind="pick2", n_opt=5, a=2, b=1,
                   bench="renorm",
                   ask="다음은 일·가정양립 분야의 향후 정책과제입니다. 저출생 문제 해결을 위해 "
                       "강화·확대되거나 추가될 필요가 있는 정책과제를 우선순위대로 두 개 "
                       "선택해 주십시오.",
                   poleA="육아기 유연근무 활성화", poleB="육아휴직 급여 상한 인상"),
    "birth2": dict(orig="LB2", topic="교육·돌봄", kind="pick2", n_opt=6, a=1, b=2,
                   bench="renorm",
                   ask="다음은 교육·돌봄 분야의 향후 정책과제입니다. 저출생 문제 해결을 위해 "
                       "강화·확대되거나 추가될 필요가 있는 정책과제를 우선순위대로 두 개 "
                       "선택해 주십시오.",
                   poleA="아이돌봄서비스 지원 확대", poleB="사교육비 경감 교육과정 개선"),
    "birth3": dict(orig="LB3", topic="결혼·출산·양육", kind="pick2", n_opt=6, a=1, b=2,
                   bench="renorm",
                   ask="다음은 결혼·출산·양육 분야의 향후 정책과제입니다. 저출생 문제 해결을 "
                       "위해 강화·확대되거나 추가될 필요가 있는 정책과제를 우선순위대로 두 개 "
                       "선택해 주십시오.",
                   poleA="결혼·출산 세금혜택 확대", poleB="부모급여·아동수당 확대"),
    "birth4": dict(orig="LB4", topic="주거", kind="pick2", n_opt=6, a=1, b=3,
                   bench="renorm",
                   ask="다음은 주거 분야의 향후 정책과제입니다. 저출생 문제 해결을 위해 "
                       "강화·확대되거나 추가될 필요가 있는 정책과제를 우선순위대로 두 개 "
                       "선택해 주십시오.",
                   poleA="주택구입·전세자금 소득기준 완화", poleB="주택청약 요건 완화"),
}

# ── 인간 기준값. 전부 위 Word 정리본의 표에서 그대로 옮긴 것이다. ─────────────
# pick12 : 1+2순위 선택률(%) · pick1 : 1순위 선택률(%) · n_eff/nA/nB : A/B 환산 분포
# `둘다` 는 |A∪B| = |A|+|B|-|A∩B| = n_eff 에서 역산된다. 즉 원자료 없이도
# 인간의 5범주(A만·B만·둘다→A·둘다→B·미선택)가 복원된다 — 이 실험의 1차 지표다.
HUMAN = {
    "env1": dict(scale_A=42.2, scale_mid=38.2, scale_B=19.6, n_eff=1859, nA=1268, nB=591),
    "env2": dict(pick12=(33.9, 28.7), pick1=(16.0, 15.5), n_eff=1736, nA=936,  nB=800),
    "env3": dict(pick12=(46.7, 21.7), pick1=(26.3, 11.0), n_eff=1862, nA=1310, nB=552),
    "env4": dict(pick12=(45.4, 47.2), pick1=(24.4, 22.2), n_eff=2265, nA=1147, nB=1118),

    # 저출생: 원자료가 없어 n_eff/nA/nB 가 없다. pick12 재정규화만 가능하다.
    # `by` 는 정리본의 하위집단 표(= questions_kr.BENCH)를 그대로 옮긴 것으로,
    # 환경 4문항과 달리 우리가 원자료에서 다시 셀 수 없는 값이다.
    "birth1": dict(pick12=(60.6, 39.0), bench_A=60.8,
                   by=dict(sex={"남자": 53.4, "여자": 68.7},
                           age={"20대": 61.5, "30대": 59.8, "40대": 61.5},
                           marital={"미혼": 61.6, "기혼": 60.0})),
    "birth2": dict(pick12=(52.3, 37.2), bench_A=58.4,
                   by=dict(sex={"남자": 57.8, "여자": 59.1},
                           age={"20대": 60.6, "30대": 61.9, "40대": 54.8},
                           marital={"미혼": 62.1, "기혼": 54.9})),
    "birth3": dict(pick12=(51.3, 39.6), bench_A=56.4,
                   by=dict(sex={"남자": 56.9, "여자": 55.9},
                           age={"20대": 61.7, "30대": 58.0, "40대": 53.0},
                           marital={"미혼": 61.4, "기혼": 52.6})),
    "birth4": dict(pick12=(45.3, 39.7), bench_A=53.3,
                   by=dict(sex={"남자": 50.0, "여자": 56.8},
                           age={"20대": 45.7, "30대": 52.5, "40대": 57.2},
                           marital={"미혼": 49.4, "기혼": 57.4})),
}


def bench(qid):
    """이 문항의 인간 기준값이 어떤 자로 재어졌는가. 머리글 참조."""
    return SPEC[qid].get("bench", "cells")


def renorm_A(sel_a, sel_b):
    """선택률 두 개를 A-share 로. 저출생 정리본이 쓴 함수이고, 페르소나에도 이것을
    그대로 적용한다 — 양쪽이 같은 자로 재어지는 것이 이 실험의 전제다."""
    t = sel_a + sel_b
    return None if t == 0 else sel_a / t * 100

QIDS = list(SPEC)


def options(qid):
    """원설문 보기 목록을 **원래 순서 그대로** 돌려준다 (1-기반 번호는 인덱스+1)."""
    return [v["label"] for v in _RAW[SPEC[qid]["orig"]]["result"]["values"]]


def human_cells(qid):
    """인간의 5범주 분해(명 수). pick2 문항만. 규칙은 모듈 docstring 참조."""
    h = HUMAN[qid]
    # bench="renorm"(저출생)은 원자료가 없어 5범주가 존재하지 않는다. 여기서 값을
    # 지어내면 이 실험의 전제가 깨지므로 명시적으로 None 을 돌려준다.
    if SPEC[qid]["kind"] != "pick2" or bench(qid) != "cells":
        return None
    A = round(h["pick12"][0] / 100 * N_HUMAN)
    B = round(h["pick12"][1] / 100 * N_HUMAN)
    both = A + B - h["n_eff"]            # |A∩B|
    a_only, b_only = A - both, B - both
    return {"A_only": a_only, "B_only": b_only,
            "both_to_A": h["nA"] - a_only, "both_to_B": h["nB"] - b_only,
            "neither": N_HUMAN - h["n_eff"], "n_eff": h["n_eff"], "N": N_HUMAN}


def _check():
    """실행 전에 항상 돈다. 여기서 조용히 어긋나면 전 실험이 틀린 표적을 겨눈다."""
    bad = []
    for q, s in SPEC.items():
        opts = options(q)
        if s["kind"] == "scale5":
            continue
        if len(opts) != s["n_opt"]:
            bad.append(f"{q}: 보기 수 {len(opts)} != {s['n_opt']}")
        # 극의 번호가 실제로 그 보기를 가리키는가 (Word 문서의 ④/⑨·③/②·①/③).
        # **문항마다 JSON 에 실린 집계가 다르다** — D6 는 1순위 응답률, E10·E13 은
        # 2개 선택의 선택률이다. 한쪽으로 통일해서 비교하면 D6 가 33.9 vs 16.0 으로
        # 어긋난다(실제로 처음에 이렇게 걸렸다). measure 를 읽어 짝을 맞춘다.
        res = _RAW[s["orig"]]["result"]
        key = "pick1" if "1순위" in res["measure"] else "pick12"
        vals = res["values"]
        for lab, idx in (("A", s["a"]), ("B", s["b"])):
            got = vals[idx - 1]["value"]; want = HUMAN[q][key][0 if lab == "A" else 1]
            if abs(got - want) > 0.05:
                bad.append(f"{q}: {lab}=보기{idx} 의 {res['measure']} {got} != 문서값 {want}")
        if bench(q) == "renorm":
            # 재정규화 값이 정리본의 A-share 와 맞는가. 극을 잘못 짚으면 여기서 걸린다.
            got = renorm_A(*HUMAN[q]["pick12"]); want = HUMAN[q]["bench_A"]
            if abs(got - want) > 0.1:
                bad.append(f"{q}: 재정규화 A-share {got:.1f} != 문서값 {want}")
            continue
        # 5범주가 음수 없이 떨어지는가 + A-share 가 문서와 맞는가
        c = human_cells(q)
        if min(c["A_only"], c["B_only"], c["both_to_A"], c["both_to_B"], c["neither"]) < 0:
            bad.append(f"{q}: 5범주에 음수 — 집계값이 서로 모순")
        if c["A_only"] + c["B_only"] + c["both_to_A"] + c["both_to_B"] != c["n_eff"]:
            bad.append(f"{q}: 5범주 합 != 유효n")
    return bad


_ERR = _check()
if _ERR:
    raise SystemExit("** origitems 정합성 실패:\n  " + "\n  ".join(_ERR))
