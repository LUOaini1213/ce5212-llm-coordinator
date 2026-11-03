# ce5212-llm-coordinator

NUS CE5212 course extract: **a traffic coordinator that may not emit simulator IDs**. Standard library only, Python 3.11+.

- **Built:** the model (or a rule twin) outputs a semantic intent — direction + seconds + flags — and deterministic code grounds the direction to an example corridor edge. Same apply layer for LLM and rules, so a gap is about the decision process, not a hidden extra actuator.
- **Found (logged course run, recounted in CI):** with the model demoted to a yes/no approver of rule-proposed actions, **137 of the 180 ticks (76%)** had no candidate and never reached the model; the model approved all 43, rejected 0 — all of them `vms` broadcasts, so the log measures the fast-path share, not the gate's judgement.
- **Limits:** the logged run used that later approval-gate variant. Its rule trigger, the Ollama loop and the SUMO network stay in the private course folder; this repo ships the semantic-intent coordinator, the grounding layer, the per-tick log and a reply parser replayed over it. Every number is from course simulation, not production.

## The result you can recount here

With the model demoted to a yes/no approver of rule-proposed actions, the rule layer proposed **43** candidate actions across the 180 coordination ticks of the logged run, and the model approved all 43, rejected 0. **137 of the 180 ticks (76%) had no candidate at all** and never reached the model: three ticks in four are decided by deterministic code, at deterministic latency.

The per-tick log of that run ships with the repo as [`data/course_run_B_s42.jsonl`](data/course_run_B_s42.jsonl) — 180 lines, one JSON object per tick, plain ASCII. The Ollama approval loop that produced it, the rule trigger that proposed its candidates and the SUMO network it ran against stay in the private course folder, so what you can re-derive here is the log's own arithmetic:

```bash
python scripts/recount_approvals.py
```

```text
recount of data/course_run_B_s42.jsonl
coordination ticks          180
candidate actions proposed  43
approved by the model       43
rejected by the model       0
ticks with no candidate     137
no-candidate share          76.1%
ticks that called the model 43
candidates by action type   vms 43
logged replies re-parsed    43 of 43
inconsistent rows           0
```

`python scripts/recount_approvals.py --check` re-derives those counts and diffs them against the numbers written above, and CI runs it on every push — so a number edited in this README without the log behind it turns the build red.

The recount also re-parses all 43 logged replies with [`coordinator/approval.py`](coordinator/approval.py) — a default-deny reply parser written for this repo, not the course loop's own code — and checks that each one gives back the logged verdict and the logged `parsed_keys`, and that a tick reaches the model exactly when it has a candidate ("inconsistent rows" counts the ticks where that fails). The replay shows the logged verdicts follow from the logged replies; it does not re-run the trigger that decided which ticks had a candidate.

The rule layer only ever proposes what it has a trigger for: all 43 candidates in this run are `vms` passenger-information broadcasts at the feeder stop, so 43 of 43 is how often the model agreed with the rule layer on that one action type; this log holds no case of the gate turning an action down, so what it measures is the fast-path share. (An earlier write-up quoted "43 of 44 (97.7%)" with one rejection: 44 is the VMS count of a separate rule-only run, corrected in commit `25221d6`.)

## Why this exists

A 4-bit local model asked to emit TraCI / OSM IDs copied placeholder tokens (`"str"`). Calls became no-ops. The fix is the same boundary as [civil-buddy](https://github.com/LUOaini1213/civil-buddy) (formerly `packing-agent`): **tools / code own identifiers; the model only routes.**

Full SUMO networks, person demand, Ollama loops and the approval gate's rule trigger stay in the private course folder (100MB+ maps). This repo is the semantic-intent coordinator and its grounding layer, the coordination log above with a replayed reply parser, and a two-arm mock you can run without SUMO. The gate's trigger code is not included — only its log is.

## Layout

```text
coordinator/     schema, parse, rule coordinator, grounding, approval-reply parser, policy, personas
scripts/         mock_compare.py — rule ticks and hand-written model-style replies through the same grounding
                 recount_approvals.py — recount and replay the log, check the README against it
                 check_public_tree.py — refuse ID-, phone- and home-path-shaped strings
data/            course_run_B_s42.jsonl — 180-tick coordination log (scenario B, seed 42)
tests/           unittest against shipped functions
```

## Quick start

Python 3.11 or newer, nothing to install. CI runs these on Ubuntu and Windows.

```bash
python -m unittest discover -s tests -v           # 40 tests, standard library, a few seconds
python scripts/mock_compare.py                    # two arms -> output/mock_compare.json, output/mock_model_replies.json
python scripts/recount_approvals.py --check       # recount the log, diff it against this README
python scripts/check_public_tree.py               # no student ID, phone number or home path in the tree
```

`mock_compare.py` runs two arms through the same `ground_intent`:

- **Rule coordinator, three ticks.** Peak tick (t=1350) should pick `east_to_cbd` and ground to example edge `479165267`. Off-peak ticks skip with `no_direction`. Expected output: [`examples/mock_compare.json`](examples/mock_compare.json).
- **Hand-written model-style replies** (not model output) through parse → sanitize → ground: a fenced reply with `"20"` as text and `"false"` as a flag, a reply of `"str"` placeholders, a reply with a stray `</think>` before an unclosed `<think>`, and plain prose. The placeholder reply reaches no edge and dispatches nothing. Expected output: [`examples/mock_model_replies.json`](examples/mock_model_replies.json).

CI diffs both files against the committed examples on every push.

**Input boundary (2026-10-12):** sanitizer and grounding share the same parsers.
Flags accept JSON booleans or explicit `true`/`false` text (case/whitespace
ignored); numbers, collections and other strings default to false. The string
`"false"` cannot trigger dispatch or an alert. Green extensions retain finite
numeric/integer-text coercion and the 0–25 s clamp; booleans, nonfinite numbers
and invalid values give zero extension without an overflow. These are offline
typed-input regressions, not a new model/SUMO evaluation. The existing three-tick
example and course-log numbers remain unchanged; see
[intent-type-checks.json](docs/intent-type-checks.json), a dated snapshot from
2026-10-12 at commit `25221d6` (the suite had 25 tests then; the current count is
the one in Quick start).

**Think-tag parsing (2026-11-03):** `extract_json_text` used to loop forever,
with the text growing on every pass, when a `</think>` came before a `<think>`.
It now removes only `<think>…</think>` pairs in order and leaves a stray or
unclosed tag for the brace extraction to step over; two time-bounded tests cover
both cases.

## Numbers from the private SUMO runs

**Not reproducible from this repo:** the SUMO network, person demand and the Ollama loop stay in the course folder, and no per-rider or per-leg summary is committed, so the runs below are quoted rather than re-runnable here. Each bullet names the demand level it belongs to.

- **Feeder dispatch gate, 4,500-commuter demand** — the rule coordinator with too-low AV triggers flooded the feeder lot: 856 dispatches, 2,232 arrivals against a 3,291-arrival no-coordination baseline. After raising the triggers and adding a cooldown: 74 dispatches, 3,066 arrivals. All three runs are seed 42 at the 4,500-commuter demand level — a larger demand than the 645-commuter run the coordination log above comes from.
- **Synchronous approval calls cost arrivals, 645-commuter demand** — blocking the TraCI loop on the model left 57 more commuters short of their destination at the cut-off than the rule-only twin at the same seed (92 aborted vs 35). Across all **394 bus riders** — the same people in both runs — door to door averaged **2.2 min** more (47.3 vs 45.1 min), and nearly all of that sits on the **Bus 95 line-haul leg** (17.3 vs 15.1 min); the other four legs together net out to under 0.1 min. Counting only the 315 riders who arrived in *both* runs gives +0.9 min instead, because that filter drops the riders the delay pushed past the cut-off. That is why approval belongs off the critical path (lower tick rate, or async pub-sub).

The corridor is 1.4 km² of SUMO network calibrated on 2,874 measured speeds. The coordination log is the 645-commuter run (scenario B, seed 42; 35% time-sensitive / 40% price-sensitive / 25% information-asymmetric personas). Course project, spring 2026.

## Scope

This is **not** end-to-end autonomous driving, **not** VLA, **not** a world model, **not** a vehicle-side planner. No BEV, no nuScenes, no CARLA. The feeder result is a control-gate outcome on one corridor, not a PDMS / Bench2Drive score, and every number here comes from course simulation, not production.

Related public work: [ce5203-aye-weaving](https://github.com/LUOaini1213/ce5203-aye-weaving) (YOLO counts + SUMO ramp metering).
