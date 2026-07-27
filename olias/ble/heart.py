"""BLE Heart Rate adapter: latest bpm, reconnect forever, never affects the sim."""
from __future__ import annotations

import asyncio
import logging
import struct

from bleak import BleakClient

logger = logging.getLogger(__name__)

HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"


def parse_heart_rate(payload: bytes) -> int:
    if payload[0] & 0x01:  # 16-bit value
        return struct.unpack_from("<H", payload, 1)[0]
    return payload[1]


class HeartRateAdapter:
    def __init__(self, address: str):
        self.address = address
        self.latest_bpm: int | None = None  # None while disconnected

    async def run(self, stop: asyncio.Event) -> None:
        backoff = 1.0
        while not stop.is_set():
            try:
                async with BleakClient(self.address) as client:
                    await client.start_notify(HR_MEASUREMENT, self._on_measurement)
                    logger.info("heart rate connected")
                    backoff = 1.0
                    while not stop.is_set() and client.is_connected:
                        await asyncio.sleep(0.5)
            except Exception as exc:
                logger.warning("heart rate connection lost: %s", exc)
            self.latest_bpm = None
            if not stop.is_set():
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10.0)

    def _on_measurement(self, _characteristic, payload: bytearray) -> None:
        self.latest_bpm = parse_heart_rate(bytes(payload))
