"""KEI 2025 국민환경의식조사 응답자 단위 원자료(n=3,008) 수신.

## 왜 스크립트로 남기는가
자료 자체는 커밋하지 않는다(개인 단위 + 재배포 권리 없음). 그러면 재현자가
같은 자료를 못 구하므로, **받는 절차**를 코드로 남겨 그 자리를 메운다.

## 출처
https://data.kei.re.kr/data/5011736e-0399-495a-bf77-a2a2e6bdf413
DOI 10.23160/keidata.31 · 한국환경연구원 · 조사기간 2025-09-24~10-15
로그인·신청·약관동의 없이 공개 배포된다(2026-08-27 확인).

## 왜 3단계인가
포털이 정적 파일 링크를 주지 않고 페이지의 자바스크립트가
  ready(세션) -> generate(POST: itemId/fileId/fingerprint -> sig,expires)
  -> file(GET: 위 파라미터)
순으로 서명 URL을 만든다. 아래는 그 절차를 그대로 따른 것이다.
fingerprint 는 브라우저가 UA|언어|화면|타임존을 이어붙여 만드는 값이고,
generate 와 file 두 요청에서 같기만 하면 된다.
"""
import json, os, sys, urllib.parse, urllib.request, http.cookiejar

BASE = "https://data.kei.re.kr"
ITEM = "5011736e-0399-495a-bf77-a2a2e6bdf413"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
FP = f"{UA}|ko-KR|1920x1080|Asia/Seoul"
FILES = {
    "befcd2da-9e60-4106-a40b-1f1dedf83a44": "kei2025_raw.sav",
    "a67b4b53-7a9f-469d-8182-196458ad9458": "kei2025_codebook.xlsx",
    "cc1dc427-2e19-493f-bb89-f5db1cb12394": "kei2025_raw.xlsx",
}
HERE = os.path.dirname(os.path.abspath(__file__))

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", UA), ("Referer", f"{BASE}/data/{ITEM}")]

op.open(f"{BASE}/kei/download/ready", timeout=60).read()
for fid, name in FILES.items():
    body = json.dumps({"itemId": ITEM, "fileId": fid, "fingerprint": FP}).encode()
    req = urllib.request.Request(f"{BASE}/kei/download/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    tok = json.loads(op.open(req, timeout=60).read())
    q = urllib.parse.urlencode({"itemId": tok["itemId"], "expires": tok["expires"],
                                "sig": tok["sig"], "fingerprint": FP,
                                "fileId": tok["fileId"]})
    blob = op.open(f"{BASE}/kei/download/file?{q}", timeout=300).read()
    out = os.path.join(HERE, name)
    with open(out, "wb") as f:
        f.write(blob)
    print(f"{name:28} {len(blob):>10,} bytes")
