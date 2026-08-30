# -*- coding: utf-8 -*-
"""논문 Appendix 표 생성 — 원설문 형식 실험을 본문 Table 3/4 와 같은 꼴로.

## 무엇을 보이려는 표인가
본문의 주장은 "재현 실패는 도구가 아니라 모델에 있다"이다. Appendix B 는 네 가지
**LLM 용 응답 형식**을 비교해 그것을 뒷받침했지만, 남는 반론이 하나 있었다 —
"인간은 8지선다 순위 응답을 했고 LLM 은 양자택일을 했으니, 애초에 다른 것을 잰
것 아니냐". 이 표는 그 반론을 닫는다. **인간이 받은 문항 그대로** 페르소나에게
묻고, **인간에게 적용된 것과 같은 함수**로 환산한다. 격차는 줄지 않는다.

## 두 패널이 서로 다른 자를 쓰는 이유
origitems 머리글 참조. 요약하면 환경 4문항은 KEI 원자료(n=3,008)가 공개돼 있어
per-respondent 재코딩을 양쪽에 적용할 수 있고, 저출생 4문항은 원자료가 없어
선택률 재정규화만 양쪽에 적용할 수 있다. 본문 Table 3 도 이미 두 패널에서 서로
다른 기준을 쓰므로(환경=방향성 응답자, 저출생=1+2순위 재정규화) 새로 생긴 구분이
아니다. 각 패널 안에서는 인간과 페르소나가 반드시 같은 자로 재어진다.

## 인간 하위집단 값을 원자료에서 다시 세는 이유
환경 4문항은 KEI 원자료로 직접 센다. 정리본 표를 옮겨 적으면 (a) 논문 Table 9~12
와 어긋나도 알 수 없고 (b) 연령 구간을 본문과 맞출 수 없다 — 정리본은 10세 단위인데
본문은 19-29/30-44/45-59/60+ 다. SQ3(만 나이, 19~69 연속)에서 본문 구간을 그대로
만든다. 재계산값이 논문 Table 9~12 와 맞는지는 --verify 가 검산한다.
저출생은 원자료가 없어 정리본 표를 그대로 쓴다(origitems.HUMAN[...]["by"]).

## 버린 선택지
- **저출생을 per-respondent 재코딩으로 비교하기** — 하지 않았다. 인간 쪽에 대응
  통계가 없어 같은 자가 되지 않는다. 커버리지/미선택 수치는 참고로만 싣는다.
- **이혼·사별 페르소나(70명)를 기혼에 합치기** — 하지 않았다. 정리본의 혼인상태
  표가 미혼/기혼 2범주뿐이라 어디에 넣어도 근거가 없다. 해당 행에서 제외한다.
"""
import collections, json, os, sys
import origitems as OI

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SAV = os.path.join(ROOT, "microdata", "kei2025_raw.sav")
POOL = os.path.join(HERE, "data", "persona_pool.jsonl")
FB = os.path.join(os.path.dirname(ROOT), "data", "survey_main.jsonl")  # the main NL forced-choice survey

ENVQ = ["env1", "env2", "env3", "env4"]
BIRQ = ["birth1", "birth2", "birth3", "birth4"]
LABEL = {"env1": "Env. priority", "env2": "Env. means", "env3": "Clim. strategy",
         "env4": "Clim. tech", "birth1": "Work–family", "birth2": "Educ.–care",
         "birth3": "Econ. support", "birth4": "Housing"}
# 주의: 본문 Table 3(b) 의 열 순서는 Work–family / Educ.–care / Econ. support / Housing
# 이고 이는 LB1/LB2/LB3/LB4 순이다. birth3=결혼·출산·양육=Econ. support 다.

DM3_MAP = {1: "Capital area", 2: "Capital area", 3: "Chungcheong",
           4: "Honam", 5: "Yeongnam", 6: "Yeongnam", 7: "Gangwon/Jeju"}
DM4_MAP = {1: "≤ middle", 2: "High school", 3: "College", 4: "Graduate"}
EDU_P = {"≤중졸": "≤ middle", "고졸": "High school", "대졸": "College", "대학원": "Graduate"}
REG_P = {"수도권": "Capital area", "영남": "Yeongnam", "호남": "Honam",
         "충청": "Chungcheong", "강원·제주": "Gangwon/Jeju"}


def env_band(a):
    return "19–29" if a < 30 else "30–44" if a < 45 else "45–59" if a < 60 else "60+"


def bir_band(a):
    return "20s" if a < 30 else "30s" if a < 40 else "40s" if a < 50 else None


def humans_env():
    """KEI 원자료에서 환경 4문항을 재코딩하고 하위집단 축을 붙인다."""
    import pyreadstat
    df, _ = pyreadstat.read_sav(SAV, usecols=["SQ3", "DM1", "DM3", "DM4", "D2",
                                              "D6", "D6_m2", "E10", "E10_m2",
                                              "E13", "E13_m2"])
    out = []
    for _, r in df.iterrows():
        rec = {"Sex": "Male" if r["DM1"] == 1 else "Female",
               "Age": env_band(r["SQ3"]),
               "Education": DM4_MAP[int(r["DM4"])],
               "Region": DM3_MAP[int(r["DM3"])]}
        rec["env1"] = "A" if r["D2"] <= 2 else ("B" if r["D2"] >= 4 else "mid")
        for q in ("env2", "env3", "env4"):
            s = OI.SPEC[q]
            f, sec = r[s["orig"]], r[s["orig"] + "_m2"]
            ia, ib = s["a"] in (f, sec), s["b"] in (f, sec)
            rec[q] = ("A" if ia and not ib else "B" if ib and not ia else
                      ("A" if f == s["a"] else "B") if ia and ib else "neither")
        out.append(rec)
    return out


def personas(results_path, arm="F"):
    """페르소나 응답 + 하위집단 축. picks 는 재정규화(저출생)에 쓴다."""
    pool = {p["uuid"]: p for p in map(json.loads, open(POOL, encoding="utf-8"))}
    d = json.load(open(results_path, encoding="utf-8"))
    by = collections.defaultdict(dict)
    for r in d["records"]:
        if r["arm"] == arm:
            by[r["uuid"]][r["qid"]] = r
    out = []
    for u, qs in by.items():
        p = pool[u]
        mar = {"미혼": "Single", "배우자있음": "Married"}.get(p["marital_status"])
        rec = {"Sex": "Male" if p["sex"] == "남자" else "Female",
               "Age": env_band(p["age"]), "AgeB": bir_band(p["age"]),
               "Education": EDU_P[p["edu4"]], "Region": REG_P[p["region_group"]],
               "Marital": mar}
        for qid, r in qs.items():
            rec[qid] = r["code"]
            if r.get("first") is not None:
                rec[qid + "_picks"] = (r["first"], r["second"])
        out.append(rec)
    return out


def forced_binary():
    """본문 주 도구(자연어 양자택일)의 페르소나 응답 + 하위집단 축."""
    pool = {p["uuid"]: p for p in map(json.loads, open(POOL, encoding="utf-8"))}
    by = collections.defaultdict(dict)
    for l in open(FB, encoding="utf-8"):
        r = json.loads(l)
        by[r["uuid"]][r["qid"]] = "A" if r["stance"] == 1 else "B"
    out = []
    for u, qs in by.items():
        p = pool[u]
        mar = {"미혼": "Single", "배우자있음": "Married"}.get(p["marital_status"])
        rec = {"Sex": "Male" if p["sex"] == "남자" else "Female",
               "Age": env_band(p["age"]), "AgeB": bir_band(p["age"]),
               "Education": EDU_P[p["edu4"]], "Region": REG_P[p["region_group"]],
               "Marital": mar, **qs}
        out.append(rec)
    return out


def share_recode(recs, qid):
    """방향성 응답자 중 A 비율. 환경 패널의 자."""
    v = [r[qid] for r in recs if r.get(qid) in ("A", "B")]
    return (sum(1 for x in v if x == "A") / len(v) * 100, len(v)) if v else (None, 0)


def share_renorm(recs, qid):
    """극 보기의 1+2순위 선택률을 재정규화. 저출생 패널의 자."""
    s = OI.SPEC[qid]
    have = [r for r in recs if qid + "_picks" in r]
    n = len(have)
    if not n:
        return None, 0
    sa = sum(1 for r in have if s["a"] in r[qid + "_picks"]) / n * 100
    sb = sum(1 for r in have if s["b"] in r[qid + "_picks"]) / n * 100
    return OI.renorm_A(sa, sb), n


# ── 표 렌더링 ────────────────────────────────────────────────────────────────
ENV_AX = [("Sex", ["Male", "Female"]),
          ("Age", ["19–29", "30–44", "45–59", "60+"]),
          ("Education", ["≤ middle", "High school", "College", "Graduate"]),
          ("Region", ["Capital area", "Yeongnam", "Honam", "Chungcheong", "Gangwon/Jeju"])]
BIR_AX = [("Sex", ["Male", "Female"]),
          ("AgeB", ["20s", "30s", "40s"]),
          ("Marital", ["Single", "Married"])]
BIR_KEY = {"Sex": ("sex", {"Male": "남자", "Female": "여자"}),
           "AgeB": ("age", {"20s": "20대", "30s": "30대", "40s": "40대"}),
           "Marital": ("marital", {"Single": "미혼", "Married": "기혼"})}


def env_rows(persona, human):
    """[(축, 집단, {qid: (llm, hum)}, 평균격차)] — 환경 패널."""
    rows = [("", "Overall", None)]
    for ax, gs in ENV_AX:
        rows += [(ax, g, ax) for g in gs]
    out = []
    for ax, g, key in rows:
        pf = persona if key is None else [r for r in persona if r[key] == g]
        hf = human if key is None else [r for r in human if r[key] == g]
        cells, gaps = {}, []
        for q in ENVQ:
            l, _ = share_recode(pf, q)
            h, _ = share_recode(hf, q)
            cells[q] = (l, h)
            if l is not None and h is not None:
                gaps.append(abs(l - h))
        out.append((ax, g, cells, sum(gaps) / len(gaps) if gaps else None))
    return out


def bir_rows(persona):
    """저출생 패널. 인간 값은 정리본 표(origitems.HUMAN[...]['by'])."""
    rows = [("", "Overall", None)]
    for ax, gs in BIR_AX:
        rows += [(ax, g, ax) for g in gs]
    out = []
    for ax, g, key in rows:
        pf = persona if key is None else [r for r in persona if r.get(key) == g]
        cells, gaps = {}, []
        for q in BIRQ:
            l, _ = share_renorm(pf, q)
            if key is None:
                h = OI.HUMAN[q]["bench_A"]
            else:
                axk, m = BIR_KEY[key]
                h = OI.HUMAN[q]["by"][axk][m[g]]
            cells[q] = (l, h)
            if l is not None:
                gaps.append(abs(l - h))
        out.append((ax, g, cells, sum(gaps) / len(gaps) if gaps else None))
    return out


def fmt(v):
    return "—" if v is None else f"{v:.0f}"


def render(rows, qs, title):
    w = 14
    print(f"\n{title}")
    print(f"  {'Axis':11}{'Group':15}" + "".join(f"{LABEL[q]:>{w}}" for q in qs) + f"{'Gap':>7}")
    prev = None
    for ax, g, cells, gap in rows:
        a = ax if ax != prev else ""
        prev = ax
        line = f"  {a:11}{g:15}"
        for q in qs:
            l, h = cells[q]
            line += f"{fmt(l) + ' / ' + fmt(h):>{w}}"
        line += f"{('—' if gap is None else f'{gap:.0f}'):>7}"
        print(line)
    print(f"  {'Mean absolute gap':26}" +
          "".join(f"{_colgap(rows, q):>{w}}" for q in qs))


def _colgap(rows, q):
    g = [abs(l - h) for _, _, c, _ in rows for l, h in [c[q]]
         if l is not None and h is not None]
    return f"{sum(g)/len(g):.0f}" if g else "—"
