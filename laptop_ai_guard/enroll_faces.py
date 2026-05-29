from __future__ import annotations

import argparse
import os
import re
import time
from pathlib import Path

import numpy as np
from PIL import Image

from face_engine import CameraFrame, CavaFaceRecognizer, FaceDatabase, MobileFaceNetRecognizer


DEFAULT_CAVAFACE_DATABASE = Path(__file__).resolve().parent / "known_faces" / "embeddings.npz"
DEFAULT_MOBILEFACENET_DATABASE = Path(__file__).resolve().parent / "known_faces_mobilefacenet" / "embeddings.npz"
DEFAULT_CAPTURE_DIR = Path(__file__).resolve().parent / "captures"


def default_database_for_model(model_name: str) -> Path:
    if model_name == "mobilefacenet":
        return DEFAULT_MOBILEFACENET_DATABASE
    return DEFAULT_CAVAFACE_DATABASE


def clean_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    if not cleaned:
        raise ValueError("Name must contain at least one letter or number")
    return cleaned[:48]


def capture_samples(
    camera_index: int,
    samples: int,
    output_dir: Path,
    name: str,
    camera_source: str,
    opencv_backend: str,
    browser_host: str,
    browser_port: int,
    no_open_browser: bool,
    browser_timeout: float,
) -> list[Path]:
    from run_guard import BrowserCameraBridge, open_camera

    output_dir.mkdir(parents=True, exist_ok=True)
    if camera_source == "browser":
        cap = BrowserCameraBridge(
            host=browser_host,
            port=browser_port,
            open_browser=not no_open_browser,
            browser_app="",
            first_frame_timeout_s=browser_timeout,
            capture_dir=output_dir,
            demo_title="Known Face Enrollment",
            demo_subtitle="Capture face samples for the local demo database",
        ).start()
    else:
        cap = open_camera(camera_index, opencv_backend)

    paths: list[Path] = []
    try:
        for _ in range(10):
            cap.read()
            time.sleep(0.05)

        print("Look at the camera. Capturing samples...")
        for index in range(samples):
            time.sleep(0.45)
            ok, frame = cap.read()
            if not ok or frame is None:
                print(f"Skipping sample {index + 1}: camera frame failed")
                continue

            path = output_dir / f"enroll_{name}_{int(time.time())}_{index + 1:02d}.jpg"
            if isinstance(frame, CameraFrame):
                image_rgb = frame.image_rgb
            else:
                image_rgb = np.asarray(frame, dtype=np.uint8)
            Image.fromarray(image_rgb, mode="RGB").save(path, quality=90)
            paths.append(path)
            print(f"Captured {path}")
    finally:
        cap.release()

    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enroll known users for Arduino Q Face Guard.")
    parser.add_argument("--name", required=True, help="Known user's display name.")
    parser.add_argument("--image", action="append", default=[], help="Image path. Can be repeated.")
    parser.add_argument("--camera", action="store_true", help="Capture enrollment images from webcam.")
    parser.add_argument(
        "--camera-source",
        choices=("opencv", "browser"),
        default="browser",
        help="Use OpenCV directly, or a browser tab that posts webcam frames to localhost.",
    )
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument(
        "--opencv-backend",
        choices=("auto", "default", "dshow", "msmf"),
        default="auto",
        help="OpenCV capture backend when --camera-source opencv is used.",
    )
    parser.add_argument("--browser-host", default="127.0.0.1", help="Browser camera bridge host.")
    parser.add_argument("--browser-port", type=int, default=8766, help="Browser camera bridge port.")
    parser.add_argument("--browser-timeout", type=float, default=60.0, help="Seconds to wait for browser frames.")
    parser.add_argument("--no-open-browser", action="store_true", help="Print the browser camera URL without opening it.")
    parser.add_argument("--samples", type=int, default=8, help="Number of webcam samples to capture.")
    parser.add_argument(
        "--recognition-model",
        choices=("mobilefacenet", "cavaface"),
        default=os.environ.get("FACE_RECOGNITION_MODEL", "mobilefacenet").lower(),
        help="Face embedding model to use.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Embedding database path. Defaults to a model-specific database.",
    )
    parser.add_argument("--captures-dir", type=Path, default=DEFAULT_CAPTURE_DIR, help="Where webcam samples are saved.")
    parser.add_argument("--flip", action="store_true", help="Use CavaFace flip ensemble for embeddings. Ignored by MobileFaceNet.")
    parser.add_argument(
        "--face-detector",
        choices=("auto", "metadata", "mediapipe", "opencv", "center"),
        default="auto",
        help="Face crop source. auto uses MediaPipe if its model is present, then browser metadata/OpenCV/center.",
    )
    model_path_default = (
        os.environ.get("FACE_MODEL_PATH")
        or os.environ.get("MOBILEFACENET_MODEL_PATH")
        or os.environ.get("CAVAFACE_MODEL_PATH")
    )
    parser.add_argument(
        "--model-runtime",
        choices=("auto", "qaihub", "onnx-qnn", "onnx-cpu"),
        default="auto",
        help="Model runtime. Use onnx-qnn with local ONNX models for the X Elite NPU.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path(model_path_default) if model_path_default else None,
        help="Path to the selected recognizer .onnx file or QNN ONNX folder.",
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
    parser.add_argument("--qnn-allow-cpu-fallback", action="store_true", help="Allow CPU fallback for legacy QNN EP sessions.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    name = clean_name(args.name)
    if args.database is None:
        args.database = default_database_for_model(args.recognition_model)

    image_paths = [Path(path) for path in args.image]
    if args.camera:
        image_paths.extend(
            capture_samples(
                args.camera_index,
                args.samples,
                args.captures_dir,
                name,
                args.camera_source,
                args.opencv_backend,
                args.browser_host,
                args.browser_port,
                args.no_open_browser,
                args.browser_timeout,
            )
        )

    if not image_paths:
        raise SystemExit("Provide at least one --image or use --camera.")

    common = dict(
        face_detector=args.face_detector,
        model_runtime=args.model_runtime,
        model_path=args.model_path,
        detector_model_path=args.detector_model_path,
        qnn_backend=args.qnn_backend,
        qnn_performance_mode=args.qnn_performance_mode,
        qnn_profile_path=args.qnn_profile_path,
        qnn_allow_cpu_fallback=args.qnn_allow_cpu_fallback,
    )
    if args.recognition_model == "mobilefacenet":
        recognizer = MobileFaceNetRecognizer(**common)
    else:
        recognizer = CavaFaceRecognizer(use_flip=args.flip, **common)
    embeddings = []
    for path in image_paths:
        try:
            embeddings.append(recognizer.embedding_from_image_path(path))
            print(f"Enrolled embedding from {path}")
        except Exception as exc:
            print(f"Skipping {path}: {exc}")

    if not embeddings:
        raise SystemExit("No usable face embeddings were created.")

    database = FaceDatabase.load(args.database)
    added = database.add_many(name, embeddings)
    database.save(args.database)
    print(f"Saved {added} embedding(s) for {name} to {args.database}")


if __name__ == "__main__":
    main()
