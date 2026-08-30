# From Simulated Citizens to Simulated Deliberation


```
run_survey.py         persona surveys (Section 4)
run_deliberation.py   debates and their controls (Section 5)
run_judge.py          LLM-judge scoring: Discourse Quality Index, argument repertoire
analyze.py            recompute paper exhibits from data/ and runs/  (no API)
harness/              API client, persona and question definitions, shared engine (core.py)
data/                 persona pools and per-persona survey responses
runs/                 per-room debate records, judge scores, and run summaries
origformat/           original-format replication (Appendix C), self-contained; see its README
```

## Setup

```
pip install openai
export OPENROUTER_API_KEY=...   # or OPENAI_API_KEY; needed only to re-run experiments
```

All experiments are API calls to hosted models. Model
identifiers as used in the paper: `openai/gpt-4.1-mini` (main),
`openai/gpt-4.1` (judge), `openai/gpt-5.5`, `meta-llama/llama-3.3-70b-instruct`,
`qwen/qwen-2.5-72b-instruct` (robustness).

## Reproducing the paper

Verify any exhibit from the released artifacts (no API):

```
python3 analyze.py table2 table3 table6 table7 fig2 table16 table20 table21 table23 table24 table25
```

Re-run an experiment:

| Paper item | Command |
|---|---|
| Table 2; Tables 8–15 (by-group survey) | `run_survey.py --instrument natural --persona full` |
| Table 3 columns | `run_survey.py --persona full` / `--persona demographics` / `--persona citizen` / `--persona none` |
| Table 5 (DQI by round) | `run_judge.py --input runs/debate_natural.jsonl` |
| Table 6 (debate vs. monologue) | `run_deliberation.py --sides survey --cue none --interaction debate` and `--interaction monologue` |
| Table 7 (six protocols) | `run_deliberation.py --sides {survey,population} --cue {none,side,opening}` |
| Figure 2 (compositions) | `run_deliberation.py --composition 6-0` and `--composition 0-6` (balanced from Table 6) |
| Table 16 (instruments) | `run_survey.py --instrument natural` / `bipolar` / `labeled --order AB` + `--order BA` / `two-ratings`, all at temperature 0; sign-bias factorial: `run_factorial.py`; recompute with `analyze.py table16` |
| Tables 17–19 (original-format replication) | `origformat/` — own runner, shipped results, and README |
| Table 20 (cross-model) | `run_survey.py --model {mini,gpt55,llama33,qwen72}` (`gpt55` with `--subsample 120`) |
| Table 21 (US pool) | `run_survey.py --pool us` (English natural forced choice, temperature 0) -> `data/survey_us.jsonl`; benchmarks in `harness/questions_us.py` |
| Table 22 (live vs. frozen quality) | `run_judge.py --input <run file>` on the four Table 7 cells |
| Table 23 (levers) | `run_deliberation.py --panels random --questions env4,birth2,birth4` + `--disclosure demographics` / `--turns simultaneous` / `--size 4|8` / `--opener A|B`; recompute with `analyze.py table23` |
| Table 24 (injection) | `run_deliberation.py --sides population --cue opening` |
| Table 25 (decomposition) | stored survey views of the injection run + `run_probe.py` (peers-hidden probe) + the `population_label` arm of `runs/debate_protocols.jsonl`; recompute with `analyze.py table25` |
| Noise floor (Appendix E) | `run_survey.py --resurvey 2` |

The artifacts in `data/` and `runs/` are the exact runs. We record the
private stance sequence over rounds 0–3 under the own-turns-included survey
(`included`) and the own-turns-excluded probe (`excluded`); a room's final
composition is the count of agents with side A at the last index.

## Data provenance and licenses

- **Personas**: subsets of NVIDIA Nemotron-Personas (Korea and USA splits),
  used and redistributed under the dataset's published license, with
  attribution to the original release. Personas are synthetic; no real
  individuals are represented.
- **Survey benchmarks**: published aggregate statistics from the 2025 KEI
  National Environmental Awareness Survey, the 5th Public Awareness Survey
  of the Presidential Committee on Aging Society and Population Policy, and
  Pew Research Center topline files, encoded in
  `harness/questions_kr.py` and `harness/questions_us.py`. No respondent
  microdata is included; the KEI microdata used in Appendix C is available
  from the survey's data archive (DOI 10.23160/keidata.31) under its own
  terms.
- **Code**: released under the MIT license.

## Notes

- The main survey and all in-debate stance surveys run at temperature 0;
  speech turns run at temperature 1.0. Option order is randomized per
  persona and held fixed across rounds (verbatim prompts in the paper's
  Appendix H and in `harness/core.py`).
- Survey-chosen (natural) rooms exist only where the survey pools allow
  them: work-family has one survey-B persona of 640 and supports no
  balanced room, and environmental means has four survey-A personas and
  supports one, which the paper excludes; the released survey-side run
  files contain the six remaining questions. Population-matched runs cover
  all eight.
