from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "models"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export CavaFace as a precompiled QNN ONNX model for Snapdragon X Elite."
    )
    parser.add_argument(
        "--device",
        default="Snapdragon X Elite CRD",
        help="Qualcomm AI Hub device name used for compilation.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Where model assets are saved.")
    parser.add_argument("--profile", action="store_true", help="Also profile the model on AI Hub after compilation.")
    parser.add_argument("--infer", action="store_true", help="Also run AI Hub sample inference after compilation.")
    parser.add_argument("--zip-assets", action="store_true", help="Save downloaded assets as a zip.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if platform.system() == "Windows" and platform.machine().upper() in {"ARM64", "AARCH64"}:
        print(
            "qai-hub-models is published for Windows x64 Python, not native Windows ARM64 Python. "
            "Run this export helper from an x64 Python environment, then use the downloaded model "
            "from native ARM64 Python with run_guard.py --model-runtime onnx-qnn.",
            file=sys.stderr,
        )

    command = [
        sys.executable,
        "-m",
        "qai_hub_models.models.cavaface.export",
        "--device",
        args.device,
        "--target-runtime",
        "precompiled_qnn_onnx",
        "--output-dir",
        str(args.output_dir),
    ]

    if not args.profile:
        command.append("--skip-profiling")
    if not args.infer:
        command.append("--skip-inferencing")
    if args.zip_assets:
        command.append("--zip-assets")

    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
