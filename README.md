# ce5212-llm-coordinator

NUS CE5212 course extract: **a traffic coordinator that may not emit simulator IDs**.

The model (or a rule twin) outputs a semantic intent — direction + seconds + flags. Deterministic code grounds the direction to an example corridor edge. Same apply layer for LLM and rules, so a gap is about the decision process, not a hidden extra actuator.

This is **not** end-to-end autonomous driving, **not** VLA, **not** a world model, **not** a vehicle-side planner. No BEV, no nuScenes, no CARLA.

## Why this exists

A 4-bit local model asked to emit TraCI / OSM IDs copied placeholder tokens (`"str"`). Calls became no-ops. The fix is the same boundary as [civil-buddy](https://github.com/LUOaini1213/civil-buddy) (formerly `packing-agent`): **tools / code own identifiers; the model only routes.**

Full SUMO networks, person demand, and Ollama loops stay in the private course folder (100MB+ maps). This repo is the decision + grounding core plus a mock compare you can run without SUMO.

## Layout

```text
coordinator/     schema, parse, rule coordinator, grounding, policy, personas
scripts/         mock_compare.py — three deterministic ticks, no GPU
tests/           unittest against shipped functions
```

## Quick start

```bash
python -m unittest tests.test_coordinator -v
python scripts/mock_compare.py
```

Peak tick (t=1350) should pick `east_to_cbd` and ground to example edge `479165267`. Off-peak ticks skip with `no_direction`.

## Honest results (from the private SUMO runs)

Rule coordinator with too-low AV triggers flooded the feeder lot (856 dispatches, arrivals 2232 vs baseline 3291). After raising triggers and adding a cooldown: 74 dispatches, arrivals 3066. That is a **control-gate** result on a corridor, not a PDMS / Bench2Drive score.

## Course-log numbers quoted elsewhere

Two numbers from the private course runs are quoted on my CV and site. They are **not** reproducible from this repo (the SUMO network, person demand and Ollama loop stay in the course folder), so here is exactly what they mean:

- **43 / 44 (97.7%)** — with the model demoted to a yes/no approver of rule-proposed actions, it approved 43 of 44 candidate actions correctly in the course simulation log; the single rejection was a defensible time-slack call. Not a production KPI.
- **Bus 95 +2.2 min** — synchronous model calls blocked the TraCI event loop; average end-to-end delay on Bus 95 rose by 2.2 minutes and 57 passengers did not arrive before the simulation cut-off. That is why approval belongs off the critical path (lower tick rate, or async pub-sub).

The corridor is 1.4 km² of SUMO network calibrated on 2,874 measured speeds, with 645 simulated commuters (35% time-sensitive / 40% price-sensitive / 25% information-asymmetric). Course project, spring 2026.

Related public work: [ce5203-aye-weaving](https://github.com/LUOaini1213/ce5203-aye-weaving) (YOLO counts + SUMO ramp metering).
