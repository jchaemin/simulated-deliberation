# From Simulated Citizens to Simulated Deliberation

## Layout

```
simdelib/          the library
  llm.py             chat client (OpenRouter; reasoning off for agents, minimal for the two reasoning judges)
  questions.py       the eight Korean questions, their survey benchmarks by group, and the five U.S. items
  personas.py        persona pools and persona prompts
  prompts.py         survey and speaking-turn prompts
  survey.py          survey calls, option order, answer parsing
  deliberation.py    debate, sealed monologue, anchoring conditions, room construction, population-matched sides
  judging.py         Discourse Quality Index and argument-repertoire judges
  shinkori.py        Shin-Kori panel, booklet, poll-specific prompts
  questionnaire.py   the original survey items and their recode (Appendix B)
  kei.py             KEI microdata loader and downloader
  stats.py           shared analysis helpers
experiments/       one script per experiment; each writes results/
analysis/          one script per part of the paper; prints the numbers and writes tables/ and results/derived/
data/              persona pools, Shin-Kori panel, original survey items
results/           all outputs (one folder per experiment)
tables/            LaTeX table rows written by the analysis scripts
```

## Rerun the experiments

Put an OpenRouter key in `.env` (`cp .env.example .env`) or in the environment variable `OPENROUTER_API_KEY`.
Run every command from the repository root. Model tags: `sol` openai/gpt-6-sol, `luna` openai/gpt-6-luna,
`mini` openai/gpt-4.1-mini, `deepseek` deepseek/deepseek-v4.1-flash, `haiku` anthropic/claude-haiku-5.5,
`qwen` qwen/qwen3.8-flash. Judges: `opus` anthropic/claude-opus-5.5, `gemini` google/gemini-3.1-pro-preview, `sol`.

Run order: the persona survey first (rooms are built from it), then debates, then the controls and judges. The
attribution test reads its statements and each model's booklet-stage answers from `results/shinkori/attribution_inputs.json`.

## Data

- **Personas.** `data/persona_pool.jsonl` (640 Korean personas, four per sex x age x education x region cell) and
  `data/persona_pool_usa.jsonl` (the 256 U.S. personas, drawn at random with seed 1 from a pool of 512 with four per
  sex x age x education x region cell, in the order drawn) are subsets of NVIDIA Nemotron-Personas (Korea and USA
  splits, CC BY 4.0), with the fields the prompts and the group benchmarks use.
- **Benchmarks.** Group-level shares of the KEI 2025 and PCASPP surveys and the Pew items are in `simdelib/questions.py`.
  Pew sources: us1, short read of 2025-05-19 (American Trends Panel 2023-24); us2, ATP wave 128 topline, item EN1
  (May-June 2023); us3, "Americans' Views of Government's Role" (2024-06-24); us4, abortion fact sheet (2026 update);
  us5, energy-strategy item.
- **Original survey items** (Appendix B): `data/original_items_kr.json`, the source items with their option lists and
  published option shares. The prompts (`simdelib/questionnaire.py`) use the option lists verbatim; the four
  environmental question stems are reworded for the prompt (the three ranked-choice items ask for a first and a second
  choice).
- **KEI microdata** (Appendix B human recode, Appendix C reweighting): publicly distributed by the Korea Environment
  Institute (DOI 10.23160/keidata.31) but not redistributed here; `python3 -m simdelib.kei` downloads it to
  `data/kei_microdata/`. `results/derived/original_questionnaire.json` and `results/derived/reweighting.json` are the
  outputs of the two analyses that use it.
- **Shin-Kori.** `data/shinkori_panel_498.json` holds, for each of the 498 agents, only the variables used in the prompt
  (age, sex, province, occupation, party), the age band used for the group comparisons, the wave-1 answer, and the
  agent's option order, with no record identifiers. They were drawn from the committee's first-wave survey (20,006
  respondents): the 5,881 respondents the released file marks as volunteers (the committee reports 5,981), sampled by survey weight to the panel's opinion x sex x age cells, shuffled with
  seed 0, first 498 kept. The raw survey file is not redistributed. The booklet summaries in `simdelib/shinkori.py` were
  written for this study, one per side, at the same length. The panel's three-way shares (waves 1, 3, 4) are from the
  committee's report.
