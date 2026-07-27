"""FTMS trainer adapter (ADR-0002): power in, grade out, reconnect forever."""
from __future__ import annotations

import asyncio
import logging
import struct

from bleak import BleakClient

logger = logging.getLogger(__name__)


async def rescan_by_name(adapter) -> None:
    """macOS rotates BLE identifiers; a stale stored id is rescued by name."""
    if not adapter.name:
        return
    from bleak import BleakScanner

    logger.info("rescanning for %s by name", adapter.name)
    device = await BleakScanner.find_device_by_name(adapter.name, timeout=10.0)
    if device is not None and device.address != adapter.address:
        logger.info("found %s at new address %s", adapter.name, device.address)
        adapter.address = device.address

FTMS_SERVICE = "00001826-0000-1000-8000-00805f9b34fb"
INDOOR_BIKE_DATA = "00002ad2-0000-1000-8000-00805f9b34fb"
CONTROL_POINT = "00002ad9-0000-1000-8000-00805f9b34fb"

OP_REQUEST_CONTROL = 0x00
OP_SET_SIM_PARAMS = 0x11

# sim-parameter constants sent alongside grade; feel-only (position comes from
# app-side physics, ADR-0001), so road defaults are fine
SIM_CRR = 0.004   # unit 0.0001
SIM_CW = 0.51     # kg/m, unit 0.01


def parse_indoor_bike_data(payload: bytes) -> tuple[float | None, float | None]:
    """(instantaneous power W, instantaneous cadence rpm), each None if absent."""
    flags = struct.unpack_from("<H", payload, 0)[0]
    offset = 2
    cadence = None
    if not flags & 0x0001:  # More Data bit clear -> instantaneous speed present
        offset += 2
    if flags & 0x0002:  # average speed
        offset += 2
    if flags & 0x0004:  # instantaneous cadence, unit 0.5 rpm
        cadence = struct.unpack_from("<H", payload, offset)[0] / 2
        offset += 2
    if flags & 0x0008:  # average cadence
        offset += 2
    if flags & 0x0010:  # total distance (uint24)
        offset += 3
    if flags & 0x0020:  # resistance level
        offset += 2
    if flags & 0x0040:  # instantaneous power
        return float(struct.unpack_from("<h", payload, offset)[0]), cadence
    return None, cadence


class TrainerAdapter:
    """Maintains a connection to the Kickr; exposes latest power, accepts grade."""

    def __init__(self, address: str, name: str | None = None):
        self.address = address
        self.name = name
        self.latest_power_w: float | None = None  # None while disconnected
        self.latest_cadence_rpm: float | None = None
        self._client: BleakClient | None = None
        self._pending_grade_pct: float | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    def set_grade(self, grade_pct: float) -> None:
        """Remember the desired grade; the connection loop delivers it."""
        self._pending_grade_pct = grade_pct

    async def run(self, stop: asyncio.Event) -> None:
        backoff = 1.0
        failures = 0
        while not stop.is_set():
            try:
                async with BleakClient(self.address) as client:
                    self._client = client
                    await client.start_notify(INDOOR_BIKE_DATA, self._on_bike_data)
                    await client.write_gatt_char(
                        CONTROL_POINT, bytes([OP_REQUEST_CONTROL]), response=True
                    )
                    logger.info("trainer connected")
                    backoff, failures = 1.0, 0
                    await self._pump_grades(client, stop)
            except Exception as exc:
                logger.warning("trainer connection lost: %s", exc)
                failures += 1
            self._client = None
            self.latest_power_w = None  # disconnected -> engine coasts at 0 W
            self.latest_cadence_rpm = None
            if failures >= 3:
                await rescan_by_name(self)
                failures = 0
            if not stop.is_set():
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10.0)

    async def _pump_grades(self, client: BleakClient, stop: asyncio.Event) -> None:
        sent: float | None = None
        while not stop.is_set() and client.is_connected:
            grade = self._pending_grade_pct
            if grade is not None and grade != sent:
                await client.write_gatt_char(
                    CONTROL_POINT, self._sim_params(grade), response=True
                )
                sent = grade
            await asyncio.sleep(0.1)

    @staticmethod
    def _sim_params(grade_pct: float) -> bytes:
        return struct.pack(
            "<BhhBB",
            OP_SET_SIM_PARAMS,
            0,  # wind speed
            round(grade_pct * 100),
            round(SIM_CRR * 10000),
            round(SIM_CW * 100),
        )

    def _on_bike_data(self, _characteristic, payload: bytearray) -> None:
        power, cadence = parse_indoor_bike_data(bytes(payload))
        if power is not None:
            self.latest_power_w = power
        if cadence is not None:
            self.latest_cadence_rpm = cadence
