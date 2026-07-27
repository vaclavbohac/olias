"""Ride screen, readable from the bike: numerals scale with the terminal."""
from __future__ import annotations

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical
from textual.widgets import Footer, Static

from olias.bigdigits import GLYPH_ROWS, render_big
from olias.engine import EngineState, Snapshot
from olias.profile import RouteProfile

SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def fmt_hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fmt_delta(seconds: float) -> str:
    sign = "+" if seconds >= 0 else "-"
    s = abs(int(seconds))
    return f"{sign}{s // 60}:{s % 60:02d}"


def fmt_ms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


class RideApp(App):
    """The session dashboard; the runner drives it via update_snapshot()."""

    CSS = """
    .label { color: $text-muted; text-align: center; width: 100%; }
    .big { text-align: center; width: 100%; }
    #ascent { color: $success; }
    #climb-row { grid-size: 3; grid-columns: 1fr 1fr 1fr; height: auto; padding-top: 1; }
    #climb-row Static { text-align: center; width: 100%; }
    #climb-row Vertical, #stats Vertical { height: auto; }
    #stats { grid-size: 5; grid-columns: 1fr 1fr 1fr 1fr 1fr; height: auto; padding-top: 1; }
    #route-progress { height: auto; padding: 0 2; margin-top: 1; }
    #stats Static { text-align: center; width: 100%; }
    #bottom { dock: bottom; height: 1; }
    #bottom Static { text-align: center; width: 100%; color: $text-muted; }
    """

    BINDINGS = [
        ("space", "pause", "Pause/Resume"),
        ("q", "quit_ride", "End ride & save"),
    ]

    def __init__(self, runner, trainer, heart, profile: RouteProfile):
        super().__init__()
        self._runner = runner
        self._trainer = trainer
        self._heart = heart
        self._profile = profile
        self._spark_cache: tuple[int, str] | None = None  # (width, chars)

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("REMAINING ASCENT · M", classes="label"),
            Static("", id="ascent", classes="big"),
            Grid(
                Vertical(Static("", id="climb-time-label", classes="label"), Static("", id="climb-time", classes="big")),
                Vertical(Static("", id="eta-label", classes="label"), Static("", id="eta", classes="big")),
                Vertical(Static("", id="delta-label", classes="label"), Static("", id="delta", classes="big")),
                id="climb-row",
            ),
            Grid(
                Vertical(Static("POWER · W", classes="label"), Static("", id="power", classes="big")),
                Vertical(Static("CADENCE · RPM", classes="label"), Static("", id="cadence", classes="big")),
                Vertical(Static("HEART · BPM", classes="label"), Static("", id="hr", classes="big")),
                Vertical(Static("SPEED · KM/H", classes="label"), Static("", id="speed", classes="big")),
                Vertical(Static("GRADE · %", classes="label"), Static("", id="grade", classes="big")),
                id="stats",
            ),
            Static("", id="route-progress"),
        )
        yield Vertical(Static("", id="status"), id="bottom")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._drive(), exclusive=True)

    async def _drive(self) -> None:
        await self._runner.run()
        self.exit()

    def _scales(self) -> tuple[int, int]:
        """(headline scale, stats scale) chosen from the terminal height."""
        rows = self.size.height or 30
        # headline ~35% of height, stats ~15%; both at least 1 glyph tall
        return max(1, int(rows * 0.35) // GLYPH_ROWS), max(1, int(rows * 0.15) // GLYPH_ROWS)

    def update_snapshot(self, snap: Snapshot) -> None:
        big, small = self._scales()
        self.query_one("#ascent", Static).update(
            render_big(f"{snap.remaining_ascent_m:.0f}", big)
        )

        climb_time_label = self.query_one("#climb-time-label", Static)
        climb_time = self.query_one("#climb-time", Static)
        if snap.climb_time_s is not None:
            on_climb = snap.climb_delta_s is not None
            climb_time_label.update("CLIMB TIME" if on_climb else "CLIMB RESULT")
            climb_time.update(render_big(fmt_ms(snap.climb_time_s), small))
        else:
            climb_time_label.update("")
            climb_time.update("")

        eta_label = self.query_one("#eta-label", Static)
        eta = self.query_one("#eta", Static)
        if snap.summit_eta_s is not None:
            eta_label.update("TO SUMMIT · EST")
            eta.update(render_big(fmt_ms(snap.summit_eta_s), small))
        else:
            eta_label.update("")
            eta.update("")

        delta_label = self.query_one("#delta-label", Static)
        delta = self.query_one("#delta", Static)
        if snap.climb_delta_s is not None:
            ahead = snap.climb_delta_s >= 0
            delta_label.update("AHEAD OF REFERENCE-YOU" if ahead else "BEHIND REFERENCE-YOU")
            delta.update(render_big(fmt_delta(snap.climb_delta_s), small))
            delta.styles.color = "green" if ahead else "red"
        else:
            delta_label.update("")
            delta.update("")

        self.query_one("#power", Static).update(render_big(f"{snap.power_w:.0f}", small))
        cadence = f"{snap.cadence_rpm:.0f}" if snap.cadence_rpm is not None else "--"
        self.query_one("#cadence", Static).update(render_big(cadence, small))
        hr = f"{snap.heart_rate_bpm}" if snap.heart_rate_bpm else "--"
        self.query_one("#hr", Static).update(render_big(hr, small))
        self.query_one("#speed", Static).update(render_big(f"{snap.speed_ms * 3.6:.1f}", small))
        self.query_one("#grade", Static).update(render_big(f"{snap.grade_pct:+.1f}", small))

        self.query_one("#route-progress", Static).update(self._route_progress(snap))

        parts = [f"{snap.position_m / 1000:.2f} km", fmt_hms(snap.elapsed_s)]
        if snap.avg_cadence_rpm is not None:
            parts.append(f"avg cad {snap.avg_cadence_rpm:.0f}")
        if snap.state is EngineState.PAUSED:
            parts.append("● PAUSED")
        if snap.state is EngineState.ARMED:
            parts.append("pedal to start")
        if snap.state is EngineState.FINISHED:
            parts.append("FINISHED")
        parts.append("trainer ✓" if self._trainer.connected else "trainer ✗ (0 W)")
        parts.append("hr ✓" if self._heart.latest_bpm is not None else "hr ✗")
        self.query_one("#status", Static).update("      ".join(parts))

    PROFILE_ROWS = 4

    def _route_progress(self, snap: Snapshot) -> Text:
        """The route's elevation silhouette, filling with color as it is ridden."""
        width = max(20, (self.size.width or 80) - 10)
        rows = self.PROFILE_ROWS
        if self._spark_cache is None or self._spark_cache[0] != width:
            total = self._profile.total_distance_m
            alts = [self._profile.altitude_at(i / (width - 1) * total) for i in range(width)]
            lo, hi = min(alts), max(alts)
            span = (hi - lo) or 1.0
            # per column: eighths of fill across the full multi-row height
            levels = [1 + int((a - lo) / span * (rows * 8 - 1)) for a in alts]
            self._spark_cache = (width, levels)
        levels = self._spark_cache[1]
        idx = min(width - 1, int(snap.position_m / self._profile.total_distance_m * width))

        text = Text()
        for row in range(rows):
            from_bottom = rows - 1 - row
            for col, level in enumerate(levels):
                full, rem = level // 8, level % 8
                if from_bottom < full:
                    ch = "█"
                elif from_bottom == full and rem:
                    ch = SPARK_BLOCKS[rem - 1]
                else:
                    ch = " "
                if col < idx:
                    style = "green"
                elif col == idx:
                    style = "reverse bright_white" if ch != " " else "dim"
                else:
                    style = "dim"
                text.append(ch, style=style)
            if row == rows - 1:
                pct = snap.position_m / self._profile.total_distance_m * 100
                text.append(f" {pct:3.0f}%", style="dim")
            if row < rows - 1:
                text.append("\n")
        return text

    def action_pause(self) -> None:
        self._runner.pause_toggle()

    def action_quit_ride(self) -> None:
        self._runner.stop.set()
        self.exit()
