from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from face_engine import FaceDatabase, MobileFaceNetRecognizer, _normalize_embedding


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "mobilefacenet_model_pipeline"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "known_faces_mobilefacenet" / "embeddings.npz"


def add_known_npy(source_dir: Path, rows: list[tuple[str, np.ndarray]]) -> int:
    count = 0
    for path in sorted(source_dir.glob("*.npy")):
        name = path.stem
        embeddings = np.asarray(np.load(path), dtype=np.float32)
        if embeddings.ndim == 1:
            embeddings = embeddings[np.newaxis, :]
        for embedding in embeddings:
            rows.append((name, _normalize_embedding(embedding)))
            count += 1
    return count


def add_enrolled_crops(
    source_dir: Path,
    rows: list[tuple[str, np.ndarray]],
    recognizer: MobileFaceNetRecognizer,
) -> int:
    count = 0
    for person_dir in sorted(child for child in source_dir.iterdir() if child.is_dir()):
        for path in sorted(person_dir.glob("*face*.jpg")):
            try:
                rows.append((person_dir.name, recognizer.embedding_from_face_image_path(path)))
                count += 1
            except Exception as exc:
                print(f"Skipping {path}: {exc}")
    return count


def write_database(rows: list[tuple[str, np.ndarray]], output_path: Path) -> None:
    database = FaceDatabase()
    grouped: dict[str, list[np.ndarray]] = {}
    for name, embedding in rows:
        grouped.setdefault(name, []).append(embedding)
    for name in sorted(grouped):
        database.add_many(name, grouped[name])
    database.save(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert the MobileFaceNet package DB into the app database format.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="mobilefacenet_model_pipeline directory.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output embeddings.npz path.")
    parser.add_argument("--model-runtime", choices=("onnx-cpu", "onnx-qnn", "auto"), default="onnx-cpu")
    parser.add_argument("--model-path", type=Path, default=None, help="Optional MobileFaceNet ONNX model path.")
    parser.add_argument("--detector-model-path", type=Path, default=None, help="Optional MediaPipe detector path.")
    parser.add_argument("--skip-known-npy", action="store_true", help="Do not import source known_faces/*.npy files.")
    parser.add_argument("--skip-enrolled-crops", action="store_true", help="Do not embed source enrolled_faces/*face*.jpg crops.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source
    rows: list[tuple[str, np.ndarray]] = []

    if not args.skip_known_npy:
        count = add_known_npy(source / "known_faces", rows)
        print(f"Imported {count} embedding(s) from {source / 'known_faces'}")

    if not args.skip_enrolled_crops:
        recognizer = MobileFaceNetRecognizer(
            face_detector="center",
            model_runtime=args.model_runtime,
            model_path=args.model_path,
            detector_model_path=args.detector_model_path,
        )
        count = add_enrolled_crops(source / "enrolled_faces", rows, recognizer)
        print(f"Embedded {count} enrolled face crop(s) from {source / 'enrolled_faces'}")

    if not rows:
        raise SystemExit("No MobileFaceNet embeddings were imported.")

    write_database(rows, args.output)
    print(f"Saved {len(rows)} MobileFaceNet embedding(s) to {args.output}")


if __name__ == "__main__":
    main()
