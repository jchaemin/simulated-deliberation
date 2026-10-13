import http.cookiejar
import json
import os
import urllib.parse
import urllib.request

from . import questionnaire as OQ

SAV = "data/kei_microdata/kei2025_raw.sav"
EDUCATION = {1: "≤중졸", 2: "고졸", 3: "대졸", 4: "대학원"}
REGION = {1: "수도권", 2: "수도권", 3: "충청", 4: "호남", 5: "영남", 6: "영남", 7: "강원·제주"}


def age_band(age):
    return "20s" if age < 30 else "30-44" if age < 45 else "45-59" if age < 60 else "60+"


def respondents():
    import pyreadstat
    cols = ["SQ3", "DM1", "DM3", "DM4", "D2", "D6", "D6_m2", "E10", "E10_m2", "E13", "E13_m2"]
    df, _ = pyreadstat.read_sav(SAV, usecols=cols)
    out = []
    for _, r in df.iterrows():
        rec = {"sex": "남자" if r["DM1"] == 1 else "여자", "age_band": age_band(r["SQ3"]), "edu4": EDUCATION[int(r["DM4"])],
               "region_group": REGION[int(r["DM3"])], "region7": int(r["DM3"]),
               "env1": "A" if r["D2"] <= 2 else ("B" if r["D2"] >= 4 else "mid")}
        for q in ("env2", "env3", "env4"):
            orig = OQ.SPEC[q]["orig"]
            picks = (r[orig], r[orig + "_m2"])
            rec[q + "_picks"] = picks
            rec[q] = OQ.recode(q, {"first": picks[0], "second": picks[1]})
        out.append(rec)
    return out


def download(folder="data/kei_microdata"):
    base, item = "https://data.kei.re.kr", "5011736e-0399-495a-bf77-a2a2e6bdf413"
    ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    fingerprint = f"{ua}|ko-KR|1920x1080|Asia/Seoul"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.addheaders = [("User-Agent", ua), ("Referer", f"{base}/data/{item}")]
    opener.open(f"{base}/kei/download/ready", timeout=60).read()
    os.makedirs(folder, exist_ok=True)
    for file_id, name in {"befcd2da-9e60-4106-a40b-1f1dedf83a44": "kei2025_raw.sav"}.items():
        body = json.dumps({"itemId": item, "fileId": file_id, "fingerprint": fingerprint}).encode()
        token = json.loads(opener.open(urllib.request.Request(f"{base}/kei/download/generate", data=body,
                                                              headers={"Content-Type": "application/json"}), timeout=60).read())
        query = urllib.parse.urlencode({"itemId": token["itemId"], "expires": token["expires"], "sig": token["sig"],
                                        "fingerprint": fingerprint, "fileId": token["fileId"]})
        blob = opener.open(f"{base}/kei/download/file?{query}", timeout=300).read()
        open(os.path.join(folder, name), "wb").write(blob)
        print(f"{name}: {len(blob):,} bytes")


if __name__ == "__main__":
    download()
