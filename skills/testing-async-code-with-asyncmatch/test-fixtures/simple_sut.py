"""Fake IoT system: an HTTP-like backend relays commands to a device asynchronously.

post() returns immediately; a worker thread applies each command to the device
after a random 50-300ms latency. Commands are processed strictly in order.
Commands addressed to a different device_id are silently dropped.
"""
import queue
import random
import threading
import time

LED_PINS = {"red_led": "gpio3", "green_led": "gpio4"}


class Device:
    def __init__(self, device_id="dev-1"):
        self.device_id = device_id
        self._lock = threading.Lock()
        self._gpios = {"gpio3": "low", "gpio4": "low"}

    def read_gpios(self):
        """Snapshot of GPIO pin states, e.g. {"gpio3": "high", "gpio4": "low"}."""
        with self._lock:
            return dict(self._gpios)

    def _set(self, pin, level):
        with self._lock:
            self._gpios[pin] = level


class Backend:
    def __init__(self, device):
        self._device = device
        self._q = queue.Queue()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def post(self, path, body):
        """Accepts e.g. post("/remote", {"device_id": "dev-1", "red_led": "on"}). Returns immediately."""
        self._q.put((path, dict(body)))

    def _run(self):
        while True:
            path, body = self._q.get()
            time.sleep(random.uniform(0.05, 0.3))
            if path != "/remote" or body.get("device_id") != self._device.device_id:
                continue
            for led, pin in LED_PINS.items():
                if led in body:
                    self._device._set(pin, "high" if body[led] == "on" else "low")
