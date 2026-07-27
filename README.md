# Olias

A bike trainer app that simulates my real ride from Málaga to Olías on a Wahoo
Kickr, using telemetry from my own recorded rides.

The terminal is the head unit: a big **Remaining Ascent** readout counts down
the climbing left, a **Climb Delta** races you against your recorded self up
the climb, and the route's elevation silhouette fills in as you ride. Every
session is written as a FIT activity with the route's real GPS trace, so it
uploads to Strava as a ride up the actual Olías road.

## How it works

- The Kickr runs in simulation mode (standard FTMS over Bluetooth): the app
  sends it the road grade for feel, and reads back your power and cadence.
- Your position along the route is computed by the app's own physics — power
  in, speed out — calibrated against my real recordings so the climb takes as
  long as it should (`docs/adr/0001-app-side-physics-for-position.md`).
- The route profile is synthesized from a reference ride
  (`resources/olias-route.csv`); three more recordings of the same loop keep
  the physics honest via replay validation (simulate a real ride's power,
  demand the real ride's time).

## Riding

```sh
uv run olias ride          # first run opens a device picker; space pauses, q saves & quits
uv run olias ride --demo   # no hardware: preview the TUI with a simulated rider
uv run olias devices       # re-pick the trainer / HR monitor later
```

Recordings land in `sessions/` as FIT files.

### macOS: Bluetooth permission

macOS kills command-line processes that touch Bluetooth without permission —
`olias ride` then appears to crash instantly (`abort`, no traceback). Grant
your terminal app Bluetooth access first: **System Settings → Privacy &
Security → Bluetooth → +**, add your terminal (e.g. `/Applications/Warp.app`
or Terminal), and relaunch it.

## Developing

```sh
uv run pytest                                # the whole suite, hardware-free
uv run tools/calibrate.py                    # refit rolling resistance to the reference rides
uv run --with fitdecode tools/build_route.py # regenerate the route profile CSV
```

Domain language lives in `CONTEXT.md`, decisions in `docs/adr/`, agent
guidance in `CLAUDE.md`.
