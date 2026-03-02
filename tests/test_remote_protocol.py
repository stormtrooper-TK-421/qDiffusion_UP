from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field

from PySide6.QtWidgets import QApplication
from websockets.sync.server import serve

import remote


class RecordingRemoteInference(remote.RemoteInference):
    def __init__(self, endpoint: str, password: str | None = None):
        super().__init__(gui=None, endpoint=endpoint, password=password)
        self.recorded: list[dict] = []

    def onResponse(self, response):  # type: ignore[override]
        self.recorded.append(response)


@dataclass
class FakeOptionsServer:
    host: str = "127.0.0.1"
    password: str = remote.DEFAULT_PASSWORD
    _thread: threading.Thread | None = None
    _stop: threading.Event = field(default_factory=threading.Event)
    port: int = 0

    def start(self) -> str:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((self.host, 0))
            self.port = sock.getsockname()[1]

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        deadline = time.time() + 3
        while time.time() < deadline:
            try:
                with socket.create_connection((self.host, self.port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        return f"ws://{self.host}:{self.port}"

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        scheme = remote.get_scheme(self.password)

        def handler(websocket) -> None:
            websocket.send(remote.encrypt(scheme, {"type": "hello", "data": {"id": "fake-client"}}))
            while not self._stop.is_set():
                try:
                    payload = websocket.recv(timeout=0.1)
                except TimeoutError:
                    continue
                request = remote.decrypt(scheme, payload)
                if request.get("type") == "options":
                    websocket.send(remote.encrypt(scheme, {"type": "options", "data": {"sources": ["fake"]}}))
                else:
                    websocket.send(remote.encrypt(scheme, {"type": "remote_error", "data": {"message": "unsupported"}}))

        with serve(handler, self.host, self.port):
            while not self._stop.is_set():
                time.sleep(0.05)


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_remote_options_round_trip() -> None:
    app = QApplication.instance() or QApplication(["pytest", "--no-effects"])
    _ = app
    fake_server = FakeOptionsServer()
    endpoint = fake_server.start()

    client = RecordingRemoteInference(endpoint=endpoint)
    try:
        client.start()
        assert _wait_for(lambda: any(msg.get("type") == "options" for msg in client.recorded))
        assert any(msg.get("type") == "status" and msg.get("data", {}).get("message") == "Connected" for msg in client.recorded)
    finally:
        client.stop()
        client.wait(3000)
        fake_server.stop()


def test_remote_connect_error_is_reported() -> None:
    app = QApplication.instance() or QApplication(["pytest", "--no-effects"])
    _ = app

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        endpoint = f"ws://127.0.0.1:{sock.getsockname()[1]}"

    client = RecordingRemoteInference(endpoint=endpoint)
    try:
        client.start()
        assert _wait_for(lambda: any(msg.get("type") == "remote_error" for msg in client.recorded))
    finally:
        client.stop()
        client.wait(3000)
