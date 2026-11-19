"""Fake IoT system: a backend relays /remote commands to an LED device."""
import queue
import random
import threading
import time

AUTO_OFF_SECS = 30.0
BLINK_SECS = 0.02


class Device:
    def __init__(self, device_id="dev-1"):
        self.device_id = device_id
        self._lock = threading.Lock()
        self._leds = {"red": "off", "green": "off"}
        self._subscribers = []

    def read_leds(self):
        """Snapshot of LED states, e.g. {"red": "on", "green": "off"}."""
        with self._lock:
            return dict(self._leds)

    def subscribe(self, callback):
        """callback({"led": "red", "state": "on"}) is called on every LED change."""
        self._subscribers.append(callback)

    def _set(self, led, state):
        with self._lock:
            self._leds[led] = state
        for cb in list(self._subscribers):
            cb({"led": led, "state": state})


class Backend:
    def __init__(self, device, schedule=None):
        self._device = device
        self._schedule = schedule or _schedule_with_timer
        self._q = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def post(self, path, body):
        """e.g. post("/remote", {"device_id": "dev-1", "red": "on"}); states: on, off, blink."""
        self._q.put((path, dict(body)))

    def _run(self):
        while True:
            path, body = self._q.get()
            time.sleep(random.uniform(0.05, 0.3))
            if path != "/remote" or body.get("device_id") != self._device.device_id:
                continue
            for led in ("red", "green"):
                if led in body:
                    self._apply(led, body[led])

    def _apply(self, led, state):
        if state == "blink":
            self._device._set(led, "blink")
            time.sleep(BLINK_SECS)
            self._device._set(led, "off")
        else:
            self._device._set(led, state)
            if state == "on":
                self._schedule(AUTO_OFF_SECS, lambda: self._device._set(led, "off"))


def _schedule_with_timer(delay_secs, action):
    t = threading.Timer(delay_secs, action)
    t.daemon = True
    t.start()
