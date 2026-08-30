# Eight two-pole sub-agendas from the two source surveys (KEI 2025; PCASPP 2025), with published group-level benchmarks.
# env* : KEI 2025 국민환경의식조사 (n=3,008) — benchmarks by sex/age_band/edu4/region_group
# birth*: 저고위 제5차 인식조사 2026-03 (n=2,800) — benchmarks by sex/age(20/30/40대)/marital

QUESTIONS_KR = {
 "env1": {"id":"env1","topic":"환경정책 우선순위",
   "poleA":"환경보전 우선 (경제성장이 다소 둔화되더라도)",
   "poleB":"경제성장 우선 (환경이 다소 훼손되더라도)"},
 "env2": {"id":"env2","topic":"환경문제 해결수단",
   "poleA":"처벌·법집행 강화","poleB":"국민·기업의 자발적 노력 우선"},
 "env3": {"id":"env3","topic":"기후위기 대응전략 (한정된 자원의 우선 투입)",
   "poleA":"기후적응 우선 (홍수·폭염 대비 인프라)","poleB":"에너지전환 우선 (재생에너지 확대)"},
 "env4": {"id":"env4","topic":"기후테크 육성 우선순위",
   "poleA":"재생에너지 기술 (태양광·풍력)","poleB":"순환경제 기술 (재활용·폐기물 관리)"},
 "birth1": {"id":"birth1","topic":"일·가정 양립 정책 우선순위",
   "poleA":"육아기 유연근무 사용 활성화","poleB":"육아휴직 급여 상한액 추가 인상"},
 "birth2": {"id":"birth2","topic":"교육·돌봄 정책 우선순위",
   "poleA":"아이돌봄서비스 정부지원(대상·시간) 확대","poleB":"사교육비 경감을 위한 교육과정·내용 개선"},
 "birth3": {"id":"birth3","topic":"결혼·출산 경제지원 방식",
   "poleA":"결혼·출산 가구 세금혜택 확대","poleB":"부모급여·아동수당 등 현금지원 확대"},
 "birth4": {"id":"birth4","topic":"저출생 주거지원 방향",
   "poleA":"주택구입·전세자금 소득기준 완화","poleB":"신혼·출산가구 청약특례 확대"},
}

# Human A-share among directional respondents (A/(A+B)), overall and by group.
BENCH = {
 "env1": {"overall":68.2,
   "sex":{"남자":57.0,"여자":79.8},
   "age_band":{"20s":50.8,"30-44":58.4,"45-59":74.9,"60+":81.2},
   "edu4":{"≤중졸":87.0,"고졸":72.9,"대졸":65.0,"대학원":68.1},
   "region_group":{"수도권":68.8,"영남":64.3,"호남":73.2,"충청":69.6,"강원·제주":68.9},
   "dist5":{"A":42.2,"mid":38.2,"B":19.6}},   # D2 full-distribution anchor
 "env2": {"overall":53.9,
   "sex":{"남자":53.6,"여자":54.3},
   "age_band":{"20s":49.1,"30-44":56.7,"45-59":54.6,"60+":53.1},
   "edu4":{"≤중졸":57.1,"고졸":52.5,"대졸":54.6,"대학원":54.6},
   "region_group":{"수도권":52.6,"영남":52.2,"호남":60.4,"충청":56.8,"강원·제주":57.1}},
 "env3": {"overall":70.4,
   "sex":{"남자":66.6,"여자":73.9},
   "age_band":{"20s":73.6,"30-44":70.9,"45-59":69.3,"60+":69.2},
   "edu4":{"≤중졸":50.0,"고졸":70.1,"대졸":71.4,"대학원":67.6},
   "region_group":{"수도권":70.0,"영남":71.3,"호남":69.1,"충청":72.7,"강원·제주":65.4}},
 "env4": {"overall":50.6,
   "sex":{"남자":53.3,"여자":48.2},
   "age_band":{"20s":46.5,"30-44":53.4,"45-59":50.4,"60+":50.6},
   "edu4":{"≤중졸":63.6,"고졸":47.9,"대졸":52.2,"대학원":50.0},
   "region_group":{"수도권":48.7,"영남":51.4,"호남":55.9,"충청":52.9,"강원·제주":53.3}},
 "birth1": {"overall":60.8,"sex":{"남자":53.4,"여자":68.7},
   "age_surv":{"20대":61.5,"30대":59.8,"40대":61.5},
   "marital":{"미혼":61.6,"기혼":60.0}},
 "birth2": {"overall":58.4,"sex":{"남자":57.8,"여자":59.1},
   "age_surv":{"20대":60.6,"30대":61.9,"40대":54.8},
   "marital":{"미혼":62.1,"기혼":54.9}},
 "birth3": {"overall":56.4,"sex":{"남자":56.9,"여자":55.9},
   "age_surv":{"20대":61.7,"30대":58.0,"40대":53.0},
   "marital":{"미혼":61.4,"기혼":52.6}},
 "birth4": {"overall":53.3,"sex":{"남자":50.0,"여자":56.8},
   "age_surv":{"20대":45.7,"30대":52.5,"40대":57.2},
   "marital":{"미혼":49.4,"기혼":57.4}},
}
# Notes (from the docs): env benchmarks are directional-only (neutrals excluded);
# birth benchmarks are relative-priority (1+2순위 renormalized), not forced-choice;
# 저출생 survey age: 20대=25-29 (our 20s includes 19-24 — compare loosely);
# ≤중졸 cells have tiny n (e.g., env2 n=14) — do not treat as strong anchors.
