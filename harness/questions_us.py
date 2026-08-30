# US battery mirroring questions_kr. Benchmarks are published Pew Research
# aggregates; A-share = A/(A+B), directional responses only.
#
# us1: Pew short read, 2025-05-19 (2023-24 ATP, N=36,908): worth cost 60 / cost jobs 38
#      https://www.pewresearch.org/short-reads/2025/05/19/support-for-stricter-environmental-regulations-outweighs-opposition-in-a-majority-of-states/
#      (no published sex/age/education splits; party only)
# us2: Pew ATP Wave 128 topline (May 30-Jun 4 2023, N=10,329), item EN1: 67 / 32
#      (no published demographic splits)
# us3: Pew, 2024-06-24, "Americans' Views of Government's Role": bigger 48 / smaller 49
#      (no published sex/age/education splits; party only)
# us4: Pew abortion fact sheet (2026 update): legal 60 / illegal 38, full demographic splits
QUESTIONS_US = {
 "us1": {"id":"us1","topic":"Environmental regulation priority",
   "poleA":"Stricter environmental laws and regulations are worth the cost",
   "poleB":"Stricter environmental laws cost too many jobs and hurt the economy"},
 "us2": {"id":"us2","topic":"America's energy priority",
   "poleA":"Developing alternative sources, such as wind, solar and hydrogen technology",
   "poleB":"Expanding exploration and production of oil, coal and natural gas"},
 "us3": {"id":"us3","topic":"Size and role of government",
   "poleA":"Bigger government providing more services",
   "poleB":"Smaller government providing fewer services"},
 "us5": {"id":"us5","topic":"The country's energy strategy",
   "poleA":"Phase out the use of oil, coal and natural gas completely, relying instead on renewable energy sources such as wind and solar power only",
   "poleB":"Use a mix of energy sources including oil, coal and natural gas along with renewable energy sources"},
 "us4": {"id":"us4","topic":"Abortion policy",
   "poleA":"Abortion should be legal in all or most cases",
   "poleB":"Abortion should be illegal in all or most cases"},
}
def _ashare(a,b): return round(100*a/(a+b),1)
BENCH_US = {
 "us1": {"overall":_ashare(60,38),"overall_w128":_ashare(53,45)}, # 61.2 / 54.1 (wave bracket)
 "us2": {"overall":_ashare(67,32)},                       # 67.7
 "us3": {"overall":_ashare(48,49)},                       # 49.5 — a true split item
 "us5": {"overall":_ashare(31,68)},                       # 31.3 — MAJORITY ON B (herd-direction probe)
 "us4": {"overall":_ashare(60,38),                        # 61.2
   "sex":{"Male":_ashare(55,44),"Female":_ashare(64,34)},           # 55.6 / 65.3
   "age_surv":{"18-29":_ashare(66,34),"30-49":_ashare(61,38),       # survey bands
               "50-64":_ashare(57,40),"65+":_ashare(57,41)},
   "edu_surv":{"HS-or-less":_ashare(54,44),"some-college":_ashare(61,38),
               "college-grad+":_ashare(65,33)}},
}
# Group-level comparison only where verified (us4). us1-us3: overall-only.
def age_surv(a): return "18-29" if a<30 else "30-49" if a<50 else "50-64" if a<65 else "65+"
def edu_surv(e): return {"HS-or-less":"HS-or-less","some-college":"some-college",
                         "bachelors":"college-grad+","graduate":"college-grad+"}[e]
