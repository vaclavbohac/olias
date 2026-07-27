"""Entry points: olias devices (scan & remember), olias ride (the session)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

DEVICES_PATH = Path.home() / ".config" / "olias" / "devices.json"
SESSIONS_DIR = Path("sessions")


def _pick_devices() -> dict | None:
    """Run the TUI picker; persist and return the selection (None if cancelled)."""
    from olias.devicepicker import DevicePickerApp

    selection = DevicePickerApp().run()
    if selection is None or selection.get("trainer") is None:
        return None
    DEVICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEVICES_PATH.write_text(json.dumps(selection, indent=2))
    print(f"saved to {DEVICES_PATH}")
    return selection


def cmd_devices(_args) -> int:
    selection = _pick_devices()
    if selection is None:
        print("cancelled — nothing saved", file=sys.stderr)
        return 1
    return 0


def cmd_ride(args) -> int:
    from olias import config
    from olias.ble.heart import HeartRateAdapter
    from olias.ble.trainer import TrainerAdapter
    from olias.engine import SessionEngine
    from olias.recording import SessionRecorder
    from olias.reference import ReferenceRide
    from olias.session import SessionRunner
    from olias.tui import RideApp

    if args.demo:
        trainer, heart = _DemoTrainer(), _DemoHeart()
    else:
        stored = json.loads(DEVICES_PATH.read_text()) if DEVICES_PATH.exists() else {}
        if not stored.get("trainer") and not args.trainer:
            stored = _pick_devices()  # first ride: choose devices in the TUI
            if stored is None:
                print("no trainer selected", file=sys.stderr)
                return 1
        stored_trainer = stored.get("trainer") or {}
        stored_heart = stored.get("heart") or {}
        trainer_addr = args.trainer or stored_trainer.get("address")
        heart_addr = args.heart or stored_heart.get("address")
        trainer = TrainerAdapter(trainer_addr, name=stored_trainer.get("name"))
        heart = (
            HeartRateAdapter(heart_addr, name=stored_heart.get("name"))
            if heart_addr
            else _NoHeart()
        )

    profile = config.load_route_profile()
    engine = SessionEngine(
        profile=profile,
        rider_model=config.default_rider_model(),
        reference=ReferenceRide.load(config.RESOURCES / "olias-ride-001.fit"),
    )

    if args.resume:
        prior_path = Path(args.resume)
        if not prior_path.exists():
            print(f"no such session: {prior_path}", file=sys.stderr)
            return 1
        recorder = SessionRecorder.resume_from(prior_path, profile)
        prior = ReferenceRide.load(prior_path)
        climb = profile.climb
        cadence_sum, cadence_samples = recorder.seeded_cadence
        engine.restore(
            position_m=prior.total_distance_m,
            elapsed_s=prior.total_time_s,
            climb_started_at_s=(
                prior.elapsed_s_at(climb.start_m)
                if prior.total_distance_m > climb.start_m
                else None
            ),
            climb_ended_at_s=(
                prior.elapsed_s_at(climb.end_m) if prior.total_distance_m >= climb.end_m else None
            ),
            cadence_sum=cadence_sum,
            cadence_samples=cadence_samples,
        )
        print(
            f"continuing from {prior.total_distance_m / 1000:.2f} km, "
            f"{int(prior.total_time_s) // 60} min ridden — pedal to resume"
        )
    else:
        recorder = SessionRecorder(profile)

    stamp = datetime.fromtimestamp(time.time()).strftime("%Y%m%d-%H%M%S")
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not args.demo:
        logging.basicConfig(
            filename=SESSIONS_DIR / f"olias-{stamp}.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    log = logging.getLogger("olias.ride")
    log.info(
        "session starting (trainer=%s heart=%s)",
        getattr(trainer, "address", "demo"),
        getattr(heart, "address", None),
    )

    app_holder = {}

    def on_snapshot(snap, wall_s):
        recorder.on_snapshot(snap, wall_s)
        app = app_holder.get("app")
        if app is not None:
            # runner executes as a textual worker on the app's own event loop
            app.update_snapshot(snap)

    runner = SessionRunner(
        engine=engine, trainer=trainer, heart=heart, on_snapshot=on_snapshot, feel=args.feel
    )
    app = RideApp(runner=runner, trainer=trainer, heart=heart, profile=profile)
    app_holder["app"] = app

    async def main_async():
        stop = runner.stop
        tasks = []
        if isinstance(trainer, TrainerAdapter):
            tasks.append(asyncio.create_task(trainer.run(stop)))
        if isinstance(heart, HeartRateAdapter):
            tasks.append(asyncio.create_task(heart.run(stop)))
        await app.run_async()
        stop.set()
        for t in tasks:
            t.cancel()

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        log.info("session ended: interrupted (ctrl-c)")
    except Exception:
        log.exception("session crashed")
        raise
    finally:
        # ride data is never thrown away, even on a crash
        written = recorder.write(SESSIONS_DIR / f"olias-{stamp}.fit")
        log.info("recording: %s", written or "nothing ridden")
        print(f"session saved: {written}" if written else "nothing ridden — no file saved")
    return 0


class _NoHeart:
    latest_bpm = None


class _DemoTrainer:
    """Simulated rider for previewing the TUI: steady tempo with some life in it."""

    connected = True

    def __init__(self):
        self.grades = []

    @property
    def latest_power_w(self):
        import math

        return 180.0 + 25.0 * math.sin(time.time() / 7)

    @property
    def latest_cadence_rpm(self):
        import math

        return 82.0 + 8.0 * math.sin(time.time() / 9)

    def set_grade(self, grade_pct):
        self.grades.append(grade_pct)


class _DemoHeart:
    @property
    def latest_bpm(self):
        import math

        return round(138 + 6 * math.sin(time.time() / 11))


def main() -> int:
    parser = argparse.ArgumentParser(prog="olias", description="Ride to Olías on the Kickr")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("devices", help="scan for the trainer and HR monitor, remember them")
    ride = sub.add_parser("ride", help="ride the route")
    ride.add_argument("--trainer", help="trainer BLE address (overrides stored)")
    ride.add_argument("--hr", dest="heart", help="heart rate BLE address (overrides stored)")
    ride.add_argument("--demo", action="store_true", help="simulated rider, no hardware needed")
    ride.add_argument(
        "--continue",
        dest="resume",
        metavar="SESSION_FIT",
        help="continue a previous session from where it stopped",
    )
    ride.add_argument(
        "--feel",
        type=float,
        default=1.0,
        help="scale the grade sent to the trainer (feel only, e.g. 0.7); "
        "simulation stays at full grade",
    )
    args = parser.parse_args()
    return {"devices": cmd_devices, "ride": cmd_ride}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
