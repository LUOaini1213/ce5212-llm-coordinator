# data/

## `course_run_B_s42.jsonl`

The per-tick coordination log of one CE5212 course simulation: scenario B, seed 42,
645-commuter demand, prompt version `z-hybrid`. 180 lines, one JSON object per
coordination tick, plain ASCII, copied out of the course run output unchanged
apart from LF line endings.

| field | meaning |
| --- | --- |
| `sim_time` | simulation clock of the tick, seconds |
| `n_candidates` | actions the rule layer proposed on this tick |
| `candidates` | each proposal: `key` (action type) and a human-readable `summary` |
| `approvals` | verdict per candidate key, e.g. `{"vms": true}`; `{}` when nothing was proposed |
| `llm_called` | whether the tick reached the model at all |
| `raw` | the model reply verbatim, present only on ticks that called it |
| `parsed_keys` | keys recovered from `raw` after parsing |
| `diag` | rule-layer state that decided whether to propose: worst occupancy, waiting AVs, spoke load, MRT ETA |

`python scripts/recount_approvals.py` counts the file and replays every logged
`raw` reply through `coordinator/approval.py` (a reply parser written for this
repo, not the course loop's own code), checking that it gives back the logged
`approvals` and `parsed_keys`; `--check` also diffs the result against the
numbers written in the top-level README.

The SUMO network, person demand and the Ollama loop that produced this log stay
in the private course folder, so the run itself is not reproducible from here —
the log is committed so its counts are.
