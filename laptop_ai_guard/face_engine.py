from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
from PIL import Image


FaceDetectorBackend = Literal["auto", "metadata", "mediapipe", "opencv", "center"]
RecognitionModel = Literal["cavaface", "mobilefacenet"]
ModelRuntime = Literal["auto", "qaihub", "onnx-qnn", "onnx-cpu"]

MODELS_DIR = Path(__file__).resolve().parent / "models"
DEFAULT_CAVAFACE_MODEL = MODELS_DIR / "cavaface" / "cavaface.onnx"
DEFAULT_MOBILEFACENET_MODEL = MODELS_DIR / "mobilefacenet" / "mobilefacenet.onnx"
DEFAULT_MEDIAPIPE_MODEL = MODELS_DIR / "media_pipe" / "media_pipe.onnx"

MEDIAPIPE_INPUT_H = 256
MEDIAPIPE_INPUT_W = 256
CAVAFACE_INPUT_H = 112
CAVAFACE_INPUT_W = 112
MOBILEFACENET_INPUT_H = 112
MOBILEFACENET_INPUT_W = 112

_QNN_PLUGIN_REGISTERED = False


@dataclass(frozen=True)
class CameraFrame:
    image_rgb: np.ndarray
    face_box: tuple[int, int, int, int] | None = None

    def copy(self) -> "CameraFrame":
        return CameraFrame(self.image_rgb.copy(), self.face_box)


@dataclass(frozen=True)
class FaceCrop:
    image_rgb: np.ndarray
    box: tuple[int, int, int, int]


@dataclass(frozen=True)
class MatchResult:
    known: bool
    name: str
    score: float


def _normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    emb = np.asarray(embedding, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(emb))
    if norm <= 1e-9:
        raise ValueError("Face recognition model returned an empty embedding")
    return emb / norm


def _rgb_array_from_pil(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _frame_to_rgb_and_box(frame: object) -> tuple[np.ndarray, tuple[int, int, int, int] | None]:
    if isinstance(frame, CameraFrame):
        return np.asarray(frame.image_rgb, dtype=np.uint8), frame.face_box
    return np.asarray(frame, dtype=np.uint8), None


def _clip_box(
    box: tuple[int, int, int, int],
    width: int,
    height: int,
    margin: float,
) -> tuple[int, int, int, int] | None:
    x, y, w, h = box
    if w <= 0 or h <= 0:
        return None

    margin_x = int(w * margin)
    margin_y = int(h * margin)
    x0 = max(0, x - margin_x)
    y0 = max(0, y - margin_y)
    x1 = min(width, x + w + margin_x)
    y1 = min(height, y + h + margin_y)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1 - x0, y1 - y0


def _crop_from_box(
    image_rgb: np.ndarray,
    box: tuple[int, int, int, int],
    margin: float,
) -> FaceCrop | None:
    height, width = image_rgb.shape[:2]
    clipped = _clip_box(box, width, height, margin)
    if clipped is None:
        return None
    x, y, w, h = clipped
    return FaceCrop(image_rgb[y : y + h, x : x + w].copy(), clipped)


def _center_face_crop(image_rgb: np.ndarray) -> FaceCrop | None:
    if image_rgb is None or image_rgb.size == 0:
        return None

    height, width = image_rgb.shape[:2]
    crop_size = int(min(width, height) * 0.82)
    if crop_size <= 0:
        return None

    x = max(0, (width - crop_size) // 2)
    y = max(0, int((height - crop_size) * 0.42))
    return _crop_from_box(image_rgb, (x, y, crop_size, crop_size), margin=0.0)


def _find_onnx_model_path(model_path: str | Path) -> Path:
    path = Path(model_path)
    if path.is_file():
        return path
    if not path.exists():
        raise FileNotFoundError(f"ONNX model path does not exist: {path}")

    direct_matches = sorted(child for child in path.iterdir() if child.is_file() and child.suffix == ".onnx")
    if direct_matches:
        return direct_matches[0]

    recursive_matches = sorted(path.rglob("*.onnx"))
    if recursive_matches:
        return recursive_matches[0]

    raise FileNotFoundError(f"No .onnx file found under {path}")


def _local_default_runtime(model_path: str | Path | None) -> ModelRuntime:
    if model_path:
        if platform.system() == "Windows" and platform.machine().upper() in {"ARM64", "AARCH64"}:
            return "onnx-qnn"
        return "onnx-cpu"
    return "qaihub"


def _register_qnn_plugin_if_available(ort) -> object | None:
    global _QNN_PLUGIN_REGISTERED

    try:
        import onnxruntime_qnn as qnn_ep  # type: ignore[import-not-found]
    except Exception:
        return None

    required_apis = (
        hasattr(ort, "register_execution_provider_library")
        and hasattr(ort, "get_ep_devices")
        and hasattr(ort.SessionOptions(), "add_provider_for_devices")
    )
    if not required_apis:
        return None

    if not _QNN_PLUGIN_REGISTERED:
        try:
            ort.register_execution_provider_library("QNNExecutionProvider", qnn_ep.get_library_path())
        except Exception as exc:
            text = str(exc).lower()
            if "already" not in text and "registered" not in text:
                raise
        _QNN_PLUGIN_REGISTERED = True

    return qnn_ep


def _create_onnx_session(
    model_path: str | Path,
    runtime: Literal["onnx-qnn", "onnx-cpu"],
    qnn_backend: Literal["htp", "cpu"] = "htp",
    qnn_performance_mode: str = "burst",
    qnn_profile_path: str | Path | None = None,
    qnn_allow_cpu_fallback: bool = False,
) -> tuple[object, object | None]:
    import onnxruntime as ort  # type: ignore[import-not-found]

    resolved_model_path = str(_find_onnx_model_path(model_path))
    run_options = None

    if runtime == "onnx-cpu":
        return ort.InferenceSession(resolved_model_path, providers=["CPUExecutionProvider"]), run_options

    qnn_ep = _register_qnn_plugin_if_available(ort)
    if qnn_ep is not None:
        devices = [device for device in ort.get_ep_devices() if device.ep_name == "QNNExecutionProvider"]
        if not devices:
            raise RuntimeError("ONNX Runtime QNN plugin loaded, but no QNN EP devices were reported.")

        backend_path_fn_name = "get_qnn_htp_path" if qnn_backend == "htp" else "get_qnn_cpu_path"
        backend_path_fn = getattr(qnn_ep, backend_path_fn_name, None)
        if backend_path_fn is None:
            raise RuntimeError(f"onnxruntime-qnn does not expose {backend_path_fn_name}().")

        session_options = ort.SessionOptions()
        ep_options = {"backend_path": backend_path_fn()}
        if qnn_profile_path is not None:
            ep_options["profiling_level"] = "basic"
            ep_options["profiling_file_path"] = str(qnn_profile_path)
        session_options.add_provider_for_devices(devices, ep_options)

        run_options = ort.RunOptions()
        run_options.add_run_config_entry("qnn.perf_mode", qnn_performance_mode)
        return ort.InferenceSession(resolved_model_path, sess_options=session_options), run_options

    provider_options: dict[str, str] = {
        "backend_path": "QnnHtp.dll" if qnn_backend == "htp" else "QnnCpu.dll",
        "htp_performance_mode": qnn_performance_mode,
        "qnn_context_priority": "high",
        "htp_graph_finalization_optimization_mode": "3",
    }
    if qnn_profile_path is not None:
        provider_options["profiling_level"] = "basic"
        provider_options["profiling_file_path"] = str(qnn_profile_path)

    providers: list[str] = ["QNNExecutionProvider"]
    options: list[dict[str, str]] = [provider_options]
    if qnn_allow_cpu_fallback:
        providers.append("CPUExecutionProvider")
        options.append({})

    return (
        ort.InferenceSession(
            resolved_model_path,
            providers=providers,
            provider_options=options,
        ),
        run_options,
    )


def _infer_layout(shape: list[object]) -> Literal["NCHW", "NHWC"]:
    if len(shape) != 4:
        return "NCHW"
    if shape[1] == 3:
        return "NCHW"
    if shape[3] == 3:
        return "NHWC"
    return "NCHW"


def _resize_rgb_to_tensor_0_1(
    image_rgb: np.ndarray,
    input_height: int,
    input_width: int,
    layout: Literal["NCHW", "NHWC"],
) -> np.ndarray:
    image = Image.fromarray(np.asarray(image_rgb, dtype=np.uint8), mode="RGB")
    resized = image.resize((input_width, input_height), Image.Resampling.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 255.0
    if layout == "NHWC":
        return arr[np.newaxis, :, :, :]
    return np.transpose(arr, (2, 0, 1))[np.newaxis, :, :, :]


def _cavaface_rgb_to_tensor(
    image_rgb: np.ndarray,
    input_height: int,
    input_width: int,
    layout: Literal["NCHW", "NHWC"],
) -> np.ndarray:
    tensor = _resize_rgb_to_tensor_0_1(image_rgb, input_height, input_width, layout)
    return ((tensor - 0.5) / 0.5).astype(np.float32)


def _build_mediapipe_anchors() -> list[tuple[float, float]]:
    anchors: list[tuple[float, float]] = []
    for row in range(16):
        for col in range(16):
            cx = (col + 0.5) / 16.0
            cy = (row + 0.5) / 16.0
            anchors.append((cx, cy))
            anchors.append((cx, cy))

    for row in range(8):
        for col in range(8):
            cx = (col + 0.5) / 8.0
            cy = (row + 0.5) / 8.0
            for _ in range(6):
                anchors.append((cx, cy))
    return anchors


_MEDIAPIPE_ANCHORS = _build_mediapipe_anchors()


class FaceDatabase:
    def __init__(self, names: list[str] | None = None, embeddings: np.ndarray | None = None):
        self.names = names or []
        if embeddings is None:
            self.embeddings = np.empty((0, 0), dtype=np.float32)
        else:
            loaded = np.asarray(embeddings, dtype=np.float32)
            if loaded.ndim == 1:
                loaded = loaded[np.newaxis, :]
            self.embeddings = loaded

    @classmethod
    def load(cls, path: str | Path) -> "FaceDatabase":
        db_path = Path(path)
        if not db_path.exists():
            return cls()

        data = np.load(db_path, allow_pickle=False)
        names = [str(name) for name in data["names"].tolist()]
        embeddings = np.asarray(data["embeddings"], dtype=np.float32)
        if embeddings.ndim == 1:
            embeddings = embeddings[np.newaxis, :]
        if len(names) != int(embeddings.shape[0]):
            raise ValueError(f"Database names/embeddings length mismatch in {db_path}")
        return cls(names, embeddings)

    def save(self, path: str | Path) -> None:
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            db_path,
            names=np.asarray(self.names, dtype=str),
            embeddings=np.asarray(self.embeddings, dtype=np.float32),
        )

    def add_many(self, name: str, embeddings: Iterable[np.ndarray]) -> int:
        rows = [_normalize_embedding(embedding) for embedding in embeddings]
        if not rows:
            return 0

        new_embeddings = np.vstack(rows).astype(np.float32)
        if self.embeddings.size != 0 and self.embeddings.shape[1] != new_embeddings.shape[1]:
            raise ValueError(
                f"Embedding dimension mismatch: database has {self.embeddings.shape[1]} values, "
                f"new model produced {new_embeddings.shape[1]} values. Use a separate database path."
            )
        if self.embeddings.size == 0:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings]).astype(np.float32)
        self.names.extend([name] * len(rows))
        return len(rows)

    def match(self, embedding: np.ndarray, threshold: float = 0.50) -> MatchResult:
        if self.embeddings.size == 0:
            return MatchResult(False, "unknown", 0.0)

        query = _normalize_embedding(embedding)
        scores = self.embeddings @ query
        best_index = int(np.argmax(scores))
        best_score = float(scores[best_index])
        best_name = self.names[best_index]
        return MatchResult(best_score >= threshold, best_name, best_score)


class _MediaPipeFaceDetector:
    def __init__(
        self,
        model_path: str | Path,
        runtime: Literal["onnx-qnn", "onnx-cpu"],
        qnn_backend: Literal["htp", "cpu"],
        qnn_performance_mode: str,
        qnn_profile_path: str | Path | None,
        qnn_allow_cpu_fallback: bool,
        confidence_threshold: float = 0.50,
        nms_threshold: float = 0.30,
    ):
        self.model_path = _find_onnx_model_path(model_path)
        self.session, self.run_options = _create_onnx_session(
            self.model_path,
            runtime=runtime,
            qnn_backend=qnn_backend,
            qnn_performance_mode=qnn_performance_mode,
            qnn_profile_path=qnn_profile_path,
            qnn_allow_cpu_fallback=qnn_allow_cpu_fallback,
        )
        self.input = self.session.get_inputs()[0]
        self.input_name = self.input.name
        self.layout = _infer_layout(self.input.shape)
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold

    @property
    def description(self) -> str:
        return f"MediaPipe ONNX providers: {', '.join(self.session.get_providers())}"

    def detect(self, image_rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
        height, width = image_rgb.shape[:2]
        tensor = _resize_rgb_to_tensor_0_1(
            image_rgb,
            input_height=MEDIAPIPE_INPUT_H,
            input_width=MEDIAPIPE_INPUT_W,
            layout=self.layout,
        )
        outputs = self.session.run(None, {self.input_name: tensor}, self.run_options)
        return self._postprocess(outputs, width, height)

    def _postprocess(self, outputs: list[np.ndarray], width: int, height: int) -> list[tuple[int, int, int, int]]:
        coords = np.concatenate(
            [
                np.asarray(outputs[0][0], dtype=np.float32),
                np.asarray(outputs[1][0], dtype=np.float32),
            ],
            axis=0,
        )
        raw_scores = np.concatenate(
            [
                np.asarray(outputs[2][0], dtype=np.float32).reshape(-1),
                np.asarray(outputs[3][0], dtype=np.float32).reshape(-1),
            ],
            axis=0,
        )
        scores = 1.0 / (1.0 + np.exp(np.clip(-raw_scores, -80.0, 80.0)))

        boxes: list[tuple[int, int, int, int]] = []
        box_scores: list[float] = []
        for idx, score_value in enumerate(scores):
            score = float(score_value)
            if score < self.confidence_threshold:
                continue

            raw = coords[idx]
            anchor_cx, anchor_cy = _MEDIAPIPE_ANCHORS[idx]
            dx = float(raw[0]) / MEDIAPIPE_INPUT_W
            dy = float(raw[1]) / MEDIAPIPE_INPUT_H
            w_norm = float(raw[2]) / MEDIAPIPE_INPUT_W
            h_norm = float(raw[3]) / MEDIAPIPE_INPUT_H

            cx = anchor_cx + dx
            cy = anchor_cy + dy
            x1n = float(np.clip(cx - w_norm / 2.0, 0.0, 1.0))
            y1n = float(np.clip(cy - h_norm / 2.0, 0.0, 1.0))
            x2n = float(np.clip(cx + w_norm / 2.0, 0.0, 1.0))
            y2n = float(np.clip(cy + h_norm / 2.0, 0.0, 1.0))
            if x2n <= x1n or y2n <= y1n:
                continue

            x1 = int(x1n * width)
            y1 = int(y1n * height)
            x2 = int(x2n * width)
            y2 = int(y2n * height)
            if (x2 - x1) < 20 or (y2 - y1) < 20:
                continue

            boxes.append((x1, y1, x2 - x1, y2 - y1))
            box_scores.append(score)

        return self._nms(boxes, box_scores)

    def _nms(self, boxes: list[tuple[int, int, int, int]], scores: list[float]) -> list[tuple[int, int, int, int]]:
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        keep: list[tuple[int, int, int, int]] = []
        while order:
            i = order.pop(0)
            keep.append(boxes[i])
            order = [j for j in order if self._iou(boxes[i], boxes[j]) < self.nms_threshold]
        return keep

    @staticmethod
    def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        ax2, ay2 = ax + aw, ay + ah
        bx2, by2 = bx + bw, by + bh

        ix1 = max(ax, bx)
        iy1 = max(ay, by)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        area_a = aw * ah
        area_b = bw * bh
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0


class FaceDetector:
    def __init__(
        self,
        backend: FaceDetectorBackend = "auto",
        face_margin: float = 0.10,
        detector_model_path: str | Path | None = None,
        detector_runtime: Literal["onnx-qnn", "onnx-cpu"] = "onnx-cpu",
        qnn_backend: Literal["htp", "cpu"] = "htp",
        qnn_performance_mode: str = "burst",
        qnn_profile_path: str | Path | None = None,
        qnn_allow_cpu_fallback: bool = False,
    ):
        self.backend = backend
        self.face_margin = face_margin
        self._cv2 = None
        self._opencv_detector = None
        self._mediapipe_detector: _MediaPipeFaceDetector | None = None

        model_path = Path(detector_model_path) if detector_model_path else DEFAULT_MEDIAPIPE_MODEL
        if backend in {"auto", "mediapipe"} and model_path.exists():
            self._mediapipe_detector = _MediaPipeFaceDetector(
                model_path=model_path,
                runtime=detector_runtime,
                qnn_backend=qnn_backend,
                qnn_performance_mode=qnn_performance_mode,
                qnn_profile_path=qnn_profile_path,
                qnn_allow_cpu_fallback=qnn_allow_cpu_fallback,
            )
        elif backend == "mediapipe":
            raise FileNotFoundError(f"MediaPipe face detector model not found: {model_path}")

        if backend in {"auto", "opencv"} and self._mediapipe_detector is None:
            self._load_opencv_detector(required=backend == "opencv")

    @property
    def description(self) -> str:
        if self._mediapipe_detector is not None:
            return self._mediapipe_detector.description
        if self._opencv_detector is not None:
            return "OpenCV Haar cascade detector"
        return f"{self.backend} face detector"

    def _load_opencv_detector(self, required: bool) -> None:
        try:
            import cv2  # type: ignore[import-not-found]
        except Exception as exc:
            if required:
                raise RuntimeError(
                    "OpenCV is not available in this Python environment. "
                    "Use --face-detector auto, --face-detector mediapipe, or --face-detector metadata."
                ) from exc
            return

        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(str(cascade_path))
        if detector.empty():
            if required:
                raise RuntimeError(f"Could not load OpenCV Haar cascade at {cascade_path}")
            return

        self._cv2 = cv2
        self._opencv_detector = detector

    def detect_largest_face(self, frame: object) -> FaceCrop | None:
        image_rgb, metadata_box = _frame_to_rgb_and_box(frame)
        if image_rgb is None or image_rgb.size == 0:
            return None

        if self._mediapipe_detector is not None and self.backend in {"auto", "mediapipe"}:
            boxes = self._mediapipe_detector.detect(image_rgb)
            if boxes:
                largest = max(boxes, key=lambda rect: rect[2] * rect[3])
                crop = _crop_from_box(image_rgb, largest, self.face_margin)
                if crop is not None:
                    return crop

        if metadata_box is not None and self.backend in {"auto", "metadata"}:
            crop = _crop_from_box(image_rgb, metadata_box, self.face_margin)
            if crop is not None:
                return crop

        if self._opencv_detector is not None and self.backend in {"auto", "opencv"}:
            crop = self._detect_with_opencv(image_rgb)
            if crop is not None:
                return crop

        if self.backend in {"auto", "center"}:
            return _center_face_crop(image_rgb)

        return None

    def _detect_with_opencv(self, image_rgb: np.ndarray) -> FaceCrop | None:
        if self._cv2 is None or self._opencv_detector is None:
            return None

        gray = self._cv2.cvtColor(image_rgb, self._cv2.COLOR_RGB2GRAY)
        gray = self._cv2.equalizeHist(gray)
        faces = self._opencv_detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80),
        )
        if len(faces) == 0:
            return None

        x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
        return _crop_from_box(image_rgb, (int(x), int(y), int(w), int(h)), self.face_margin)


class _QaiHubModelsCavaFaceRuntime:
    def __init__(self, use_flip: bool, input_height: int, input_width: int):
        try:
            from qai_hub_models.models.cavaface.app import CavaFaceApp
            from qai_hub_models.models.cavaface.model import CavaFace
        except ImportError as exc:
            raise RuntimeError(
                "qai-hub-models is not installed. On Windows ARM64/X Elite, use the local "
                "ONNX model with --model-runtime onnx-qnn."
            ) from exc

        self.model = CavaFace.from_pretrained()
        self.app = CavaFaceApp(self.model, input_height=input_height, input_width=input_width)
        self.use_flip = use_flip

    @property
    def description(self) -> str:
        return "qai-hub-models PyTorch runtime"

    def predict_features(self, image_rgb: np.ndarray) -> np.ndarray:
        pil_image = Image.fromarray(np.asarray(image_rgb, dtype=np.uint8), mode="RGB")
        return self.app.predict_features(pil_image, use_flip=self.use_flip)


class _OnnxCavaFaceRuntime:
    def __init__(
        self,
        model_path: str | Path,
        runtime: Literal["onnx-qnn", "onnx-cpu"],
        use_flip: bool,
        input_height: int,
        input_width: int,
        qnn_backend: Literal["htp", "cpu"] = "htp",
        qnn_performance_mode: str = "burst",
        qnn_profile_path: str | Path | None = None,
        qnn_allow_cpu_fallback: bool = False,
    ):
        self.model_path = _find_onnx_model_path(model_path)
        self.use_flip = use_flip
        self.input_height = input_height
        self.input_width = input_width
        self.session, self.run_options = _create_onnx_session(
            self.model_path,
            runtime=runtime,
            qnn_backend=qnn_backend,
            qnn_performance_mode=qnn_performance_mode,
            qnn_profile_path=qnn_profile_path,
            qnn_allow_cpu_fallback=qnn_allow_cpu_fallback,
        )
        self.input = self.session.get_inputs()[0]
        self.input_name = self.input.name
        self.layout = _infer_layout(self.input.shape)
        self.providers = ", ".join(self.session.get_providers())

    @property
    def description(self) -> str:
        return f"ONNX Runtime providers: {self.providers}"

    def predict_features(self, image_rgb: np.ndarray) -> np.ndarray:
        tensor = _cavaface_rgb_to_tensor(
            image_rgb,
            input_height=self.input_height,
            input_width=self.input_width,
            layout=self.layout,
        )
        embedding = self._run(tensor)
        if self.use_flip:
            if self.layout == "NHWC":
                flipped = np.flip(tensor, axis=2).copy()
            else:
                flipped = np.flip(tensor, axis=3).copy()
            embedding = (embedding + self._run(flipped)) / 2.0
        return embedding

    def _run(self, tensor: np.ndarray) -> np.ndarray:
        outputs = self.session.run(None, {self.input_name: tensor}, self.run_options)
        return np.asarray(outputs[0], dtype=np.float32).reshape(-1)


class CavaFaceRecognizer:
    display_name = "CavaFace"
    database_id = "cavaface"
    embedding_size = 512

    def __init__(
        self,
        use_flip: bool = False,
        face_margin: float = 0.10,
        face_detector: FaceDetectorBackend = "auto",
        detector_model_path: str | Path | None = None,
        model_runtime: ModelRuntime = "auto",
        model_path: str | Path | None = None,
        qnn_backend: Literal["htp", "cpu"] = "htp",
        qnn_performance_mode: str = "burst",
        qnn_profile_path: str | Path | None = None,
        qnn_allow_cpu_fallback: bool = False,
    ):
        local_model_path = Path(model_path) if model_path is not None else (DEFAULT_CAVAFACE_MODEL if DEFAULT_CAVAFACE_MODEL.exists() else None)
        runtime = _local_default_runtime(local_model_path) if model_runtime == "auto" else model_runtime

        detector_runtime: Literal["onnx-qnn", "onnx-cpu"] = "onnx-qnn" if runtime == "onnx-qnn" else "onnx-cpu"
        self.detector = FaceDetector(
            face_detector,
            face_margin=face_margin,
            detector_model_path=detector_model_path,
            detector_runtime=detector_runtime,
            qnn_backend=qnn_backend,
            qnn_performance_mode=qnn_performance_mode,
            qnn_profile_path=qnn_profile_path,
            qnn_allow_cpu_fallback=qnn_allow_cpu_fallback,
        )
        self.input_height = CAVAFACE_INPUT_H
        self.input_width = CAVAFACE_INPUT_W

        if runtime in {"onnx-qnn", "onnx-cpu"}:
            if local_model_path is None:
                raise ValueError(
                    f"--model-path is required when --model-runtime {runtime} is used and "
                    f"{DEFAULT_CAVAFACE_MODEL} does not exist."
                )
            self.runtime = _OnnxCavaFaceRuntime(
                model_path=local_model_path,
                runtime=runtime,
                use_flip=use_flip,
                input_height=self.input_height,
                input_width=self.input_width,
                qnn_backend=qnn_backend,
                qnn_performance_mode=qnn_performance_mode,
                qnn_profile_path=qnn_profile_path,
                qnn_allow_cpu_fallback=qnn_allow_cpu_fallback,
            )
        else:
            self.runtime = _QaiHubModelsCavaFaceRuntime(
                use_flip=use_flip,
                input_height=self.input_height,
                input_width=self.input_width,
            )

    @property
    def runtime_description(self) -> str:
        return f"{self.runtime.description}; detector={self.detector.description}"

    def detect_largest_face(self, frame: object) -> FaceCrop | None:
        return self.detector.detect_largest_face(frame)

    def embedding_from_frame(self, frame: object) -> np.ndarray:
        face = self.detect_largest_face(frame)
        if face is None:
            raise ValueError("No face detected")
        return _normalize_embedding(self.runtime.predict_features(face.image_rgb))

    def embedding_from_bgr(self, frame_bgr: np.ndarray) -> np.ndarray:
        try:
            import cv2  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError("embedding_from_bgr requires OpenCV; use embedding_from_frame instead.") from exc

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        return self.embedding_from_frame(CameraFrame(frame_rgb))

    def embedding_from_image_path(self, image_path: str | Path) -> np.ndarray:
        path = Path(image_path)
        if not path.exists():
            raise ValueError(f"Could not read image: {path}")
        with Image.open(path) as image:
            frame = CameraFrame(_rgb_array_from_pil(image))
        return self.embedding_from_frame(frame)


class MobileFaceNetRecognizer:
    display_name = "MobileFaceNet"
    database_id = "mobilefacenet"
    embedding_size = 128

    def __init__(
        self,
        face_margin: float = 0.10,
        face_detector: FaceDetectorBackend = "auto",
        detector_model_path: str | Path | None = None,
        model_runtime: ModelRuntime = "auto",
        model_path: str | Path | None = None,
        qnn_backend: Literal["htp", "cpu"] = "htp",
        qnn_performance_mode: str = "burst",
        qnn_profile_path: str | Path | None = None,
        qnn_allow_cpu_fallback: bool = False,
    ):
        local_model_path = Path(model_path) if model_path is not None else (
            DEFAULT_MOBILEFACENET_MODEL if DEFAULT_MOBILEFACENET_MODEL.exists() else None
        )
        runtime = _local_default_runtime(local_model_path) if model_runtime == "auto" else model_runtime
        if runtime == "qaihub":
            raise RuntimeError("MobileFaceNet is available through local ONNX only. Use --model-runtime onnx-qnn or onnx-cpu.")

        detector_runtime: Literal["onnx-qnn", "onnx-cpu"] = "onnx-qnn" if runtime == "onnx-qnn" else "onnx-cpu"
        self.detector = FaceDetector(
            face_detector,
            face_margin=face_margin,
            detector_model_path=detector_model_path,
            detector_runtime=detector_runtime,
            qnn_backend=qnn_backend,
            qnn_performance_mode=qnn_performance_mode,
            qnn_profile_path=qnn_profile_path,
            qnn_allow_cpu_fallback=qnn_allow_cpu_fallback,
        )
        self.input_height = MOBILEFACENET_INPUT_H
        self.input_width = MOBILEFACENET_INPUT_W

        if local_model_path is None:
            raise ValueError(
                f"--model-path is required for MobileFaceNet because {DEFAULT_MOBILEFACENET_MODEL} does not exist."
            )

        self.runtime = _OnnxCavaFaceRuntime(
            model_path=local_model_path,
            runtime=runtime,
            use_flip=False,
            input_height=self.input_height,
            input_width=self.input_width,
            qnn_backend=qnn_backend,
            qnn_performance_mode=qnn_performance_mode,
            qnn_profile_path=qnn_profile_path,
            qnn_allow_cpu_fallback=qnn_allow_cpu_fallback,
        )

    @property
    def runtime_description(self) -> str:
        return f"MobileFaceNet {self.runtime.description}; detector={self.detector.description}"

    def detect_largest_face(self, frame: object) -> FaceCrop | None:
        return self.detector.detect_largest_face(frame)

    def embedding_from_frame(self, frame: object) -> np.ndarray:
        face = self.detect_largest_face(frame)
        if face is None:
            raise ValueError("No face detected")
        return _normalize_embedding(self.runtime.predict_features(face.image_rgb))

    def embedding_from_face_image(self, image_rgb: np.ndarray) -> np.ndarray:
        return _normalize_embedding(self.runtime.predict_features(image_rgb))

    def embedding_from_bgr(self, frame_bgr: np.ndarray) -> np.ndarray:
        try:
            import cv2  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError("embedding_from_bgr requires OpenCV; use embedding_from_frame instead.") from exc

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        return self.embedding_from_frame(CameraFrame(frame_rgb))

    def embedding_from_image_path(self, image_path: str | Path) -> np.ndarray:
        path = Path(image_path)
        if not path.exists():
            raise ValueError(f"Could not read image: {path}")
        with Image.open(path) as image:
            frame = CameraFrame(_rgb_array_from_pil(image))
        return self.embedding_from_frame(frame)

    def embedding_from_face_image_path(self, image_path: str | Path) -> np.ndarray:
        path = Path(image_path)
        if not path.exists():
            raise ValueError(f"Could not read image: {path}")
        with Image.open(path) as image:
            return self.embedding_from_face_image(_rgb_array_from_pil(image))
