# Shared engine for the survey and deliberation pipelines. Every experiment in the
# paper is a configuration of the functions here; run_survey.py and
# run_deliberation.py expose the switches.
import json, random, re, math, difflib, hashlib, collections
import llm
from llm import persona_system, _agent_name
from questions_kr import QUESTIONS_KR, BENCH

ISSUES = ["env1", "env2", "env3", "env4", "birth1", "birth2", "birth3", "birth4"]

def dh(*parts):  # deterministic across processes (builtin hash is salted)
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)

def load_pool(path="data/persona_pool.jsonl"):
    pool = [json.loads(l) for l in open(path)]
    return pool, {p["uuid"]: p for p in pool}

def load_survey(path="data/survey_main.jsonl"):
    sv = collections.defaultdict(dict); first = collections.defaultdict(dict)
    for l in open(path):
        r = json.loads(l)
        sv[r["qid"]][r["uuid"]] = r["stance"]; first[r["qid"]][r["uuid"]] = r.get("first")
    return sv, first

def order_of(first, uuid, qid):
    f = first.get(qid, {}).get(uuid)
    return f if f in ("A", "B") else random.Random(dh(uuid, qid, "nn")).choice(["A", "B"])

def classify(choice, q):
    if choice is None: return None
    if "중립" in choice or "모르" in choice: return 0
    ha = q["poleA"].split("(")[0].strip(); hb = q["poleB"].split("(")[0].strip()
    ra = difflib.SequenceMatcher(None, choice, q["poleA"]).ratio() + difflib.SequenceMatcher(None, choice, ha).ratio()
    rb = difflib.SequenceMatcher(None, choice, q["poleB"]).ratio() + difflib.SequenceMatcher(None, choice, hb).ratio()
    if max(ra, rb) < 0.4 or ra == rb: return None
    return 1 if ra > rb else -1

# ---------- persona specifications (Table 3 columns) ----------
AGE_KR = {"20s": "20대", "30-44": "30~44세", "45-59": "45~59세", "60+": "60세 이상"}

def system_prompt(p, variant):
    if variant == "full":
        return persona_system(p)
    if variant == "demographics":
        return (f"당신은 아래 인구통계 특성을 가진 대한민국 시민입니다.\n"
                f"성별: {p['sex']} · 연령대: {AGE_KR[p['age_band']]} · 학력: {p['edu4']} · 거주지역: {p['region_group']}\n"
                f"답변은 항상 지정된 JSON 형식으로만 작성하세요.")
    if variant == "citizen":
        return "당신은 대한민국 시민입니다. 답변은 항상 지정된 JSON 형식으로만 작성하세요."
    if variant == "none":
        return "답변은 항상 지정된 JSON 형식으로만 작성하세요."
    raise ValueError(variant)

# ---------- population-matched side assignment (Appendix G) ----------
def _agesurv(a): return "20대" if 20 <= a <= 29 else "30대" if 30 <= a <= 39 else "40대" if 40 <= a <= 49 else None
def _marital2(m): return "기혼" if m == "배우자있음" else "미혼" if m == "미혼" else None
def _logit(p): p = min(max(p, 0.02), 0.98); return math.log(p / (1 - p))
def _sig(x): return 1 / (1 + math.exp(-x))

def cellP(p, qid):
    fam = "env" if qid.startswith("env") else "birth"
    axes = ["sex", "age_band", "edu4", "region_group"] if fam == "env" else ["sex", "age_surv", "marital"]
    base = BENCH[qid]["overall"] / 100; lo = _logit(base)
    for ax in axes:
        lvl = {"sex": p["sex"], "age_band": p["age_band"], "edu4": p["edu4"], "region_group": p["region_group"],
               "age_surv": _agesurv(p["age"]), "marital": _marital2(p["marital_status"])}.get(ax)
        sv = BENCH[qid].get(ax, {}).get(lvl)
        if sv is not None: lo += _logit(sv / 100) - _logit(base)
    return min(max(_sig(lo), 0.05), 0.95)

def inj_side(p, qid):
    return 1 if random.Random(dh(p["uuid"], qid, "inj")).random() < cellP(p, qid) else -1

# ---------- survey instruments (Section 4.1, Table 16) ----------
def ask_natural(p, q, firstpole, variant="full", temperature=0.0):
    a, b = (q["poleA"], q["poleB"]) if firstpole == "A" else (q["poleB"], q["poleA"])
    u = (f"[쟁점] {q['topic']}\n다음 두 입장 중 당신의 생각에 더 가까운 것은 무엇입니까? 반드시 하나를 선택하세요.\n"
         f"· {a}\n· {b}\n"
         'JSON으로만, 위 두 입장 중 하나를 그대로 적으세요: {"choice": "..."}')
    t = llm.chat(llm.MODEL, [{"role": "system", "content": system_prompt(p, variant)},
                                          {"role": "user", "content": u}],
                       temperature=temperature, max_tokens=80, response_format={"type": "json_object"})
    m = re.search(r'"choice"\s*:\s*"([^"]*)"', t or "")
    return m.group(1) if m else None

def ask_labeled(p, q, swap=False, temperature=0.7):
    pa, pb = (q["poleB"], q["poleA"]) if swap else (q["poleA"], q["poleB"])
    u = (f"[쟁점] {q['topic']}\n"
         f"(A) {pa}\n(B) {pb}\n\n"
         "당신은 A와 B 중 어느 쪽을 선택하시겠습니까? 정말 어느 쪽도 아니면 '중립'.\n"
         'JSON으로만: {"choice": "A" 또는 "B" 또는 "중립"}')
    t = llm.chat(llm.MODEL, [{"role": "system", "content": persona_system(p)},
                                          {"role": "user", "content": u}],
                       temperature=temperature, max_tokens=30, response_format={"type": "json_object"})
    m = re.search(r'"choice"\s*:\s*"?(A|B|중립)', t or "")
    return m.group(1) if m else None

def ask_bipolar(p, q, temperature=0.0):
    u = (f"[쟁점] {q['topic']}\n[선택지] (A) {q['poleA']}   vs   (B) {q['poleB']}\n"
         f"[질문] 당신은 A와 B 중 어느 쪽에 더 가깝습니까?\n"
         f"[척도] +2 A를 매우 지지 · +1 A를 지지 · 0 중립·유보 · -1 B를 지지 · -2 B를 매우 지지"
         '\n\n현재 당신의 입장을 JSON으로. 예: {"stance": <-2~2 정수>}')
    t = llm.chat(llm.MODEL, [{"role": "system", "content": persona_system(p)},
                                          {"role": "user", "content": u}],
                       temperature=temperature, max_tokens=60, response_format={"type": "json_object"})
    m = re.search(r'"stance"\s*:\s*(-?[0-2])', t or "")
    return int(m.group(1)) if m else None

def ask_two_ratings(p, q, pole, temperature=0.7):
    u = (f"[쟁점] {q['topic']}\n당신은 아래 입장을 얼마나 지지합니까?\n[입장] {pole}\n"
         "0 = 지지하지 않음, 1 = 어느 정도 지지, 2 = 강하게 지지\n"
         'JSON으로만: {"support": 0 또는 1 또는 2}')
    t = llm.chat(llm.MODEL, [{"role": "system", "content": persona_system(p)},
                                          {"role": "user", "content": u}],
                       temperature=temperature, max_tokens=25, response_format={"type": "json_object"})
    m = re.search(r'"support"\s*:\s*([012])', t or "")
    return int(m.group(1)) if m else None

# ---------- deliberation engine (Section 5) ----------
def make_names(panel):
    names = {}; used = set()
    for i in range(len(panel)):
        n = _agent_name(panel[i], i)
        if n in used: n = f"{n}({i+1})"
        used.add(n); names[i] = n
    return names

def demo_tag(p): return f"{p['sex']}·{p['age_band']}·{p['edu4']}"

def stance_survey(p, q, qid, vis, first, private_preamble=False):
    fp = order_of(first, p["uuid"], qid)
    a, b = (q["poleA"], q["poleB"]) if fp == "A" else (q["poleB"], q["poleA"])
    pre = "이것은 토론과 별개의 비공개 설문입니다. 다음 두 입장 중 당신의 생각에 더 가까운 것은? 반드시 하나를 선택하세요.\n" \
        if private_preamble else \
        "다음 두 입장 중 당신의 생각에 더 가까운 것은 무엇입니까? 반드시 하나를 선택하세요.\n"
    u = (f"[쟁점] {q['topic']}\n" + (f"[지금까지의 토론]\n{vis}\n\n" if vis else "") + pre +
         f"· {a}\n· {b}\nJSON으로만, 위 두 입장 중 하나를 그대로 적으세요: {{\"choice\": \"...\"}}")
    t = llm.chat(llm.MODEL, [{"role": "system", "content": persona_system(p)},
                                          {"role": "user", "content": u}],
                       temperature=0.0, max_tokens=80, response_format={"type": "json_object"})
    m = re.search(r'"choice"\s*:\s*"([^"]*)"', t or "")
    return classify(m.group(1) if m else None, q)

def speak(p, q, vis, name, side=None, temperature=1.0):
    cue = (f"[당신의 입장] 당신은 '{q['poleA'] if side > 0 else q['poleB']}' 쪽을 지지합니다.\n" if side in (1, -1) else "")
    head = (f"[쟁점] {q['topic']}\n[논점] {q['poleA']}  또는  {q['poleB']}\n" + cue
            + (f"[지금까지의 토론]\n{vis}\n" if vis else "[지금까지의 토론] 아직 발언이 없습니다.\n")
            + f"\n당신은 {name}입니다. 위 논의를 이어서 2~4문장으로 자신의 생각을 말하세요. 발언만 JSON으로: {{\"public\": \"...\"}}")
    t = llm.chat(llm.MODEL, [{"role": "system", "content": persona_system(p)},
                                          {"role": "user", "content": head}],
                       temperature=temperature, max_tokens=400, response_format={"type": "json_object"})
    try:
        return json.loads(t).get("public", "")
    except Exception:
        m = re.search(r'"public"\s*:\s*"(.*?)"', t or "", re.S)
        return m.group(1) if m else "..."

def open_speak(p, q, name, side, temperature=1.0):
    pole = q["poleA"] if side > 0 else q["poleB"]
    head = (f"[쟁점] {q['topic']}\n[논점] {q['poleA']}  또는  {q['poleB']}\n[당신의 입장] 당신은 '{pole}' 쪽입니다.\n\n"
            f"당신은 {name}입니다. 위 입장을 지지하는 이유를 2~4문장으로 말하세요. 발언만 JSON으로: {{\"public\": \"...\"}}")
    t = llm.chat(llm.MODEL, [{"role": "system", "content": persona_system(p)},
                                          {"role": "user", "content": head}],
                       temperature=temperature, max_tokens=400, response_format={"type": "json_object"})
    try:
        return json.loads(t).get("public", "")
    except Exception:
        m = re.search(r'"public"\s*:\s*"(.*?)"', t or "", re.S)
        return m.group(1) if m else "..."

def debate(panel, ids, qid, seed, r0, first, cue="none", rounds=3,
           disclosure="name", turns="sequential", speech_temp=1.0, cond="natural",
           opener=None):
    """One room. cue: none | side (round-1 cue line) | opening (argued round-0 turn).
    disclosure: name | demographics. turns: sequential | simultaneous.
    opener: 'A' or 'B' moves an agent holding that side to the front of round 1."""
    q = QUESTIONS_KR[qid]; rng = random.Random(seed); n = len(panel)
    base = make_names(panel)
    names = {i: (f"{base[i]}({demo_tag(panel[i])})" if disclosure == "demographics" else base[i]) for i in range(n)}
    inc = {i: [r0[i]] for i in range(n)}; exc = {i: [r0[i]] for i in range(n)}
    convo = []
    if cue == "opening":
        order = list(range(n)); rng.shuffle(order)
        for i in order: convo.append((i, open_speak(panel[i], q, names[i], r0[i], speech_temp)))
    for r in range(1, rounds + 1):
        order = list(range(n)); rng.shuffle(order)
        if opener in ("A", "B") and r == 1:
            want = 1 if opener == "A" else -1
            front = [i for i in order if r0[i] == want]
            if front:
                order.remove(front[0]); order = [front[0]] + order
        round_utts = []
        for i in order:
            seen = convo if turns == "simultaneous" else convo + round_utts
            vis = "\n".join(f"{names[a]}: {u}" for a, u in seen)
            side = r0[i] if (cue == "side" and r == 1) else None
            round_utts.append((i, speak(panel[i], q, vis, names[i], side, speech_temp)))
        convo += round_utts
        for i in range(n):
            vall = "\n".join(f"{names[a]}: {u}" for a, u in convo)
            vown = "\n".join(f"{names[a]}: {u}" for a, u in convo if a != i)
            inc[i].append(stance_survey(panel[i], q, qid, vall, first))
            exc[i].append(stance_survey(panel[i], q, qid, vown, first))
    return {"issue": qid, "seed": seed, "cond": cond, "ids": ids,
            "included": inc, "excluded": exc,
            "transcript": [[names[i], u] for i, u in convo]}

def monologue(panel, ids, qid, seed, r0, first, rounds=3, speech_temp=1.0):
    q = QUESTIONS_KR[qid]; names = make_names(panel); n = len(panel)
    sides = {i: [r0[i]] for i in range(n)}; own = {i: [] for i in range(n)}
    for r in range(1, rounds + 1):
        for i in range(n): own[i].append(speak(panel[i], q, "\n".join(own[i]), names[i], None, speech_temp))
        for i in range(n): sides[i].append(stance_survey(panel[i], q, qid, "\n".join(own[i]), first))
    return {"issue": qid, "seed": seed, "cond": "mono", "ids": ids, "sides": sides}

# ---------- room construction ----------
def build_rooms(A, B, composition, n_rooms, base_seed, size=6):
    """Non-overlapping draws. composition: '3-3' | '6-0' | '0-6' (counts of side-A, side-B agents)."""
    ca, cb = {"3-3": (size // 2, size - size // 2), "6-0": (size, 0), "0-6": (0, size)}[composition]
    rng = random.Random(base_seed); a = A[:]; b = B[:]; rng.shuffle(a); rng.shuffle(b)
    out = []
    for d in range(n_rooms):
        if len(a) >= ca and len(b) >= cb:
            ids = a[:ca] + b[:cb]; del a[:ca]; del b[:cb]
            r0 = {i: (1 if i < ca else -1) for i in range(size)}
            out.append((ids, r0, base_seed + d))
    return out
