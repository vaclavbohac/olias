"""Ride screen: Remaining Ascent as the headline, Climb Delta when it matters."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical
from textual.widgets import Footer, Static

from olias.engine import EngineState, Snapshot


def fmt_hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fmt_delta(seconds: float) -> str:
    sign = "+" if seconds >= 0 else "-"
    s = abs(int(seconds))
    return f"{sign}{s // 60}:{s % 60:02d}"


class RideApp(App):
    """The session dashboard; the runner drives it via update_snapshot()."""

    CSS = """
    #ascent { content-align: center middle; text-style: bold; height: 5; }
    #delta { content-align: center middle; height: 3; }
    #stats { grid-size: 3 2; height: 8; }
    #stats Static { content-align: center middle; }
    #status { dock: bottom; height: 1; color: $text-muted; }
    """

    BINDINGS = [
        ("space", "pause", "Pause/Resume"),
        ("q", "quit_ride", "End ride & save"),
    ]

    def __init__(self, runner, trainer, heart):
        super().__init__()
        self._runner = runner
        self._trainer = trainer
        self._heart = heart

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("—", id="ascent"),
            Static("", id="delta"),
            Grid(
                Static("", id="power"),
                Static("", id="hr"),
                Static("", id="speed"),
                Static("", id="grade"),
                Static("", id="distance"),
                Static("", id="elapsed"),
                id="stats",
            ),
            Static("", id="status"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._drive(), exclusive=True)

    async def _drive(self) -> None:
        await self._runner.run()
        self.exit()

    def update_snapshot(self, snap: Snapshot) -> None:
        self.query_one("#ascent", Static).update(
            f"⛰  {snap.remaining_ascent_m:,.0f} m of climbing to go"
        )
        if snap.climb_delta_s is not None:
            mood = "ahead of" if snap.climb_delta_s >= 0 else "behind"
            self.query_one("#delta", Static).update(
                f"{fmt_delta(snap.climb_delta_s)} {mood} reference-you"
            )
        else:
            self.query_one("#delta", Static).update("")
        self.query_one("#power", Static).update(f"{snap.power_w:.0f} W")
        hr = f"{snap.heart_rate_bpm} bpm" if snap.heart_rate_bpm else "-- bpm"
        self.query_one("#hr", Static).update(hr)
        self.query_one("#speed", Static).update(f"{snap.speed_ms * 3.6:.1f} km/h")
        self.query_one("#grade", Static).update(f"{snap.grade_pct:+.1f} %")
        self.query_one("#distance", Static).update(f"{snap.position_m / 1000:.2f} km")
        self.query_one("#elapsed", Static).update(fmt_hms(snap.elapsed_s))

        parts = []
        if snap.state is EngineState.PAUSED:
            parts.append("PAUSED")
        if snap.state is EngineState.ARMED:
            parts.append("pedal to start")
        if snap.state is EngineState.FINISHED:
            parts.append("FINISHED")
        parts.append("trainer ✓" if self._trainer.connected else "trainer ✗ (0 W)")
        parts.append("hr ✓" if self._heart.latest_bpm is not None else "hr ✗")
        self.query_one("#status", Static).update("   ".join(parts))

    def action_pause(self) -> None:
        self._runner.pause_toggle()

    def action_quit_ride(self) -> None:
        self._runner.stop.set()
        self.exit()
