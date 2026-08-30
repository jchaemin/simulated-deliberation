# -*- coding: utf-8 -*-
"""원설문 형식으로 LLM 에게 묻는다 — instrument-matched replication.

## 무엇을 없애는가

    지금까지  인간: 8지 중 2개 선택 → 연구자 재코딩 → A-share
              LLM : A/B 강제 선택              → A-share      ← 자가 다르다
    이 실험    양쪽 다 원설문 형식 → **같은 함수** → A-share

## 재코딩은 origitems 의 규칙을 그대로 쓴다

`recode()` 는 원자료 정리본(Word)에 적힌 규칙을 코드로 옮긴 것이고, 그 규칙을
인간 집계값에 적용하면 네 문항의 bench_A 가 정확히 재현된다(origitems._check).
**규칙을 여기서 바꾸면 인간 쪽과 자가 달라진다.** 바꿀 일이 있으면 origitems 의
검산부터 다시 돌려야 한다.

`둘 다 선택 → 1순위 기준` 이므로 응답은 집합이 아니라 **순위**여야 한다.
그래서 {"first": 번호, "second": 번호} 로 받는다.

## 두 팔 — 원설문 충실 vs 순서 상쇄

우리 측정으로 선택지 순서·번호는 답을 10~75pp 움직인다. 원설문 순서를 그대로
쓰면 그 편향을 통째로 물려받고, 무작위화하면 "원설문 그대로" 가 아니게 된다.
그래서 둘 다 돌린다.

    arm=F  원설문 보기 순서 그대로 (D6 ④/⑨ · E10 ③/② · E13 ①/③).
           리뷰어가 요구한 복제는 이쪽이다.
    arm=R  페르소나마다 보기 순서를 무작위 치환. 순서와 **번호 라벨을 동시에**
           상쇄한다(항목이 매번 다른 번호를 받으므로).

    F ≈ R  → 격차는 순서 인공물이 아니다. A1 주장이 강해진다.
    F ≠ R  → 그 차이가 곧 9지·8지 목록의 제시 편향 크기다. 이것도 결과다.

D2 는 순위 문항이 아니라 1~5 양극척도이므로, arm=R 은 **앵커를 뒤집는다**
(1=경제성장…5=환경보전). 우리 4요인 중 sign_bias 하나만 살린 형태다.

## 온도 0 인 이유

비교 대상인 그쪽 §4 설문이 T=0 이다(본 파이프라인의 stance survey).
인간은 1인 1응답이므로 페르소나도 1회씩만 답한다 — 표본 반복이 아니라 **인구**다.
T 를 올리면 같은 페르소나가 여러 답을 낼 수 있어 "1인 1표" 대응이 깨진다.

## 버린 선택지

- **저출생 4문항** — 넣지 않았다. 인간 쪽 규칙이 다르고(둘다 해소 불가) 원자료가
  없어 4범주가 복원되지 않는다. 같은 함수를 양쪽에 적용한다는 이 실험의 전제가
  성립하지 않는다. 이유는 origitems 머리글 참조.
- **페르소나당 반복 측정** — 하지 않았다. 위 "온도 0" 참조.
- **번호 대신 문안을 그대로 적게 하기** — 하지 않았다. 원설문 설문지에 번호가
  있으므로 번호가 faithful 이고, difflib 퍼지매칭(그쪽 classify())은 임계값
  0.4 에서 조용히 오분류할 수 있다. 번호가 붙어 생기는 라벨 편향은 arm=R 이 상쇄한다.
"""
import argparse, hashlib, json, os, random, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict

import client
import deliberation
from client import chat
from deliberation import NEUTRAL_SYSTEM, persona_system
import origitems as OI

_HERE = os.path.dirname(os.path.abspath(__file__))
STUB = client.STUB
RES = os.path.join(_HERE, "results", "_stub" if STUB else "")
POOL = os.path.join(_HERE, "data", "persona_pool.jsonl")

ARMS = ("F", "R")
# D2 의 앵커. JSON 의 format.scale.anchors 를 그대로 쓴다.
_D2 = OI._RAW["D2"]["question"]["format"]["scale"]["anchors"]
D2_LOW, D2_HIGH = _D2["1"], _D2["5"]


def _rot(qid, uuid, n):
    """arm=R 의 보기 치환. 결정적이어야 재현된다 — hash() 는 프로세스마다 salt 된다."""
    h = int(hashlib.md5(f"{qid}|{uuid}|rot".encode()).hexdigest()[:12], 16)
    idx = list(range(1, n + 1))
    random.Random(h).shuffle(idx)
    return idx                      # 화면 k번 자리에 원래 idx[k-1]번 보기


def build(qid, arm, uuid):
    """발제문과, 화면 번호 → 원설문 번호 매핑을 함께 돌려준다."""
    s = OI.SPEC[qid]
    if s["kind"] == "scale5":
        lo, hi = (D2_LOW, D2_HIGH) if arm == "F" else (D2_HIGH, D2_LOW)
        body = (f"[문항] {s['ask']}\n"
                f"1 — {lo}\n5 — {hi}\n"
                f"1에서 5 사이의 정수 하나로 답하세요. 3은 중립입니다.\n\n"
                f'JSON으로만 답하세요. 예: {{"scale": <1~5 정수>, "reason": "한 문장"}}')
        # arm=R 은 척도가 뒤집혔으므로 원설문 눈금으로 되돌릴 부호를 함께 준다
        return body, {"flip": arm == "R"}
    opts = OI.options(qid)
    order = list(range(1, len(opts) + 1)) if arm == "F" else _rot(qid, uuid, len(opts))
    lines = "\n".join(f"{k}. {opts[o - 1]}" for k, o in enumerate(order, 1))
    body = (f"[문항] {s['ask']}\n{lines}\n\n"
            f"1순위와 2순위를 보기 번호로 답하세요. 서로 다른 번호여야 합니다.\n"
            f'JSON으로만 답하세요. 예: {{"first": <번호>, "second": <번호>, "reason": "한 문장"}}')
    return body, {"order": order}


def parse(qid, txt, meta):
    """응답 → 원설문 눈금. 실패는 삼키지 않고 올린다."""
    m = re.search(r"\{.*\}", txt or "", re.S)
    d = json.loads(m.group(0)) if m else {}
    s = OI.SPEC[qid]
    reason = d.get("reason") if isinstance(d.get("reason"), str) else None
    if s["kind"] == "scale5":
        v = int(d["scale"])
        if not 1 <= v <= 5:
            raise ValueError(f"scale out of range: {v}")
        if meta["flip"]:
            v = 6 - v                      # 뒤집은 척도를 원설문 눈금으로 되돌린다
        return {"scale": v, "reason": reason}
    o = meta["order"]
    f, sec = int(d["first"]), int(d["second"])
    for x in (f, sec):
        if not 1 <= x <= len(o):
            raise ValueError(f"pick out of range: {x}")
    if f == sec:
        raise ValueError(f"duplicate pick: {f}")
    return {"first": o[f - 1], "second": o[sec - 1], "reason": reason}   # 원설문 번호로 환원


def recode(qid, r):
    """**인간에게 적용된 것과 같은 규칙.** origitems 머리글의 Word 인용 참조.

    A만→A · B만→B · 둘다→1순위 기준 · 둘다 미선택→neither
    D2 는 순위 문항이 아니라 1·2→A / 3→중립 / 4·5→B.
    """
    s = OI.SPEC[qid]
    if s["kind"] == "scale5":
        v = r["scale"]
        return "A" if v <= 2 else ("B" if v >= 4 else "mid")
    a, b = s["a"], s["b"]
    picks = (r["first"], r["second"])
    ia, ib = a in picks, b in picks
    if ia and not ib:
        return "A"
    if ib and not ia:
        return "B"
    if ia and ib:
        return "A" if r["first"] == a else "B"      # 1순위 기준
    return "neither"


def ask_one(qid, body, meta, seed, system, max_tokens=300):
    txt = chat(deliberation.MODEL,
               [{"role": "system", "content": system},
                {"role": "user", "content": body}],
               temperature=0.0, max_tokens=max_tokens, seed=seed,
               response_format={"type": "json_object"})
    if not isinstance(txt, str) or not txt.strip():
        raise RuntimeError("empty content")
    return parse(qid, txt, meta)


def main(argv=None):
    ap = argparse.ArgumentParser(description="원설문 형식 복제 (환경 4문항)")
    ap.add_argument("--model", default="openai/gpt-4.1-mini")
    ap.add_argument("--qs", default="all")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--persona", type=int, default=640,
                    help="페르소나 N명이 문항당 1회씩 답한다 (0=맨 모델, -n 회 반복)")
    ap.add_argument("--persona-seed", type=int, default=11)
    ap.add_argument("-n", type=int, default=80, help="--persona 0 일 때의 반복 수")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    qs = OI.QIDS if a.qs == "all" else [x.strip() for x in a.qs.split(",")]
    miss = [q for q in qs if q not in OI.SPEC]
    if miss:
        print(f"** 없는 문항: {', '.join(miss)} (가능: {', '.join(OI.QIDS)})"); return 2
    arms = [x.strip().upper() for x in a.arms.split(",") if x.strip()]
    if any(x not in ARMS for x in arms):
        print(f"** arm 은 {'/'.join(ARMS)} 만 됩니다."); return 2
    if a.persona < 0 or a.n < 1:
        print("** --persona 는 0 이상, -n 은 1 이상이어야 합니다."); return 2

    # ── 첫 호출 전에 인물·라우팅·경로를 전부 확정한다 ───────────────────────
    people = []
    if a.persona:
        if not os.path.exists(POOL):
            print(f"** 페르소나 풀이 없습니다: {POOL}"); return 2
        pool = [json.loads(l) for l in open(POOL, encoding="utf-8")]
        if len(pool) < a.persona:
            print(f"** 풀에 {len(pool)}명뿐입니다 (요청 {a.persona})."); return 2
        # 인간은 1인 1응답이다. 인구 전체를 재현하는 것이므로 **풀 순서대로 전원**을
        # 쓴다 — biasprobe 의 인구셀 라운드로빈은 부분표집(N<640)용이라 여기서는
        # 오히려 순서만 바꿀 뿐이다. N=640 이면 두 방식이 같은 집합을 준다.
        people = pool[:a.persona]
    reps = a.persona or a.n

    try:
        pf = client.preflight(a.model)
    except Exception as e:
        print(f"** 라우팅 실패: {e}"); return 2
    optkey = ",".join(f"{k}={v}" for k, v in sorted(pf["options"].items()))

    os.makedirs(RES, exist_ok=True)
    cond = (f"orig1|{','.join(sorted(qs))}|{','.join(sorted(arms))}|{a.persona}"
            f"|{a.persona_seed}|{reps}|{a.seed}|{pf['provider']}|{pf['sent_model']}|{optkey}")
    cid = hashlib.sha256(cond.encode()).hexdigest()[:6]
    path = os.path.join(RES, f"origsurvey_{a.model.replace('/', '__')}_{cid}.json")
    if os.path.exists(path) and not a.force:
        print(f"** 이미 있습니다: {path}\n   덮어쓰려면 --force"); return 2

    who = f"페르소나 {a.persona}명" if a.persona else f"맨 모델 ×{a.n}"
    calls = len(qs) * len(arms) * reps
    print(f"■ origsurvey(원설문 형식) · {a.model} · {who}{' [스텁]' if STUB else ''}")
    print(f"  문항 {len(qs)} × arm {len(arms)}({'/'.join(arms)}) × {reps} = {calls:,}회 · 동시 {a.workers}")
    print(f"  공급자 {pf['provider']} · 보낼 모델 id {pf['sent_model']} · 옵션 {optkey} · temperature=0")
    if a.dry:
        print("  --dry: 호출하지 않고 끝냅니다."); return 0

    deliberation.MODEL = a.model
    t0 = time.time()
    jobs = []
    for k, qid in enumerate(qs):
        for ai, arm in enumerate(arms):
            for i in range(reps):
                p = people[i] if a.persona else None
                uid = p["uuid"] if p else f"bare{i}"
                body, meta = build(qid, arm, uid)
                jobs.append((qid, arm, i, uid, body, meta, p,
                             a.seed + k * 1_000_000 + ai * 100_000 + i))

    done = [0]
    def one(j):
        qid, arm, i, uid, body, meta, p, seed = j
        done[0] += 1
        if done[0] % 500 == 0:
            print(f"    {done[0]:,}/{len(jobs):,}", flush=True)
        sysmsg = persona_system(p) if p else NEUTRAL_SYSTEM
        err = None
        for mt in (300, 700):
            try:
                r = ask_one(qid, body, meta, seed, sysmsg, max_tokens=mt)
                err = None
                break
            except Exception as e:
                err = {"qid": qid, "arm": arm, "i": i,
                       "err": f"{type(e).__name__}: {str(e)[:90]}"}
        if err is not None:
            return None, err
        rec = {"qid": qid, "arm": arm, "i": i, "uuid": uid, "code": recode(qid, r)}
        rec.update(r)
        return rec, None

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        pairs = list(ex.map(one, jobs))
    recs = [r for r, _ in pairs if r is not None]
    fails = [f for _, f in pairs if f is not None]
    if not recs:
        print("** 남은 응답이 없습니다. 저장하지 않습니다."); return 1

    # ── 요약 ────────────────────────────────────────────────────────────────
    def cells(rows):
        c = Counter(r["code"] for r in rows)
        n = len(rows); eff = c["A"] + c["B"]
        return {"N": n, "A": c["A"], "B": c["B"], "mid": c["mid"], "neither": c["neither"],
                "n_eff": eff, "A_share": round(100 * c["A"] / eff, 1) if eff else None,
                "coverage": round(100 * eff / n, 1) if n else None}
    by = {q: {arm: cells([r for r in recs if r["qid"] == q and r["arm"] == arm])
              for arm in arms} for q in qs}
    # 둘다 선택 비율 — 강제 이분에서는 잴 수 없던 값
    both = {}
    for q in qs:
        if OI.SPEC[q]["kind"] != "pick2":
            continue
        s = OI.SPEC[q]
        for arm in arms:
            rows = [r for r in recs if r["qid"] == q and r["arm"] == arm]
            nb = sum(1 for r in rows if s["a"] in (r["first"], r["second"])
                     and s["b"] in (r["first"], r["second"]))
            both[f"{q}|{arm}"] = round(100 * nb / len(rows), 1) if rows else None
    # 전체 보기 분포 (1+2순위 선택률) — 인간 집계와 직접 비교되는 형태
    dist = {}
    for q in qs:
        if OI.SPEC[q]["kind"] != "pick2":
            continue
        for arm in arms:
            rows = [r for r in recs if r["qid"] == q and r["arm"] == arm]
            c = Counter()
            for r in rows:
                c[r["first"]] += 1; c[r["second"]] += 1
            dist[f"{q}|{arm}"] = [round(100 * c[k] / len(rows), 1)
                                  for k in range(1, len(OI.options(q)) + 1)]
    scale_dist = {f"{q}|{arm}": dict(sorted(Counter(
                      r["scale"] for r in recs if r["qid"] == q and r["arm"] == arm).items()))
                  for q in qs if OI.SPEC[q]["kind"] == "scale5" for arm in arms}

    # bench="renorm" 문항은 인간 기준값이 per-respondent 재코딩이 아니라 선택률
    # 재정규화다. 같은 함수를 페르소나에도 적용한 값을 여기서 함께 저장한다 —
    # 나중에 재계산하면 어느 자를 썼는지 흐려진다.
    renorm = {}
    for q in qs:
        if OI.SPEC[q]["kind"] != "pick2":
            continue
        s = OI.SPEC[q]
        renorm[q] = {}
        for arm in arms:
            rows = [r for r in recs if r["qid"] == q and r["arm"] == arm]
            n = len(rows)
            if not n:
                continue
            sa = sum(1 for r in rows if s["a"] in (r["first"], r["second"])) / n * 100
            sb = sum(1 for r in rows if s["b"] in (r["first"], r["second"])) / n * 100
            renorm[q][arm] = {"sel_A": round(sa, 2), "sel_B": round(sb, 2),
                              "A_share_renorm": OI.renorm_A(sa, sb), "n": n}

    out = {"design": "origformat-env-v1", "renorm": renorm, "bench_kind": {q: OI.bench(q) for q in qs}, "model": a.model, "qs": qs, "arms": arms,
           "cond_id": cid, "provider": pf["provider"], "endpoint": pf["endpoint"],
           "sent_model": pf["sent_model"], "request_options": pf["options"],
           "temperature": 0.0, "persona": a.persona, "persona_seed": a.persona_seed,
           "reps": reps, "seed": a.seed, "stub": STUB,
           "elapsed_sec": round(time.time() - t0, 1),
           "n_ok": len(recs), "n_fail": len(fails), "failures": fails[:50],
           "recode_rule": "A만→A · B만→B · 둘다→1순위 · 둘다미선택→neither "
                          "(D2: 1·2→A / 3→mid / 4·5→B)",
           "by_question": by, "both_pct": both, "option_dist_pick12": dist,
           "scale_dist": scale_dist, "records": recs}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

    print(f"\n{'='*84}")
    print(f"  {a.model} · {who} · 유효 {len(recs):,} / 실패 {len(fails)}")
    print(f"{'='*84}")
    print(f"  {'문항':7}{'arm':5}{'A':>7}{'B':>7}{'중립':>7}{'미선택':>8}{'커버리지':>9}{'A-share':>9}   인간")
    for q in qs:
        h = OI.human_cells(q)
        if h:
            ha = h["A_only"] + h["both_to_A"]
            htxt = f"cov {100*h['n_eff']/h['N']:.1f}% · A {100*ha/h['n_eff']:.1f}%"
        elif OI.bench(q) == "renorm":
            # 저출생: 인간 쪽 기준값이 선택률 재정규화라 커버리지 개념이 없다.
            htxt = f"재정규화 A {OI.HUMAN[q]['bench_A']:.1f}%"
        else:
            hh = OI.HUMAN[q]
            htxt = f"cov {100*hh['n_eff']/OI.N_HUMAN:.1f}% · A {100*hh['nA']/hh['n_eff']:.1f}%"
        for arm in arms:
            c = by[q][arm]
            print(f"  {q:7}{arm:5}{c['A']:7}{c['B']:7}{c['mid']:7}{c['neither']:8}"
                  f"{(c['coverage'] or 0):8.1f}%{(c['A_share'] or 0):8.1f}%   {htxt if arm==arms[0] else ''}")
    print(f"\n  호출 {len(jobs):,} · {out['elapsed_sec']}초 · 저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
