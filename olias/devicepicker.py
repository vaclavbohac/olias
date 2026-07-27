"""Device picker: scan for trainers and HR straps, choose them in the TUI.

Filters by advertised service: only FTMS devices land in the trainer list,
only Heart Rate devices in the HR list. Returns
{"trainer": {"address", "name"} | None, "heart": {...} | None} or None if
cancelled.
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

FTMS_UUID = "00001826-0000-1000-8000-00805f9b34fb"
HR_UUID = "0000180d-0000-1000-8000-00805f9b34fb"

SCAN_SECONDS = 10.0


async def scan():
    """[(name, address, is_trainer, is_heart)] for advertisers of either service."""
    from bleak import BleakScanner

    found = await BleakScanner.discover(timeout=SCAN_SECONDS, return_adv=True)
    results = []
    for device, adv in found.values():
        uuids = {u.lower() for u in (adv.service_uuids or [])}
        is_trainer, is_heart = FTMS_UUID in uuids, HR_UUID in uuids
        if is_trainer or is_heart:
            results.append((device.name or device.address, device.address, is_trainer, is_heart))
    return results


class DevicePickerApp(App):
    CSS = """
    #title { text-style: bold; padding: 1 2; }
    #hint { color: $text-muted; padding: 0 2; }
    OptionList { margin: 1 2; height: 1fr; }
    """

    BINDINGS = [
        ("r", "rescan", "Rescan"),
        ("s", "skip", "Skip"),
        ("q", "cancel", "Cancel"),
    ]

    def __init__(self):
        super().__init__()
        self._devices: list[tuple[str, str, bool, bool]] = []
        self._stage = "trainer"
        self._selection = {"trainer": None, "heart": None}

    def compose(self) -> ComposeResult:
        yield Static("", id="title")
        yield Static("", id="hint")
        yield OptionList(id="list")
        yield Footer()

    def on_mount(self) -> None:
        self.action_rescan()

    def action_rescan(self) -> None:
        self.query_one("#title", Static).update("Scanning for 10 s…")
        self.query_one("#hint", Static).update("wake the trainer, strap on the HR monitor")
        self.query_one("#list", OptionList).clear_options()
        self.run_worker(self._scan(), exclusive=True)

    async def _scan(self) -> None:
        try:
            self._devices = await scan()
        except Exception as exc:
            self.query_one("#title", Static).update("Bluetooth unavailable")
            self.query_one("#hint", Static).update(
                f"{exc} — on macOS grant Bluetooth to your terminal in "
                "System Settings › Privacy & Security › Bluetooth, then press r"
            )
            return
        self._show_stage()

    def _show_stage(self) -> None:
        wanted = 2 if self._stage == "trainer" else 3  # tuple index of the capability flag
        title = "Pick your TRAINER" if self._stage == "trainer" else "Pick your HEART RATE monitor"
        options = [
            Option(f"{name}  ({address})", id=address)
            for name, address, *flags in self._devices
            if (name, address, *flags)[wanted]
        ]
        self.query_one("#title", Static).update(title)
        hint = "enter: select · r: rescan · q: cancel"
        if self._stage == "heart":
            hint += " · s: ride without HR"
        self.query_one("#hint", Static).update(hint if options else f"none found — {hint}")
        option_list = self.query_one("#list", OptionList)
        option_list.clear_options()
        option_list.add_options(options)
        if options:
            option_list.highlighted = 0
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        address = event.option.id
        name = next(n for n, a, *_ in self._devices if a == address)
        self._selection[self._stage] = {"address": address, "name": name}
        self._advance()

    def action_skip(self) -> None:
        if self._stage == "heart":
            self._advance()

    def _advance(self) -> None:
        if self._stage == "trainer":
            self._stage = "heart"
            self._show_stage()
        else:
            self.exit(self._selection)

    def action_cancel(self) -> None:
        self.exit(None)
