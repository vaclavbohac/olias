# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Olias is a bike trainer app that simulates a real bike ride to Olias (Málaga) using the author's recorded ride telemetry. Planned functionality (per README):

- Connects to a Wahoo Kickr trainer via Bluetooth
- Connects to a heart rate monitor via Bluetooth
- Controls trainer resistance based on the rider's current position along the route
- Replays telemetry from real rides to simulate the same ride

Domain vocabulary lives in `CONTEXT.md` (use its terms — Route Profile, Remaining Ascent, Climb Delta, Rider Model, etc.); architectural decisions and their rationale live in `docs/adr/`. Read both before designing anything.

## Environment and commands

- Python 3.11 (pinned in `.python-version`); uv-managed, hatchling-built package.
- Tests: `uv run pytest` (single test: `uv run pytest tests/test_engine.py -k pause`)
- Lint & format (both enforced by CI): `uv run ruff check --fix .` and `uv run ruff format .`
- Ride: `uv run olias ride` (first time: `uv run olias devices` to scan & store BLE devices)
- Recalibrate Crr after new reference rides: `uv run tools/calibrate.py`, copy the value into `olias/config.py` — the replay-validation tests are the guardrail
- Rebuild the route CSV: `uv run --with fitdecode tools/build_route.py`

## Architecture

Pure core (no I/O, fully tested): `profile` (Route Profile + Remaining Ascent), `physics` (Rider Model), `reference` (FIT recordings indexed by riding time/position), `replay` (Replay Validation — read its docstring before touching it; every rule answers a real failure), `engine` (tick state machine: ARMED/RIDING/PAUSED/FINISHED, Climb Delta, trainer grade dedup). Shell: `session` (asyncio runner), `ble/` (FTMS trainer + HR adapters, reconnect-forever, disconnect = 0 W), `recording` (FIT writer; output reads back via `ReferenceRide`), `tui` (Textual), `cli`. Constants and the calibrated model live in `olias/config.py`.

## Ride data (`resources/`)

Four FIT activity files of the same ~36 km Olias loop (start/end at 36.699, -4.437 in Málaga, ~500-550 m ascent, max altitude ~520 m), all recorded on the same Wahoo ELEMNT BOLT. `fitdecode` parses them cleanly.

| File | Date | Duration | Notes |
|---|---|---|---|
| olias-ride-001.fit | 2025-01-25 | 2:24:46 | Reference ride: correct altitude, fullest field coverage |
| olias-ride-002.fit | 2025-05-23 | 1:44:53 | Fastest effort (NP 206 W); baro drifts ~22 m over the ride |
| olias-ride-003.fit | 2023-01-02 | 2:27:41 | Starts in a -3 garage floor, so early altitude/min altitude read ~7-15 m below street level |
| olias-ride-004.fit | 2024-05-22 | 2:16:17 | — |

Facts that matter when parsing:

- `record` messages are 1 Hz and include position, altitude, grade, distance, power, heart_rate, cadence, speed, temperature. Use recorded `grade` (indexed by `distance`) to drive trainer resistance — no need to derive it from GPS/altitude.
- Altitude in 002 and 004 was recorded with a miscalibrated barometer (~150-230 m too low) and has been rewritten in-place with constant offsets (+143.0 m, +228.6 m) to align with ride 001. Use 001 as the canonical route profile; treat all four as performance recordings over it.
- Expect nulls: altitude/grade are missing for the first ~60-390 m of a ride (baro warm-up), the first record lacks GPS, and 002 has mid-ride power/cadence gaps. Per-second grade also has spikes (e.g. -22% in 002) — smooth or clamp before sending to the trainer.
- `distance` drifts between recordings (total distance differs by up to ~1.5 km for the same route), so distance-indexed comparisons across rides are only approximate.
- Each file also carries `session`/`lap` summaries (NP, TSS, IF, HR/power zone times) usable without processing records.

## Canonical route profile (`resources/olias-route.csv`)

The clean distance-indexed profile the simulator should drive resistance from — use it instead of raw FIT grade. Columns: `distance_m` (uniform 5 m grid), `lat`, `lon`, `altitude_m`, `grade_pct`. 7,252 points, 36.26 km, 583 m ascent, grade -10.0..+11.0%.

Regenerate with `uv run --with fitdecode tools/build_route.py`: it resamples ride 001, smooths altitude with a 55 m moving average, and derives grade from the smoothed altitude over 30 m spans (clamped to ±18%) — so the raw recordings' grade spikes cannot reach the trainer by construction.
