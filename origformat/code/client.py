import hashlib, json, os, random, re, threading, time, pathlib
from openai import OpenAI

# STUB_LLM=1 이면 API 를 부르지 않고 결정적 가짜 응답을 낸다. 배선 검사용이며,
# 산출물은 results/_stub/ 로 격리되어 실측과 섞이지 않는다.
# 스텁 판정은 **이 상수 하나뿐**이다. 다른 모듈은 여기서 import 해 쓴다.
# 모듈마다 따로 판정하면 해석이 갈린다 — 실제로 client 는 bool(getenv) 라
# `STUB_LLM=0` 을 참으로 봤고 biasprobe 는 == "1" 로 거짓으로 봐서, 스텁을 끄려고
# 0 을 넣으면 **가짜 응답이 실측 경로에 stub:false 로 저장**됐다.
# 엄격 비교("1" 일 때만)로 통일한다. 켜는 방법이 하나뿐이어야 실수가 없다.
STUB = os.getenv("STUB_LLM") == "1"

def _load_env():
    envf = pathlib.Path(__file__).resolve().parent / ".env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def route(model):
    """(엔드포인트, 키, 보낼 모델 id) 를 **한 곳에서** 정한다.

    전에는 client() 와 _norm() 이 각자 판단했고 우선순위가 서로 달랐다.
      client()  OPENAI_API_KEY 를 먼저 본다
      _norm()   OPENROUTER_API_KEY 가 **없을 때만** "openai/" 접두사를 뗐다
    두 키를 다 넣으면 OpenAI 엔드포인트로 가면서 모델 id 는 "openai/gpt-4.1-mini"
    그대로 → 400, 그리고 재시도 4회에 20초를 태운다. 교차모델 실험에서 두 키를
    함께 두는 것이 정상 상태이므로, 키 유무가 아니라 **모델 id 가 라우팅을 정한다.**
    """
    _load_env()
    oa, orr = os.getenv("OPENAI_API_KEY"), os.getenv("OPENROUTER_API_KEY")
    vendor, _, bare = model.partition("/")
    openai_native = (not bare) or vendor == "openai"
    if openai_native and oa:
        return ("https://api.openai.com/v1", oa, bare or model)
    if orr:
        return ("https://openrouter.ai/api/v1", orr, model)
    if openai_native:
        raise RuntimeError(f"{model}: OPENAI_API_KEY 도 OPENROUTER_API_KEY 도 없습니다.")
    raise RuntimeError(f"{model}: OpenAI 엔드포인트로 갈 수 없는 모델입니다. "
                       f"OPENROUTER_API_KEY 를 .env 에 넣으세요.")


_CLIENTS = {}
_CLIENT_LOCK = threading.Lock()


def client(model):
    """엔드포인트마다 클라이언트를 **하나만** 만들어 재사용한다.

    전에는 chat() 이 호출될 때마다 OpenAI() 를 새로 만들었다. 그러면 호출마다
    TLS 핸드셰이크를 다시 하고 커넥션이 쌓인다 — 실측으로 12병렬 실행 중
    열린 소켓이 203개까지 갔다. 병렬을 올릴수록 손해가 커지고, 파일 디스크립터
    한계에 걸리면 실패가 특정 시점에 몰린다.
    """
    base, key, _ = route(model)
    k = (base, key)
    c = _CLIENTS.get(k)
    if c is None:
        with _CLIENT_LOCK:
            c = _CLIENTS.get(k)
            if c is None:
                c = OpenAI(base_url=base, api_key=key, max_retries=0)
                _CLIENTS[k] = c
    return c


def _norm(model):
    return route(model)[2]


PROVIDER = {"api.openai.com": "openai", "openrouter.ai": "openrouter"}


def preflight(model):
    """첫 호출 전에 **라우팅과 옵션을 함께** 확정한다.

    반환: {provider, endpoint, sent_model, options}
    provider 가 필요한 이유: 같은 `openai/gpt-4.1-mini` 라도 OPENAI_API_KEY 가 있으면
    OpenAI 직접, 없고 OpenRouter 키만 있으면 OpenRouter 로 간다. 실행 조건이 다른데
    조건 해시와 경로가 같으면 서로 다른 공급자가 낸 수치가 한 파일에 섞이고,
    나중에 어느 쪽이 낸 값인지 재구성할 수 없다.
    """
    if STUB:
        return {"provider": "stub", "endpoint": "stub", "sent_model": model,
                "options": options(model)}
    base, _, sent = route(model)
    host = base.split("//")[1].split("/")[0]
    return {"provider": PROVIDER.get(host, host), "endpoint": base,
            "sent_model": sent, "options": options(model)}


# 재시도해도 결과가 달라지지 않는 오류. 여기 걸리면 즉시 올린다.
_FATAL = ("invalid_api_key", "authentication", "permission", "not_found",
          "model_not_found", "unsupported", "invalid_request", "billing",
          "insufficient_quota", "context_length")


def _fatal(e):
    code = getattr(e, "status_code", None) or getattr(e, "code", None)
    if code in (401, 403, 404):
        return True
    m = str(e).lower()
    return any(k in m for k in _FATAL)


def _stub_shape(text):
    """프롬프트의 `예: {...}` 를 읽어 **요구된 응답 모양**을 알아낸다.

    스텁이 언제나 {"stance": -1|0|1} 만 내면, 다른 응답 공간을 쓰는 경로
    (1~5 정수 · 서술 라벨 · 이분 선택)는 드라이런에서 전부 파싱 실패한다.
    실제로 fmtprobe 의 words·binary 형식이 스텁에서 100% 실패했다 —
    실측이었다면 두 형식이 통째로 날아간 뒤에야 알았을 것이다.
    """
    if '"first"' in text and '"second"' in text:
        # origsurvey 의 원설문 순위 문항(1·2순위). 보기 수는 프롬프트의 "n. " 줄에서
        # 센다 — 고정값을 박으면 9지(D6)와 8지(E10/E13)가 한쪽에서 범위를 벗어난다.
        n = max([int(m) for m in re.findall(r"(?m)^\s*(\d+)\.\s", text)] or [8])
        return ("rank2", "1..n", n)
    if '"scale"' in text:
        # origsurvey 의 D2 5점 양극척도. 아래 "1~5" 분기보다 먼저 봐야 한다 —
        # 이 프롬프트에도 "1~5" 가 들어 있어 순서를 바꾸면 stance 로 잘못 간다.
        return ("scale", "1..5", None)
    if '"A":' in text and '"B":' in text:
        # ratingprobe 의 단극 이중평정. 두 선택지를 **각각** 1~5로 매기므로
        # 단일 stance 를 내면 전 칸이 파싱 실패한다. "1~5" 분기보다 먼저 본다 —
        # 이 프롬프트에도 "1~5" 가 들어 있어 순서를 바꾸면 가려진다.
        return ("rating2", "1..5", None)
    if '"choice"' in text:
        if "또는" in text and "중 하나만" in text:
            return ("choice", "binary", None)
        opts = re.findall(r"「([^」]+)」", text)
        return ("choice", "words", opts or None)
    if "1~5" in text:
        return ("stance", "1..5", None)
    return ("stance", "-2..2", None)


def _stub(messages, seed):
    """비용 0 으로 전 경로를 확인하기 위한 결정적 가짜 응답(STUB_LLM=1).

    무작위가 아니라 **메시지 내용 + seed 의 해시**로 정한다. seed 를 빼면 같은 조건의
    반복 표본 N 개가 전부 같은 값이 되어, 분산에 걸리는 분기를 드라이런이 밟지 못한다. 무작위면 같은 명령을 두 번 돌렸을 때
    경로가 갈려서, 드라이런으로 확인한 것이 실제로 돌 것과 같다는 보장이 없다.
    stance 는 -1/0/+1 만 낸다 — 실측에서 ±2 는 4,388건 중 16건(0.36%)뿐이라
    스텁이 ±2 를 흔하게 내면 실제와 다른 분기를 밟는다.
    """
    text = "".join(m["content"] for m in messages)
    h = hashlib.sha256((text + f"|seed={seed}").encode("utf-8")).hexdigest()
    n = int(h[:8], 16)
    field, kind, opts = _stub_shape(text)
    n_ = n
    out = {"public": f"[stub {h[:6]}] 스텁 발언입니다.",
           "confidence": 50 + int(h[8:10], 16) % 50, "reason": f"[stub {h[:6]}]"}
    if field == "rank2":
        # 두 번호를 해시의 **다른 자리**에서 뽑되 겹치면 밀어낸다. 같으면
        # parse() 가 duplicate 로 올리므로 드라이런이 정상 경로를 못 밟는다.
        n = opts
        f = (n_ % n) + 1
        s2 = (int(h[8:16], 16) % n) + 1
        if s2 == f:
            s2 = (s2 % n) + 1
        out["first"], out["second"] = f, s2
    elif field == "scale":
        out["scale"] = (n_ % 5) + 1
    elif field == "rating2":
        # 두 점수를 해시의 **다른 자리**에서 뽑는다. 같은 자리를 쓰면 언제나
        # 동점이 되어 동점률 분기와 pref 부호 분기를 드라이런이 밟지 못한다.
        out["A"] = (n % 5) + 1
        out["B"] = (int(h[8:16], 16) % 5) + 1
    elif kind == "binary":
        out["choice"] = "A" if n % 2 else "B"
    elif kind == "words" and opts:
        out["choice"] = opts[n % len(opts)]
    elif kind == "1..5":
        out["stance"] = (n % 5) + 1
    else:
        out["stance"] = (n % 3) - 1
    return json.dumps(out, ensure_ascii=False)

# temperature 를 받지 않는 계열. 보내면 400 이고, _fatal() 이 즉시 올려 실행이 죽는다.
# 출처: sbs-deliberation-v3 CLAUDE.md — 2026-08-19 실측으로 luna·sol·terra 모두 400.
# 조용히 빼지 않고 목록으로 두는 이유: 어떤 실행이 temperature 없이 돌았는지가
# 재현에 필요한 정보라, usage 와 함께 기록으로 남아야 한다.
NO_TEMPERATURE = ("openai/gpt-5.6-", "gpt-5.6-")

def takes_temperature(model):
    """이 모델에 temperature 를 실어도 되는가. NO_TEMPERATURE 를 **선언만 해 두고
    쓰지 않으면** 목록이 있으나 마나다 — 해당 계열로 실험을 걸면 첫 병렬 배치에서
    전부 400 이 나고 _fatal() 이 즉시 올려 실행이 죽는다."""
    return not any(model.startswith(x) for x in NO_TEMPERATURE)


def options(model):
    """이 모델에 실제로 실릴 요청 옵션. preflight 와 chat 이 **같은 함수**를 본다.
    결과 manifest 에도 이 값을 적어, 어떤 옵션으로 돈 수치인지 나중에 재구성한다."""
    return {"temperature": takes_temperature(model)}


def chat(model, messages, temperature=0.7, seed=None, max_tokens=1024, retries=4,
         response_format=None):
    if STUB:
        return _stub(messages, seed)
    c = client(model)
    last = None
    for a in range(retries):
        try:
            kw = dict(model=_norm(model), messages=messages, max_tokens=max_tokens)
            if takes_temperature(model):
                kw["temperature"] = temperature
            if seed is not None:
                kw["seed"] = seed
            if response_format is not None:
                kw["response_format"] = response_format
            r = c.chat.completions.create(**kw)
            return r.choices[0].message.content
        except Exception as e:
            last = e
            if _fatal(e):
                raise
            time.sleep(2 * (a + 1))
    raise last

if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen/qwen-2.5-72b-instruct"
    print("smoke model:", model)
    print(chat(model, [{"role": "user", "content": "한 문장으로 자기소개 해줘."}],
               max_tokens=120))
