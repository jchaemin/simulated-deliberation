import json
import os
import random

from experiments._common import read_jsonl

CELLS = {"natural": ("chosen", "none"), "opening_matched": ("matched", "opening"),
         "cue_chosen": ("chosen", "cue"), "cue_matched": ("matched", "cue")}
grid = read_jsonl("results/anchoring_grid/sol.jsonl")
os.makedirs("results/frozen_rooms", exist_ok=True)
for name, (pool, conn) in CELLS.items():
    rooms = random.Random(0).sample([r for r in grid if (r["pool"], r["conn"]) == (pool, conn)], 10)
    with open(f"results/frozen_rooms/{name}.jsonl", "w", encoding="utf-8") as f:
        for r in rooms:
            f.write(json.dumps({k: r[k] for k in ("issue", "seed", "ids", "included", "transcript")}, ensure_ascii=False) + "\n")
