# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Olias is a bike trainer app that simulates a real bike ride to Olias (Málaga) using the author's recorded ride telemetry. Planned functionality (per README):

- Connects to a Wahoo Kickr trainer via Bluetooth
- Connects to a heart rate monitor via Bluetooth
- Controls trainer resistance based on the rider's current position along the route
- Replays telemetry from real rides to simulate the same ride

The project is at the scaffold stage: `main.py` is a hello-world entry point and there are no dependencies, tests, or package structure yet.

## Environment and commands

- Python 3.11 (pinned in `.python-version`); project metadata in `pyproject.toml` (uv-style layout).
- Run the app: `uv run main.py` (or `python main.py`)
- Add a dependency: `uv add <package>`

No linter, formatter, or test runner is configured yet.
