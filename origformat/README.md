# Original-format replication (Appendix C — Tables 17–19)

The main pipeline surveys personas with a two-way forced choice. This module
re-runs the eight questions in the *source surveys' own formats* — the original
option lists, response rules, and two option-order arms — and scores personas
against the published human distributions question by question. It is
self-contained: its own client, items, recode rules, and tables.

```
code/origsurvey.py    collect responses (original instrument, arms F=original / R=reversed)
code/origitems.py     items, option lists, recode rules; verifies itself on import
code/origtables.py    render the appendix tables from results + human benchmarks
code/client.py        API client (stub mode: STUB_LLM=1 calls nothing, writes to results/_stub/)
code/deliberation.py  persona system prompt (shared wording with the survey code)
code/results/         the shipped runs behind the paper's tables (condition hashes 248adc env / f8d537 birth)
csv/                  the rendered tables as released (J1 instruments, J2 by group, J3 within cell)
human_benchmark.json  precomputed human aggregates (overall and by group)
tables.json           the same tables in machine-readable form
microdata/fetch_kei.py  downloads the KEI 2025 microdata (DOI 10.23160/keidata.31); not redistributed
```

## Verify without API calls

`origitems.py` re-checks its recode targets on every import — option counts
against the source-survey JSON, pole option numbers, and that the recoded
aggregates reproduce the published benchmark values — and aborts on any
mismatch:

```
cd code && python3 -c "import origitems"
```

## Re-collect responses

```
cd code
STUB_LLM=1 python3 origsurvey.py --qs env1 --persona 8      # wiring check, zero cost
python3 origsurvey.py --qs env1,env2,env3,env4     --persona 640 --workers 48
python3 origsurvey.py --qs birth1,birth2,birth3,birth4 --persona 640 --workers 48
```

5,120 calls per line at temperature 0. Output filenames carry a condition hash
(provider, model, options, personas, seed, questions), so a run under different
conditions cannot overwrite the shipped results.

## Render the tables

```
cd code && python3 -c "
import origtables as T
h  = T.humans_env()
pe = T.personas('results/origsurvey_openai__gpt-4.1-mini_248adc.json','F')
pb = T.personas('results/origsurvey_openai__gpt-4.1-mini_f8d537.json','F')
T.render(T.env_rows(pe,h), T.ENVQ, '(a) Environmental policy')
T.render(T.bir_rows(pb),   T.BIRQ, '(b) Low-birthrate policy')
"
```

The environmental panel's human columns are recomputed from the KEI microdata:
run `microdata/fetch_kei.py` first (`pip install pyreadstat`; no login or
application step). Without the microdata, the shipped `human_benchmark.json`
holds the same aggregates, and `csv/` and `tables.json` are the rendered
output. The low-birthrate panel needs no microdata; its benchmarks are the
published renormalized shares encoded in `origitems.HUMAN`.
