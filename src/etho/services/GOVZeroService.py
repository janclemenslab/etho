#!/usr/bin/env python
import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import defopt

from .ZeroService import BaseZeroService
from .utils.log_exceptions import for_all_methods, log_exceptions

try:
    from bleak import AdvertisementData, BleakScanner, BLEDevice

    bleak_import_error = None
except ImportError as bleak_import_error:
    AdvertisementData = Any
    BLEDevice = Any
    BleakScanner = None


DEFAULT_INTERVAL = 60.0
H5075_MANUFACTURER_ID = 0xEC88


def normalize_address(address: str) -> str:
    if address is None:
        raise ValueError("address is required")
    address = address.strip()
    if not address:
        raise ValueError("address is required")
    return address.upper()


@dataclass
class H5075Measurement:
    timestamp: datetime
    temperature_c: float
    humidity: float


def decode_h5075_measurement(payload: bytes, timestamp: Optional[datetime] = None) -> H5075Measurement:
    if len(payload) < 4:
        raise ValueError("manufacturer payload is too short")

    raw = int.from_bytes(payload[1:4], byteorder="big", signed=False)
    is_negative = bool(raw & 0x800000)
    if is_negative:
        raw ^= 0x800000

    temperature_c = int(raw / 1000) / 10.0
    if is_negative:
        temperature_c = -temperature_c
    humidity = (raw % 1000) / 10.0

    if timestamp is None:
        timestamp = datetime.now()

    return H5075Measurement(timestamp=timestamp, temperature_c=temperature_c, humidity=humidity)


def format_measurement_log_line(measurement: H5075Measurement) -> str:
    return f"{measurement.timestamp:%Y-%m-%d %H:%M:%S},{measurement.temperature_c:.1f},{measurement.humidity:.1f}"


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class GOV(BaseZeroService):
    LOGGING_PORT = 1455
    SERVICE_PORT = 4255
    SERVICE_NAME = "GOV"

    def setup(self, address: str, interval: float = DEFAULT_INTERVAL, duration: float = 0):
        if bleak_import_error is not None:
            raise bleak_import_error

        interval = DEFAULT_INTERVAL if interval is None else float(interval)
        if interval <= 0:
            raise ValueError("interval must be > 0")

        self.address = normalize_address(address)
        self.interval = interval
        self.duration = float(duration)
        self.measurement: Optional[H5075Measurement] = None
        self.data = None

        self._state_lock = threading.Lock()
        self._latest_measurement: Optional[H5075Measurement] = None
        self._latest_measurement_seen_at: Optional[float] = None
        self._last_logged_measurement_seen_at: Optional[float] = None
        self._last_emit_monotonic: Optional[float] = None
        self._thread_stopper = threading.Event()
        self._scanner_thread = threading.Thread(target=self._scanner_worker, args=(self._thread_stopper,), daemon=True)

        if self.duration > 0:
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={"stop_service": True})

        self.info = {
            "job": {
                "address": self.address,
                "interval": f"{self.interval}s",
                "duration": f"{self.duration}s",
            }
        }

    def start(self):
        self._time_started = time.time()
        self._scanner_thread.start()
        self._emit_info(f"scanning for {self.address}")
        self._emit_info(f"logging at {self.interval:.1f}s resolution")
        if hasattr(self, "_thread_timer"):
            self._emit_info(f"duration {self.duration} seconds")
            self._thread_timer.start()
            self._emit_info("finish timer started")

    def _scanner_worker(self, stop_event):
        try:
            asyncio.run(self._scanner_loop(stop_event))
        except Exception:
            self.log.exception("scanner loop failed")

    async def _scanner_loop(self, stop_event):
        async with BleakScanner(detection_callback=self._detection_callback):
            while not stop_event.is_set():
                self._maybe_log_latest_measurement()
                await asyncio.sleep(0.2)

    def _detection_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        if getattr(device, "address", None) is None:
            return
        if normalize_address(device.address) != self.address:
            return

        manufacturer_data = advertisement_data.manufacturer_data.get(H5075_MANUFACTURER_ID)
        if manufacturer_data is None:
            return

        measurement = decode_h5075_measurement(manufacturer_data, timestamp=datetime.now())
        seen_at = time.monotonic()
        self._record_measurement(measurement, seen_at)
        self._maybe_log_latest_measurement(now_monotonic=seen_at)

    def _record_measurement(self, measurement: H5075Measurement, seen_at: Optional[float] = None):
        if seen_at is None:
            seen_at = time.monotonic()

        with self._state_lock:
            self.measurement = measurement
            self._latest_measurement = measurement
            self._latest_measurement_seen_at = seen_at

    def _maybe_log_latest_measurement(self, now_monotonic: Optional[float] = None):
        if now_monotonic is None:
            now_monotonic = time.monotonic()

        with self._state_lock:
            if self._latest_measurement is None or self._latest_measurement_seen_at is None:
                return

            if self._latest_measurement_seen_at == self._last_logged_measurement_seen_at:
                return

            if self._last_emit_monotonic is not None and now_monotonic - self._last_emit_monotonic < self.interval:
                return

            line = format_measurement_log_line(self._latest_measurement)
            self.data = line
            self._last_logged_measurement_seen_at = self._latest_measurement_seen_at
            self._last_emit_monotonic = now_monotonic

        self._emit_info(line)

    def _write_to_console(self, message: str):
        try:
            print(message, flush=True)
        except OSError:
            # Hidden/disowned Windows service processes can have an invalid stdout.
            # Logging should continue even when there is no usable console.
            pass

    def _emit_info(self, message: str):
        self.log.info(message)
        self._write_to_console(message)

    def _emit_warning(self, message: str):
        self.log.warning(message)
        self._write_to_console(message)

    def finish(self, stop_service=False):
        self._emit_warning("stopping")
        if hasattr(self, "_thread_stopper"):
            self._thread_stopper.set()
        if hasattr(self, "_thread_timer"):
            self._thread_timer.cancel()
        if hasattr(self, "_scanner_thread") and self._scanner_thread.is_alive() and threading.current_thread() is not self._scanner_thread:
            self._scanner_thread.join(timeout=5)

        self._emit_warning("   stopped ")
        self._flush_loggers()
        if stop_service:
            time.sleep(2)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self):
        return hasattr(self, "_scanner_thread") and self._scanner_thread.is_alive()

    def test(self):
        return bleak_import_error is None

    def cleanup(self):
        self.finish()
        return True


def cli(serializer: str = "default", port: Optional[str] = None):
    if port is None:
        port = GOV.SERVICE_PORT
    s = GOV(serializer=serializer)
    s.bind(f"tcp://0.0.0.0:{port}")
    print("running GOVZeroService")
    s.run()
    print("done")


if __name__ == "__main__":
    defopt.run(cli)
