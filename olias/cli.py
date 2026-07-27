"""Entry points: olias devices (scan & remember), olias ride (the session)."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

DEVICES_PATH = Path.home() / ".config" / "olias" / "devices.json"
SESSIONS_DIR = Path("sessions")


def cmd_devices(_args) -> int:
    from bleak import BleakScanner

    print("scanning for 10 s — wake the trainer and strap on the HR monitor...")
    devices = asyncio.run(BleakScanner.discover(timeout=10.0))
    named = [d for d in devices if d.name]
    if not named:
        print("no named BLE devices found")
        return 1
    for i, d in enumerate(named):
        print(f"  [{i}] {d.name}  ({d.address})")

    def pick(prompt):
        raw = input(prompt).strip()
        if not raw:
            return None
        d = named[int(raw)]
        return {"address": d.address, "name": d.name}

    config = {
        "trainer": pick("trainer number (enter to skip): "),
        "heart": pick("heart rate number (enter to skip): "),
    }
    DEVICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEVICES_PATH.write_text(json.dumps(config, indent=2))
    print(f"saved to {DEVICES_PATH}")
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

    if not DEVICES_PATH.exists() and not (args.trainer and args.heart):
        print("no devices configured — run `olias devices` first", file=sys.stderr)
        return 1
    stored = json.loads(DEVICES_PATH.read_text()) if DEVICES_PATH.exists() else {}
    trainer_addr = args.trainer or (stored.get("trainer") or {}).get("address")
    heart_addr = args.heart or (stored.get("heart") or {}).get("address")
    if not trainer_addr:
        print("no trainer configured", file=sys.stderr)
        return 1

    profile = config.load_route_profile()
    engine = SessionEngine(
        profile=profile,
        rider_model=config.default_rider_model(),
        reference=ReferenceRide.load(config.RESOURCES / "olias-ride-001.fit"),
    )
    trainer = TrainerAdapter(trainer_addr)
    heart = HeartRateAdapter(heart_addr) if heart_addr else _NoHeart()
    recorder = SessionRecorder(profile)

    app_holder = {}

    def on_snapshot(snap, wall_s):
        recorder.on_snapshot(snap, wall_s)
        app = app_holder.get("app")
        if app is not None:
            # runner executes as a textual worker on the app's own event loop
            app.update_snapshot(snap)

    runner = SessionRunner(engine=engine, trainer=trainer, heart=heart, on_snapshot=on_snapshot)
    app = RideApp(runner=runner, trainer=trainer, heart=heart)
    app_holder["app"] = app

    async def main_async():
        stop = runner.stop
        tasks = [asyncio.create_task(trainer.run(stop))]
        if isinstance(heart, HeartRateAdapter):
            tasks.append(asyncio.create_task(heart.run(stop)))
        await app.run_async()
        stop.set()
        for t in tasks:
            t.cancel()

    asyncio.run(main_async())

    stamp = datetime.fromtimestamp(time.time()).strftime("%Y%m%d-%H%M%S")
    written = recorder.write(SESSIONS_DIR / f"olias-{stamp}.fit")
    print(f"session saved: {written}" if written else "nothing ridden — no file saved")
    return 0


class _NoHeart:
    latest_bpm = None


def main() -> int:
    parser = argparse.ArgumentParser(prog="olias", description="Ride to Olías on the Kickr")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("devices", help="scan for the trainer and HR monitor, remember them")
    ride = sub.add_parser("ride", help="ride the route")
    ride.add_argument("--trainer", help="trainer BLE address (overrides stored)")
    ride.add_argument("--hr", dest="heart", help="heart rate BLE address (overrides stored)")
    args = parser.parse_args()
    return {"devices": cmd_devices, "ride": cmd_ride}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
