from __future__ import annotations

import argparse
import base64
import io
import json
import os
import platform
import re
import socket
import struct
import sys
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
import webbrowser

import numpy as np
import serial
from serial.tools import list_ports
from PIL import Image

from face_engine import CameraFrame, CavaFaceRecognizer, FaceDatabase


DEFAULT_DATABASE = Path(__file__).resolve().parent / "known_faces" / "embeddings.npz"
DEFAULT_CAPTURE_DIR = Path(__file__).resolve().parent / "captures"
DATABASE_LOCK = threading.Lock()


def default_adb_path() -> Path:
    if platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        candidates = []
        if local_app_data:
            candidates.append(
                Path(local_app_data)
                / "Arduino15"
                / "packages"
                / "arduino"
                / "tools"
                / "adb"
                / "32.0.0"
                / "adb.exe"
            )
        candidates.append(
            Path.home()
            / "AppData"
            / "Local"
            / "Arduino15"
            / "packages"
            / "arduino"
            / "tools"
            / "adb"
            / "32.0.0"
            / "adb.exe"
        )
        for candidate in candidates:
            try:
                if candidate.exists():
                    return candidate
            except OSError:
                continue
        return Path("adb.exe")
    return Path.home() / "Library/Arduino15/packages/arduino/tools/adb/32.0.0/adb"


def default_camera_source() -> str:
    if platform.system() == "Windows" and platform.machine().upper() in {"ARM64", "AARCH64"}:
        return "browser"
    return "opencv"


def default_browser_app() -> str:
    return "Google Chrome" if platform.system() == "Darwin" else ""


DEFAULT_ADB = default_adb_path()
DEMO_DASHBOARD_PAGE = Path(__file__).resolve().parent / "demo_dashboard.html"


def load_demo_dashboard_page() -> str:
    try:
        return DEMO_DASHBOARD_PAGE.read_text(encoding="utf-8")
    except OSError:
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Face Guard Demo</title>
</head>
<body>
  <video id="video" autoplay playsinline muted style="width:100%;max-width:960px"></video>
  <p id="camera-status">Starting camera...</p>
  <canvas id="canvas" hidden></canvas>
  <script>
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const statusEl = document.getElementById("camera-status");
    async function start() {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      video.srcObject = stream;
      await video.play();
      canvas.width = video.videoWidth || 1280;
      canvas.height = video.videoHeight || 720;
      setInterval(async () => {
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        await fetch("/frame", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ image: canvas.toDataURL("image/jpeg", 0.82), face: null })
        });
        statusEl.textContent = "Camera connected.";
      }, 250);
    }
    start().catch((err) => { statusEl.textContent = `Camera failed: ${err}`; });
  </script>
</body>
</html>"""


def parse_browser_face_box(value: object) -> tuple[int, int, int, int] | None:
    if not isinstance(value, dict):
        return None

    try:
        x = int(round(float(value["x"])))
        y = int(round(float(value["y"])))
        width = int(round(float(value["width"])))
        height = int(round(float(value["height"])))
    except (KeyError, TypeError, ValueError):
        return None

    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def known_face_summary(database: FaceDatabase) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for name in database.names:
        counts[name] = counts.get(name, 0) + 1
    return [{"name": name, "samples": counts[name]} for name in sorted(counts)]


class BrowserCameraBridge:
    def __init__(
        self,
        host: str,
        port: int,
        open_browser: bool,
        browser_app: str,
        first_frame_timeout_s: float,
        capture_dir: Path,
        demo_title: str,
        demo_subtitle: str,
        database_path: Path | None = None,
        recognizer: CavaFaceRecognizer | None = None,
        database: FaceDatabase | None = None,
    ):
        self.host = host
        self.port = port
        self.open_browser = open_browser
        self.browser_app = browser_app
        self.first_frame_timeout_s = first_frame_timeout_s
        self.capture_dir = Path(capture_dir)
        self.database_path = Path(database_path) if database_path is not None else None
        self.recognizer = recognizer
        self.database = database
        self._frame = None
        self._frame_time = 0.0
        self._frame_count = 0
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._demo_state = {
            "title": demo_title,
            "subtitle": demo_subtitle,
            "mode": "Starting demo dashboard",
            "camera": {
                "connected": False,
                "frames": 0,
                "face_hint": "waiting",
            },
            "hardware": {
                "source": "Arduino UNO Q RouterBridge",
                "distance_ok": False,
                "buzzer_ok": False,
                "threshold_mm": None,
                "distance_mm": None,
                "near": False,
            },
            "ai": {
                "runtime": "CavaFace runs locally on the laptop.",
                "known_faces": [],
            },
            "result": {
                "state": "idle",
                "title": "Waiting",
                "message": "Bring a hand near the distance sensor to start a face check.",
                "detail": "The next close-distance event will run face recognition.",
                "name": None,
                "score": None,
                "threshold": None,
                "capture_url": None,
                "buzzer": "idle",
            },
            "events": [],
        }

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def configure_demo(self, runtime_description: str, known_names: list[str], threshold: float) -> None:
        self.update_demo(
            mode="Ready for store demo",
            ai={
                "runtime": self._friendly_runtime_description(runtime_description),
                "known_faces": sorted(set(known_names)),
                "known_face_summary": known_face_summary(self.database) if self.database is not None else [],
            },
            result={
                "threshold": threshold,
            },
        )
        self.add_demo_event("Demo ready", "Camera, AI model, Arduino, and known-face database are being monitored.")

    def update_demo(self, **sections: dict[str, object]) -> None:
        with self._lock:
            for key, value in sections.items():
                if isinstance(value, dict) and isinstance(self._demo_state.get(key), dict):
                    self._demo_state[key].update(value)
                else:
                    self._demo_state[key] = value

    def add_demo_event(self, title: str, message: str) -> None:
        event = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "title": title,
            "message": message,
        }
        with self._lock:
            self._demo_state["events"].insert(0, event)
            del self._demo_state["events"][8:]

    def demo_snapshot(self) -> dict[str, object]:
        with self._lock:
            return json.loads(json.dumps(self._demo_state))

    def known_faces_snapshot(self) -> dict[str, object]:
        if self.database is None:
            return {"ok": False, "error": "Known-face database is not attached to the dashboard."}
        with DATABASE_LOCK:
            summary = known_face_summary(self.database)
            total = int(self.database.embeddings.shape[0]) if self.database.embeddings is not None else 0
        return {
            "ok": True,
            "database": str(self.database_path) if self.database_path else "",
            "total_embeddings": total,
            "people": summary,
        }

    def capture_url(self, capture_path: Path | None) -> str | None:
        if capture_path is None:
            return None
        return f"/capture/{Path(capture_path).name}"

    def enroll_known_face(self, name: str, samples: int) -> dict[str, object]:
        if self.recognizer is None or self.database is None or self.database_path is None:
            return {"ok": False, "error": "Enrollment is not available until the model and database are loaded."}

        clean_name = " ".join(str(name).strip().split())
        if not clean_name:
            return {"ok": False, "error": "Enter a name before adding a known face."}
        if len(clean_name) > 48:
            return {"ok": False, "error": "Use a shorter display name."}

        target = max(1, min(int(samples or 6), 12))
        embeddings: list[np.ndarray] = []
        saved_frame = None
        seen_frame_count = -1
        deadline = time.time() + max(8.0, target * 2.2)
        self.update_demo(mode=f"Adding {clean_name}", result={"state": "checking", "title": "Adding known face", "message": f"Collecting {target} face samples for {clean_name}.", "detail": "Ask the person to face the camera and stay still for a moment.", "name": clean_name, "score": None, "capture_url": None, "buzzer": "idle"})
        self.add_demo_event("Enrollment started", f"Collecting samples for {clean_name}.")

        while len(embeddings) < target and time.time() < deadline:
            with self._lock:
                frame = self._frame.copy() if self._frame is not None else None
                frame_count = self._frame_count

            if frame is None or frame_count == seen_frame_count:
                time.sleep(0.15)
                continue
            seen_frame_count = frame_count

            try:
                embedding = self.recognizer.embedding_from_frame(frame)
            except Exception:
                time.sleep(0.18)
                continue

            embeddings.append(embedding)
            saved_frame = frame
            self.update_demo(result={"message": f"Collected {len(embeddings)} of {target} samples for {clean_name}."})
            time.sleep(0.22)

        if not embeddings:
            self.update_demo(mode="Enrollment needs another try", result={"state": "error", "title": "No face captured", "message": "No usable face sample was captured. Ask the person to face the camera and try again.", "detail": "The known-face database was not changed.", "name": clean_name, "score": None, "capture_url": None, "buzzer": "idle"})
            self.add_demo_event("Enrollment failed", f"No usable face sample was captured for {clean_name}.")
            return {"ok": False, "error": "No usable face sample was captured. Face the camera and try again."}

        with DATABASE_LOCK:
            added = self.database.add_many(clean_name, embeddings)
            self.database.save(self.database_path)
            people = known_face_summary(self.database)
            names = sorted(set(self.database.names))
            total = int(self.database.embeddings.shape[0])

        capture_path = save_capture(saved_frame, self.capture_dir, f"enrolled_{safe_serial_name(clean_name)}") if saved_frame is not None else None
        self.update_demo(
            mode="Known face added",
            ai={"known_faces": names, "known_face_summary": people},
            result={
                "state": "known",
                "title": "Known face added",
                "message": f"{clean_name} is now in the local known-face database.",
                "detail": f"Added {added} face sample{'s' if added != 1 else ''}.",
                "name": clean_name,
                "score": None,
                "capture_url": self.capture_url(capture_path),
                "buzzer": "quiet",
            },
        )
        self.add_demo_event("Known face added", f"{clean_name} added with {added} sample{'s' if added != 1 else ''}.")
        return {
            "ok": True,
            "name": clean_name,
            "added": added,
            "total_embeddings": total,
            "people": people,
            "capture_url": self.capture_url(capture_path),
        }

    @staticmethod
    def _friendly_runtime_description(description: str) -> str:
        if "QNNExecutionProvider" in description:
            return "CavaFace and MediaPipe run locally through ONNX Runtime QNN on the laptop NPU."
        return description or "CavaFace runs locally on the laptop."

    def start(self) -> "BrowserCameraBridge":
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:
                return

            def do_GET(self) -> None:
                path = urlparse(self.path).path

                if path == "/status":
                    message = json.dumps(bridge.demo_snapshot()).encode("utf-8")
                    self.send_response(200)
                    self.send_header("content-type", "application/json")
                    self.send_header("cache-control", "no-store")
                    self.send_header("content-length", str(len(message)))
                    self.end_headers()
                    self.wfile.write(message)
                    return

                if path == "/known-faces":
                    message = json.dumps(bridge.known_faces_snapshot()).encode("utf-8")
                    self.send_response(200)
                    self.send_header("content-type", "application/json")
                    self.send_header("cache-control", "no-store")
                    self.send_header("content-length", str(len(message)))
                    self.end_headers()
                    self.wfile.write(message)
                    return

                if path.startswith("/capture/"):
                    name = Path(unquote(path.removeprefix("/capture/"))).name
                    capture_path = bridge.capture_dir / name
                    if not capture_path.is_file():
                        self.send_error(404)
                        return
                    data = capture_path.read_bytes()
                    self.send_response(200)
                    self.send_header("content-type", "image/jpeg")
                    self.send_header("cache-control", "no-store")
                    self.send_header("content-length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return

                if path != "/":
                    self.send_error(404)
                    return

                page = load_demo_dashboard_page().encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
                print("Demo dashboard opened. Allow camera access and keep this tab open.", flush=True)

            def do_POST(self) -> None:
                path = urlparse(self.path).path
                if path == "/enroll":
                    length = int(self.headers.get("content-length", "0"))
                    payload = self.rfile.read(length)
                    try:
                        body = json.loads(payload or b"{}")
                        result = bridge.enroll_known_face(
                            name=str(body.get("name", "")),
                            samples=int(body.get("samples", 6)),
                        )
                        status = 200 if result.get("ok") else 400
                    except Exception as exc:
                        result = {"ok": False, "error": str(exc)}
                        status = 500

                    message = json.dumps(result).encode("utf-8")
                    self.send_response(status)
                    self.send_header("content-type", "application/json")
                    self.send_header("cache-control", "no-store")
                    self.send_header("content-length", str(len(message)))
                    self.end_headers()
                    self.wfile.write(message)
                    return

                if path != "/frame":
                    self.send_error(404)
                    return

                length = int(self.headers.get("content-length", "0"))
                payload = self.rfile.read(length)
                try:
                    body = json.loads(payload)
                    data_url = str(body["image"])
                    _, encoded = data_url.split(",", 1)
                    jpg = base64.b64decode(encoded)
                    image = Image.open(io.BytesIO(jpg)).convert("RGB")
                    frame = CameraFrame(np.asarray(image, dtype=np.uint8), parse_browser_face_box(body.get("face")))
                except Exception as exc:
                    message = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                    self.send_response(400)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(message)))
                    self.end_headers()
                    self.wfile.write(message)
                    return

                with bridge._lock:
                    bridge._frame = frame
                    bridge._frame_time = time.time()
                    bridge._frame_count += 1
                    frame_count = bridge._frame_count
                    bridge._demo_state["camera"].update(
                        {
                            "connected": True,
                            "frames": frame_count,
                            "face_hint": "browser face box" if frame.face_box else "python detector",
                        }
                    )
                    if bridge._demo_state["mode"] == "Starting demo dashboard":
                        bridge._demo_state["mode"] = "Camera connected"

                if frame_count == 1:
                    print("Browser camera frames are arriving.", flush=True)
                message = json.dumps({"ok": True, "frames": frame_count}).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(message)))
                self.end_headers()
                self.wfile.write(message)

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        print(f"Browser camera bridge: {self.url}")
        if self.open_browser:
            if self.browser_app and platform.system() == "Darwin":
                subprocess.run(["open", "-a", self.browser_app, self.url], check=False)
            else:
                webbrowser.open(self.url)

        deadline = time.time() + self.first_frame_timeout_s
        while time.time() < deadline:
            with self._lock:
                if self._frame is not None:
                    print("Browser camera connected.")
                    return self
            time.sleep(0.1)

        raise RuntimeError(
            f"No browser camera frames arrived. Open {self.url} in Chrome, allow camera access, "
            "and keep the tab open."
        )

    def read(self) -> tuple[bool, object]:
        with self._lock:
            if self._frame is None:
                return False, None
            return True, self._frame.copy()

    def release(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


class RouterBridgeClient:
    def __init__(self, adb_path: Path, timeout_s: float = 4.0):
        self.adb_path = Path(adb_path)
        self.timeout_s = timeout_s
        self.local_port = 17890
        self._forwarded = False
        self._msg_id = 0

    def call(self, method: str, *args: object) -> object:
        self._ensure_forward()
        self._msg_id += 1
        msg_id = self._msg_id
        request = self._pack([0, msg_id, method, list(args)])

        with socket.create_connection(("127.0.0.1", self.local_port), timeout=self.timeout_s) as sock:
            sock.settimeout(self.timeout_s)
            sock.sendall(request)
            deadline = time.time() + self.timeout_s
            buffer = b""
            while time.time() < deadline:
                try:
                    buffer += sock.recv(4096)
                except socket.timeout:
                    break

                if not buffer:
                    break

                try:
                    response, consumed = self._unpack(buffer)
                except EOFError:
                    continue

                if consumed != len(buffer):
                    buffer = buffer[consumed:]

                if (
                    not isinstance(response, list)
                    or len(response) != 4
                    or response[0] != 1
                    or response[1] != msg_id
                ):
                    raise RuntimeError(f"Unexpected RouterBridge response for {method}: {response!r}")

                error = response[2]
                if error is not None:
                    if isinstance(error, list) and len(error) >= 2:
                        raise RuntimeError(f"RouterBridge error {error[0]} for {method}: {error[1]}")
                    raise RuntimeError(f"RouterBridge error for {method}: {error!r}")
                return response[3]

        raise RuntimeError(f"RouterBridge timed out waiting for {method}")

    def call_value(self, method: str, *args: object) -> object:
        return self.call(method, *args)

    def call_int(self, method: str, *args: object) -> int:
        return int(self.call_value(method, *args))

    def call_bool(self, method: str, *args: object) -> bool:
        value = self.call_value(method, *args)
        if isinstance(value, bool):
            return value
        if str(value).lower() in {"true", "1"}:
            return True
        if str(value).lower() in {"false", "0"}:
            return False
        raise RuntimeError(f"Expected boolean response from {method}, got: {value}")

    def call_text(self, method: str, *args: object) -> str:
        return str(self.call_value(method, *args)).strip().strip('"')

    def _ensure_forward(self) -> None:
        if self._forwarded:
            return
        proc = subprocess.run(
            [
                str(self.adb_path),
                "forward",
                f"tcp:{self.local_port}",
                "localfilesystem:/var/run/arduino-router.sock",
            ],
            text=True,
            capture_output=True,
            timeout=self.timeout_s,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stdout + proc.stderr).strip() or "Failed to create adb router forward")
        self._forwarded = True

    @classmethod
    def _pack(cls, value: object) -> bytes:
        if value is None:
            return b"\xc0"
        if value is True:
            return b"\xc3"
        if value is False:
            return b"\xc2"
        if isinstance(value, int):
            if 0 <= value <= 0x7F:
                return bytes([value])
            if -32 <= value < 0:
                return bytes([0xE0 + value + 32])
            if -128 <= value <= 127:
                return b"\xd0" + value.to_bytes(1, "big", signed=True)
            if -32768 <= value <= 32767:
                return b"\xd1" + value.to_bytes(2, "big", signed=True)
            return b"\xd2" + value.to_bytes(4, "big", signed=True)
        if isinstance(value, float):
            return b"\xcb" + struct.pack(">d", value)
        if isinstance(value, str):
            data = value.encode("utf-8")
            if len(data) < 32:
                return bytes([0xA0 | len(data)]) + data
            if len(data) <= 0xFF:
                return b"\xd9" + bytes([len(data)]) + data
            return b"\xda" + len(data).to_bytes(2, "big") + data
        if isinstance(value, (list, tuple)):
            if len(value) < 16:
                prefix = bytes([0x90 | len(value)])
            else:
                prefix = b"\xdc" + len(value).to_bytes(2, "big")
            return prefix + b"".join(cls._pack(item) for item in value)
        raise TypeError(f"Unsupported RouterBridge argument: {value!r}")

    @classmethod
    def _unpack(cls, data: bytes, offset: int = 0) -> tuple[object, int]:
        if offset >= len(data):
            raise EOFError
        marker = data[offset]
        offset += 1

        def read(size: int) -> bytes:
            nonlocal offset
            if offset + size > len(data):
                raise EOFError
            chunk = data[offset : offset + size]
            offset += size
            return chunk

        if marker <= 0x7F:
            return marker, offset
        if marker >= 0xE0:
            return marker - 256, offset
        if 0x90 <= marker <= 0x9F:
            items = []
            for _ in range(marker & 0x0F):
                item, offset = cls._unpack(data, offset)
                items.append(item)
            return items, offset
        if 0xA0 <= marker <= 0xBF:
            return read(marker & 0x1F).decode("utf-8", errors="replace"), offset
        if marker == 0xC0:
            return None, offset
        if marker == 0xC2:
            return False, offset
        if marker == 0xC3:
            return True, offset
        if marker == 0xCC:
            return read(1)[0], offset
        if marker == 0xCD:
            return int.from_bytes(read(2), "big"), offset
        if marker == 0xCE:
            return int.from_bytes(read(4), "big"), offset
        if marker == 0xD0:
            return int.from_bytes(read(1), "big", signed=True), offset
        if marker == 0xD1:
            return int.from_bytes(read(2), "big", signed=True), offset
        if marker == 0xD2:
            return int.from_bytes(read(4), "big", signed=True), offset
        if marker == 0xCA:
            return struct.unpack(">f", read(4))[0], offset
        if marker == 0xCB:
            return struct.unpack(">d", read(8))[0], offset
        if marker == 0xD9:
            return read(read(1)[0]).decode("utf-8", errors="replace"), offset
        if marker == 0xDA:
            return read(int.from_bytes(read(2), "big")).decode("utf-8", errors="replace"), offset
        if marker == 0xDC:
            count = int.from_bytes(read(2), "big")
            items = []
            for _ in range(count):
                item, offset = cls._unpack(data, offset)
                items.append(item)
            return items, offset
        raise RuntimeError(f"Unsupported RouterBridge MessagePack marker 0x{marker:02x}")


def list_serial_ports() -> None:
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return

    for port in ports:
        print(f"{port.device}\t{port.description}\t{port.hwid}")


def choose_serial_port() -> str:
    ports = list(list_ports.comports())
    if not ports:
        raise RuntimeError("No serial ports found. Connect the Arduino over USB.")

    preferred_tokens = ("arduino", "uno", "usbmodem", "ttyacm", "wchusbserial", "usb serial")
    for port in ports:
        haystack = f"{port.device} {port.description} {port.hwid}".lower()
        if any(token in haystack for token in preferred_tokens):
            return port.device

    return ports[0].device


class OpenCVCamera:
    def __init__(self, camera_index: int, backend: str):
        try:
            import cv2  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError(
                "OpenCV is not available in this Python environment. "
                "On native Windows ARM64, use --camera-source browser."
            ) from exc

        self.cv2 = cv2
        self.cap = self._open(camera_index, backend)

        for _ in range(10):
            self.cap.read()
            time.sleep(0.05)

    def _open(self, camera_index: int, backend: str):
        candidates: list[int | None]
        if backend == "default":
            candidates = [None]
        elif backend == "dshow":
            candidates = [self.cv2.CAP_DSHOW]
        elif backend == "msmf":
            candidates = [self.cv2.CAP_MSMF]
        elif platform.system() == "Windows":
            candidates = [self.cv2.CAP_DSHOW, self.cv2.CAP_MSMF, None]
        else:
            candidates = [None]

        for candidate in candidates:
            cap = self.cv2.VideoCapture(camera_index) if candidate is None else self.cv2.VideoCapture(camera_index, candidate)
            if cap.isOpened():
                return cap
            cap.release()

        raise RuntimeError(f"Could not open camera index {camera_index}")

    def read(self) -> tuple[bool, CameraFrame | None]:
        ok, frame_bgr = self.cap.read()
        if not ok or frame_bgr is None:
            return False, None
        frame_rgb = self.cv2.cvtColor(frame_bgr, self.cv2.COLOR_BGR2RGB)
        return True, CameraFrame(frame_rgb)

    def release(self) -> None:
        self.cap.release()


def open_camera(camera_index: int, backend: str) -> OpenCVCamera:
    return OpenCVCamera(camera_index, backend)


def open_capture_source(args: argparse.Namespace, recognizer: CavaFaceRecognizer | None = None, database: FaceDatabase | None = None):
    if args.camera_source == "browser":
        bridge = BrowserCameraBridge(
            host=args.browser_host,
            port=args.browser_port,
            open_browser=not args.no_open_browser,
            browser_app=args.browser_app,
            first_frame_timeout_s=args.browser_timeout,
            capture_dir=args.captures_dir,
            demo_title=args.demo_title,
            demo_subtitle=args.demo_subtitle,
            database_path=args.database,
            recognizer=recognizer,
            database=database,
        )
        if recognizer is not None and database is not None:
            bridge.configure_demo(
                runtime_description=recognizer.runtime_description,
                known_names=list(database.names),
                threshold=args.threshold,
            )
        return bridge.start()

    return open_camera(args.camera_index, args.opencv_backend)


def capture_best_face_frame(
    cap,
    recognizer: CavaFaceRecognizer,
    attempts: int,
    delay_s: float,
) -> tuple[object, object]:
    best_frame = None
    best_face = None
    best_area = 0

    for _ in range(attempts):
        ok, frame = cap.read()
        if not ok or frame is None:
            time.sleep(delay_s)
            continue

        face = recognizer.detect_largest_face(frame)
        if face is not None:
            _, _, w, h = face.box
            area = w * h
            if area > best_area:
                best_frame = frame.copy()
                best_face = face
                best_area = area

        time.sleep(delay_s)

    if best_frame is None or best_face is None:
        raise ValueError("No face detected in webcam frames")

    return best_frame, best_face


def safe_serial_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return cleaned[:48] or "known"


def send_line(ser: serial.Serial, line: str) -> None:
    print(f"> {line}")
    ser.write((line + "\n").encode("utf-8"))
    ser.flush()


class SerialPollClient:
    def __init__(self, ser: serial.Serial, timeout_s: float = 2.0):
        self.ser = ser
        self.timeout_s = timeout_s

    def query(self, command: str, expected_prefix: str | None = None) -> str:
        self.ser.reset_input_buffer()
        send_line(self.ser, command)
        deadline = time.time() + self.timeout_s
        last_line = ""

        while time.time() < deadline:
            raw = self.ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            print(f"< {line}")
            last_line = line
            if expected_prefix is None or line == expected_prefix or line.startswith(expected_prefix):
                return line

        raise RuntimeError(f"No response for {command}; last line: {last_line or '<none>'}")

    def ping(self) -> bool:
        return self.query("PING", "PONG") == "PONG"

    def status(self) -> dict[str, int]:
        line = self.query("STATUS?", "STATUS,")
        values: dict[str, int] = {}
        for part in line.removeprefix("STATUS,").split(","):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            try:
                values[key.strip()] = int(value.strip())
            except ValueError:
                continue
        return values

    def set_threshold_mm(self, threshold_mm: int) -> int:
        line = self.query(f"SET_THRESHOLD_MM,{threshold_mm}", "THRESHOLD_MM,")
        return int(line.split(",", 1)[1])

    def read_distance_mm(self) -> int:
        line = self.query("READ_DISTANCE_MM", "DISTANCE,")
        return int(line.split(",", 1)[1])

    def buzz_unknown(self) -> str:
        return self.query("BUZZ_UNKNOWN")

    def buzz_fault(self) -> str:
        return self.query("BUZZ_FAULT")


def save_capture(frame, capture_dir: Path, label: str) -> Path:
    capture_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = capture_dir / f"{stamp}_{label}.jpg"
    if isinstance(frame, CameraFrame):
        image_rgb = frame.image_rgb
    else:
        image_rgb = np.asarray(frame, dtype=np.uint8)
    Image.fromarray(image_rgb, mode="RGB").save(path, quality=90)
    return path


def publish_demo(cap, **sections: dict[str, object]) -> None:
    update = getattr(cap, "update_demo", None)
    if callable(update):
        update(**sections)


def publish_demo_event(cap, title: str, message: str) -> None:
    add_event = getattr(cap, "add_demo_event", None)
    if callable(add_event):
        add_event(title, message)


def demo_capture_url(cap, capture_path: Path | None) -> str | None:
    capture_url = getattr(cap, "capture_url", None)
    if callable(capture_url):
        return capture_url(capture_path)
    return None


def recognize_face_event(
    cap,
    recognizer: CavaFaceRecognizer,
    database: FaceDatabase,
    threshold: float,
    capture_dir: Path,
    attempts: int,
    delay_s: float,
) -> tuple[bool, str, float, Path | None]:
    frame, _ = capture_best_face_frame(cap, recognizer, attempts, delay_s)
    embedding = recognizer.embedding_from_frame(frame)
    with DATABASE_LOCK:
        match = database.match(embedding, threshold=threshold)
    label = safe_serial_name(match.name if match.known else "unknown")
    capture_path = save_capture(frame, capture_dir, f"{label}_{match.score:.3f}")
    return match.known, match.name, match.score, capture_path


def handle_proximity(
    ser: serial.Serial,
    cap,
    recognizer: CavaFaceRecognizer,
    database: FaceDatabase,
    threshold: float,
    capture_dir: Path,
    attempts: int,
    delay_s: float,
) -> None:
    publish_demo(
        cap,
        mode="Running face check",
        result={
            "state": "checking",
            "title": "Checking face",
            "message": "Distance trigger received. The laptop is comparing the face now.",
            "detail": "CavaFace is running against the local known-face database.",
            "name": None,
            "score": None,
            "capture_url": None,
            "buzzer": "idle",
        },
    )
    publish_demo_event(cap, "Proximity trigger", "The board reported a close-distance event.")
    try:
        known, name, score, capture_path = recognize_face_event(
            cap, recognizer, database, threshold, capture_dir, attempts, delay_s
        )

        if known:
            print(f"Known face: {name} score={score:.3f} capture={capture_path}")
            publish_demo(
                cap,
                mode="Known face matched",
                result={
                    "state": "known",
                    "title": "Known face",
                    "message": "Face matched a person in the local database. The buzzer stays quiet.",
                    "detail": f"Matched {name} with score {score:.3f}.",
                    "name": name,
                    "score": score,
                    "threshold": threshold,
                    "capture_url": demo_capture_url(cap, capture_path),
                    "buzzer": "quiet",
                },
            )
            publish_demo_event(cap, "Known face", f"{name} matched with score {score:.3f}. Buzzer stayed quiet.")
            send_line(ser, f"KNOWN,{safe_serial_name(name)},{score:.3f}")
        else:
            print(f"Unknown face: best={name} score={score:.3f} capture={capture_path}")
            publish_demo(
                cap,
                mode="Unknown face alert",
                result={
                    "state": "unknown",
                    "title": "Unknown face",
                    "message": "No trusted match was found. The buzzer alert has been sent.",
                    "detail": f"Best candidate was {name} with score {score:.3f}.",
                    "name": "Unknown visitor",
                    "score": score,
                    "threshold": threshold,
                    "capture_url": demo_capture_url(cap, capture_path),
                    "buzzer": "buzzed",
                },
            )
            publish_demo_event(cap, "Unknown face", f"Score {score:.3f} was below threshold. Buzzer alert sent.")
            send_line(ser, f"UNKNOWN,{score:.3f}")
    except Exception as exc:
        print(f"Recognition failed: {exc}")
        publish_demo(
            cap,
            mode="Face check failed",
            result={
                "state": "error",
                "title": "Face check failed",
                "message": "The app could not complete the face check. The buzzer alert was sent as a fallback.",
                "detail": str(exc),
                "name": "Check failed",
                "score": None,
                "threshold": threshold,
                "capture_url": None,
                "buzzer": "buzzed",
            },
        )
        publish_demo_event(cap, "Face check failed", str(exc))
        send_line(ser, "UNKNOWN,0.000")


def run_routerbridge_guard(
    args: argparse.Namespace,
    cap,
    recognizer: CavaFaceRecognizer,
    database: FaceDatabase,
) -> None:
    client = RouterBridgeClient(args.adb_path, timeout_s=args.router_timeout)

    print("Checking UNO Q RouterBridge firmware...")
    for attempt in range(1, 21):
        try:
            ping = client.call_text("face_guard_ping")
            if ping == "pong":
                break
        except Exception as exc:
            if attempt == 20:
                raise RuntimeError(f"RouterBridge firmware did not answer: {exc}") from exc
            time.sleep(0.5)

    distance_ok = client.call_bool("distance_found")
    buzzer_ok = client.call_bool("buzzer_found")
    threshold_mm = client.call_int("threshold_mm")
    if args.proximity_threshold_mm is not None:
        threshold_mm = client.call_int("set_threshold_mm", args.proximity_threshold_mm)
    print(f"STATUS,distance_ok={int(distance_ok)},buzzer_ok={int(buzzer_ok)},threshold_mm={threshold_mm}")
    publish_demo(
        cap,
        mode="Waiting for customer",
        hardware={
            "source": "UNO Q RouterBridge over USB",
            "distance_ok": distance_ok,
            "buzzer_ok": buzzer_ok,
            "threshold_mm": threshold_mm,
            "near": False,
        },
    )
    publish_demo_event(cap, "Hardware ready", f"Distance sensor and buzzer status loaded. Trigger distance is {threshold_mm} mm.")
    if not distance_ok:
        raise RuntimeError("Modulino Distance was not found by the UNO Q firmware")
    if not buzzer_ok:
        print("Warning: Modulino Buzzer was not found; unknown faces cannot sound the alarm.")

    armed = True
    person_present = False
    last_trigger_at = 0.0
    last_reported_distance = None
    print("Polling Distance Modulino through RouterBridge. Press Ctrl+C to stop.")

    try:
        while True:
            distance_mm = client.call_int("read_distance_mm")
            now = time.time()

            if distance_mm > 0 and distance_mm != last_reported_distance:
                print(f"DISTANCE,{distance_mm}")
                last_reported_distance = distance_mm

            is_close = distance_mm > 0 and distance_mm <= threshold_mm
            publish_demo(
                cap,
                mode="Customer detected" if is_close else "Waiting for customer",
                hardware={
                    "distance_mm": distance_mm if distance_mm > 0 else None,
                    "threshold_mm": threshold_mm,
                    "near": is_close,
                },
            )

            if distance_mm <= 0 or distance_mm > threshold_mm + args.exit_hysteresis:
                person_present = False

            in_cooldown = (now - last_trigger_at) < args.trigger_cooldown

            if armed and is_close and (not person_present or not in_cooldown):
                person_present = True
                last_trigger_at = now
                print(f"PROXIMITY,{distance_mm}")
                publish_demo(
                    cap,
                    mode="Running face check",
                    result={
                        "state": "checking",
                        "title": "Checking face",
                        "message": "Distance trigger received. The laptop is comparing the face now.",
                        "detail": "CavaFace is running against the local known-face database.",
                        "name": None,
                        "score": None,
                        "capture_url": None,
                        "buzzer": "idle",
                    },
                )
                publish_demo_event(cap, "Proximity trigger", f"Distance sensor reported {distance_mm} mm.")

                try:
                    known, name, score, capture_path = recognize_face_event(
                        cap,
                        recognizer,
                        database,
                        threshold=args.threshold,
                        capture_dir=args.captures_dir,
                        attempts=args.attempts,
                        delay_s=args.delay,
                    )
                    if known:
                        print(f"KNOWN,{safe_serial_name(name)},{score:.3f},capture={capture_path}")
                        publish_demo(
                            cap,
                            mode="Known face matched",
                            result={
                                "state": "known",
                                "title": "Known face",
                                "message": "Face matched a person in the local database. The buzzer stays quiet.",
                                "detail": f"Matched {name} with score {score:.3f}.",
                                "name": name,
                                "score": score,
                                "threshold": args.threshold,
                                "capture_url": demo_capture_url(cap, capture_path),
                                "buzzer": "quiet",
                            },
                        )
                        publish_demo_event(cap, "Known face", f"{name} matched with score {score:.3f}. Buzzer stayed quiet.")
                    else:
                        print(f"UNKNOWN,{score:.3f},capture={capture_path}")
                        if buzzer_ok:
                            client.call_text("buzz_unknown")
                        publish_demo(
                            cap,
                            mode="Unknown face alert",
                            result={
                                "state": "unknown",
                                "title": "Unknown face",
                                "message": (
                                    "No trusted match was found. The buzzer alert has been sent."
                                    if buzzer_ok
                                    else "No trusted match was found. The buzzer is not available on this setup."
                                ),
                                "detail": f"Best candidate was {name} with score {score:.3f}.",
                                "name": "Unknown visitor",
                                "score": score,
                                "threshold": args.threshold,
                                "capture_url": demo_capture_url(cap, capture_path),
                                "buzzer": "buzzed" if buzzer_ok else "idle",
                            },
                        )
                        publish_demo_event(
                            cap,
                            "Unknown face",
                            (
                                f"Score {score:.3f} was below threshold. Buzzer alert sent."
                                if buzzer_ok
                                else f"Score {score:.3f} was below threshold. Buzzer unavailable."
                            ),
                        )
                except Exception as exc:
                    print(f"Recognition failed: {exc}")
                    if buzzer_ok:
                        client.call_text("buzz_unknown")
                    publish_demo(
                        cap,
                        mode="Face check failed",
                        result={
                            "state": "error",
                            "title": "Face check failed",
                            "message": (
                                "The app could not complete the face check. The buzzer alert was sent as a fallback."
                                if buzzer_ok
                                else "The app could not complete the face check. The buzzer is not available on this setup."
                            ),
                            "detail": str(exc),
                            "name": "Check failed",
                            "score": None,
                            "threshold": args.threshold,
                            "capture_url": None,
                            "buzzer": "buzzed" if buzzer_ok else "idle",
                        },
                    )
                    publish_demo_event(cap, "Face check failed", str(exc))

            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nStopping.")


def run_serial_poll_guard(
    args: argparse.Namespace,
    cap,
    recognizer: CavaFaceRecognizer,
    database: FaceDatabase,
    ser: serial.Serial,
) -> None:
    client = SerialPollClient(ser, timeout_s=args.serial_timeout)

    print("Checking UNO Q serial firmware...")
    for attempt in range(1, 16):
        try:
            if client.ping():
                break
        except Exception as exc:
            if attempt == 15:
                raise RuntimeError(f"Serial firmware did not answer PING on {ser.port}: {exc}") from exc
            time.sleep(0.5)

    status = client.status()
    distance_ok = bool(status.get("distance_ok", 0))
    buzzer_ok = bool(status.get("buzzer_ok", 0))
    threshold_mm = status.get("threshold_mm", args.proximity_threshold_mm or 700)
    if args.proximity_threshold_mm is not None:
        threshold_mm = client.set_threshold_mm(args.proximity_threshold_mm)

    print(f"STATUS,distance_ok={int(distance_ok)},buzzer_ok={int(buzzer_ok)},threshold_mm={threshold_mm}")
    publish_demo(
        cap,
        mode="Waiting for customer",
        hardware={
            "source": f"Serial polling on {ser.port}",
            "distance_ok": distance_ok,
            "buzzer_ok": buzzer_ok,
            "threshold_mm": threshold_mm,
            "near": False,
        },
    )
    publish_demo_event(cap, "Hardware ready", f"Distance sensor and buzzer status loaded. Trigger distance is {threshold_mm} mm.")
    if not distance_ok:
        raise RuntimeError("Modulino Distance was not found by the UNO Q firmware")
    if not buzzer_ok:
        print("Warning: Modulino Buzzer was not found; unknown faces cannot sound the alarm.")

    person_present = False
    last_trigger_at = 0.0
    last_reported_distance = None
    print("Polling Distance Modulino through serial. Press Ctrl+C to stop.")

    try:
        while True:
            distance_mm = client.read_distance_mm()
            now = time.time()

            if distance_mm > 0 and distance_mm != last_reported_distance:
                print(f"DISTANCE,{distance_mm}")
                last_reported_distance = distance_mm

            is_close = distance_mm > 0 and distance_mm <= threshold_mm
            publish_demo(
                cap,
                mode="Customer detected" if is_close else "Waiting for customer",
                hardware={
                    "distance_mm": distance_mm if distance_mm > 0 else None,
                    "threshold_mm": threshold_mm,
                    "near": is_close,
                },
            )

            if distance_mm <= 0 or distance_mm > threshold_mm + args.exit_hysteresis:
                person_present = False

            in_cooldown = (now - last_trigger_at) < args.trigger_cooldown

            if is_close and (not person_present or not in_cooldown):
                person_present = True
                last_trigger_at = now
                print(f"PROXIMITY,{distance_mm}")
                publish_demo(
                    cap,
                    mode="Running face check",
                    result={
                        "state": "checking",
                        "title": "Checking face",
                        "message": "Distance trigger received. The laptop is comparing the face now.",
                        "detail": "CavaFace is running against the local known-face database.",
                        "name": None,
                        "score": None,
                        "capture_url": None,
                        "buzzer": "idle",
                    },
                )
                publish_demo_event(cap, "Proximity trigger", f"Distance sensor reported {distance_mm} mm.")

                try:
                    known, name, score, capture_path = recognize_face_event(
                        cap,
                        recognizer,
                        database,
                        threshold=args.threshold,
                        capture_dir=args.captures_dir,
                        attempts=args.attempts,
                        delay_s=args.delay,
                    )
                    if known:
                        print(f"KNOWN,{safe_serial_name(name)},{score:.3f},capture={capture_path}")
                        publish_demo(
                            cap,
                            mode="Known face matched",
                            result={
                                "state": "known",
                                "title": "Known face",
                                "message": "Face matched a person in the local database. The buzzer stays quiet.",
                                "detail": f"Matched {name} with score {score:.3f}.",
                                "name": name,
                                "score": score,
                                "threshold": args.threshold,
                                "capture_url": demo_capture_url(cap, capture_path),
                                "buzzer": "quiet",
                            },
                        )
                        publish_demo_event(cap, "Known face", f"{name} matched with score {score:.3f}. Buzzer stayed quiet.")
                    else:
                        print(f"UNKNOWN,{score:.3f},capture={capture_path}")
                        if buzzer_ok:
                            client.buzz_unknown()
                        publish_demo(
                            cap,
                            mode="Unknown face alert",
                            result={
                                "state": "unknown",
                                "title": "Unknown face",
                                "message": (
                                    "No trusted match was found. The buzzer alert has been sent."
                                    if buzzer_ok
                                    else "No trusted match was found. The buzzer is not available on this setup."
                                ),
                                "detail": f"Best candidate was {name} with score {score:.3f}.",
                                "name": "Unknown visitor",
                                "score": score,
                                "threshold": args.threshold,
                                "capture_url": demo_capture_url(cap, capture_path),
                                "buzzer": "buzzed" if buzzer_ok else "idle",
                            },
                        )
                        publish_demo_event(
                            cap,
                            "Unknown face",
                            (
                                f"Score {score:.3f} was below threshold. Buzzer alert sent."
                                if buzzer_ok
                                else f"Score {score:.3f} was below threshold. Buzzer unavailable."
                            ),
                        )
                except Exception as exc:
                    print(f"Recognition failed: {exc}")
                    if buzzer_ok:
                        client.buzz_unknown()
                    publish_demo(
                        cap,
                        mode="Face check failed",
                        result={
                            "state": "error",
                            "title": "Face check failed",
                            "message": (
                                "The app could not complete the face check. The buzzer alert was sent as a fallback."
                                if buzzer_ok
                                else "The app could not complete the face check. The buzzer is not available on this setup."
                            ),
                            "detail": str(exc),
                            "name": "Check failed",
                            "score": None,
                            "threshold": args.threshold,
                            "capture_url": None,
                            "buzzer": "buzzed" if buzzer_ok else "idle",
                        },
                    )
                    publish_demo_event(cap, "Face check failed", str(exc))

            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nStopping.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Laptop AI bridge for Arduino Q Face Guard.")
    parser.add_argument("--port", default="auto", help="Arduino serial port, or 'auto'.")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate.")
    parser.add_argument(
        "--hardware-source",
        choices=("serial", "routerbridge"),
        default="routerbridge",
        help="Use plain serial firmware, or UNO Q RouterBridge RPC firmware.",
    )
    parser.add_argument(
        "--serial-protocol",
        choices=("poll", "events"),
        default="poll",
        help="Serial protocol. poll asks the board for distance; events listens for PROXIMITY lines.",
    )
    parser.add_argument("--serial-timeout", type=float, default=2.0, help="Seconds to wait for one serial reply.")
    parser.add_argument("--adb-path", type=Path, default=DEFAULT_ADB, help="Path to adb for UNO Q RouterBridge mode.")
    parser.add_argument("--router-timeout", type=float, default=4.0, help="Seconds to wait for one RouterBridge call.")
    parser.add_argument("--poll-interval", type=float, default=0.20, help="Seconds between Distance Modulino polls.")
    parser.add_argument("--trigger-cooldown", type=float, default=5.0, help="Seconds between proximity AI runs.")
    parser.add_argument(
        "--proximity-threshold-mm",
        type=int,
        default=None,
        help="Override the firmware proximity threshold in millimeters.",
    )
    parser.add_argument("--exit-hysteresis", type=int, default=150, help="Millimeters past threshold before re-arming.")
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument(
        "--opencv-backend",
        choices=("auto", "default", "dshow", "msmf"),
        default="auto",
        help="OpenCV capture backend when --camera-source opencv is used.",
    )
    parser.add_argument(
        "--camera-source",
        choices=("opencv", "browser"),
        default=default_camera_source(),
        help="Use OpenCV directly, or a browser tab that posts webcam frames to localhost.",
    )
    parser.add_argument("--browser-host", default="127.0.0.1", help="Browser camera bridge host.")
    parser.add_argument("--browser-port", type=int, default=8765, help="Browser camera bridge port.")
    parser.add_argument("--browser-app", default=default_browser_app(), help="macOS browser app to open for camera capture.")
    parser.add_argument("--browser-timeout", type=float, default=60.0, help="Seconds to wait for browser frames.")
    parser.add_argument("--no-open-browser", action="store_true", help="Print the browser camera URL without opening it.")
    parser.add_argument("--demo-title", default="Lenskart AI Guard Demo", help="Title shown on the browser demo dashboard.")
    parser.add_argument(
        "--demo-subtitle",
        default="Arduino UNO Q, laptop NPU, camera, distance sensor, buzzer",
        help="Subtitle shown on the browser demo dashboard.",
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help="Embedding database path.")
    parser.add_argument("--captures-dir", type=Path, default=DEFAULT_CAPTURE_DIR, help="Where captured frames are saved.")
    parser.add_argument("--threshold", type=float, default=0.50, help="Known-user cosine similarity threshold.")
    parser.add_argument("--attempts", type=int, default=10, help="Webcam frames to inspect after a proximity trigger.")
    parser.add_argument("--delay", type=float, default=0.12, help="Delay between frame attempts.")
    parser.add_argument("--flip", action="store_true", help="Use CavaFace flip ensemble for embeddings.")
    parser.add_argument(
        "--face-detector",
        choices=("auto", "metadata", "mediapipe", "opencv", "center"),
        default="auto",
        help="Face crop source. auto uses MediaPipe if its model is present, then browser metadata/OpenCV/center.",
    )
    model_path_default = os.environ.get("CAVAFACE_MODEL_PATH")
    parser.add_argument(
        "--model-runtime",
        choices=("auto", "qaihub", "onnx-qnn", "onnx-cpu"),
        default="auto",
        help="CavaFace runtime. Use onnx-qnn with an exported CavaFace ONNX model for the X Elite NPU.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path(model_path_default) if model_path_default else None,
        help="Path to a CavaFace .onnx file or precompiled QNN ONNX folder.",
    )
    detector_model_default = os.environ.get("FACE_DETECTOR_MODEL_PATH")
    parser.add_argument(
        "--detector-model-path",
        type=Path,
        default=Path(detector_model_default) if detector_model_default else None,
        help="Path to the MediaPipe face detector .onnx model.",
    )
    parser.add_argument("--qnn-backend", choices=("htp", "cpu"), default="htp", help="QNN backend; htp runs on the NPU.")
    parser.add_argument("--qnn-performance-mode", default="burst", help="QNN HTP performance mode.")
    parser.add_argument("--qnn-profile-path", type=Path, default=None, help="Optional QNN profiling CSV path.")
    parser.add_argument(
        "--qnn-allow-cpu-fallback",
        action="store_true",
        help="Allow CPU fallback for legacy QNN EP sessions. Off by default so NPU setup errors stay visible.",
    )
    parser.add_argument("--list-ports", action="store_true", help="Print serial ports and exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_ports:
        list_serial_ports()
        return

    port = choose_serial_port() if args.hardware_source == "serial" and args.port == "auto" else args.port
    database = FaceDatabase.load(args.database)
    if database.embeddings.size == 0:
        print(f"Warning: no known embeddings found at {args.database}; every face will be unknown.")
    else:
        print(f"Loaded {len(database.names)} known embedding(s) from {args.database}")

    print("Loading CavaFace model...")
    recognizer = CavaFaceRecognizer(
        use_flip=args.flip,
        face_detector=args.face_detector,
        model_runtime=args.model_runtime,
        model_path=args.model_path,
        detector_model_path=args.detector_model_path,
        qnn_backend=args.qnn_backend,
        qnn_performance_mode=args.qnn_performance_mode,
        qnn_profile_path=args.qnn_profile_path,
        qnn_allow_cpu_fallback=args.qnn_allow_cpu_fallback,
    )
    print(f"CavaFace runtime: {recognizer.runtime_description}")
    print("Opening camera source...")
    cap = open_capture_source(args, recognizer=recognizer, database=database)

    if args.hardware_source == "routerbridge":
        try:
            run_routerbridge_guard(args, cap, recognizer, database)
        finally:
            cap.release()
        return

    print(f"Opening Arduino serial port {port} at {args.baud} baud...")
    with serial.Serial(port, args.baud, timeout=args.serial_timeout) as ser:
        time.sleep(2.0)
        ser.reset_input_buffer()

        if args.serial_protocol == "poll":
            try:
                run_serial_poll_guard(args, cap, recognizer, database, ser)
            finally:
                cap.release()
            return

        send_line(ser, "STATUS?")
        print("Listening for PROXIMITY events. Press Ctrl+C to stop.")

        try:
            while True:
                raw = ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                print(f"< {line}")
                if line.startswith("PROXIMITY,"):
                    handle_proximity(
                        ser,
                        cap,
                        recognizer,
                        database,
                        threshold=args.threshold,
                        capture_dir=args.captures_dir,
                        attempts=args.attempts,
                        delay_s=args.delay,
                    )
        except KeyboardInterrupt:
            print("\nStopping.")
        finally:
            cap.release()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        raise SystemExit(1)
