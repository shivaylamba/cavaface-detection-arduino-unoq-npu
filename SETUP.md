# CavaFace UNO Q NPU Demo Setup

This guide sets up the retail demo from the GitHub repository:

```text
https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu.git
```

The repository contains the demo source code, firmware sketch, dashboard UI,
and Python scripts. It intentionally does not contain large model files,
private face embeddings, captured face images, virtual environments, logs, or
local Arduino tool caches.

## What Was Pushed To GitHub

These project files are in GitHub:

```text
.gitignore
README.md
SETUP.md
firmware/arduino_q_face_guard/arduino_q_face_guard.ino
laptop_ai_guard/__init__.py
laptop_ai_guard/demo_dashboard.html
laptop_ai_guard/enroll_faces.py
laptop_ai_guard/export_cavaface_npu.py
laptop_ai_guard/face_engine.py
laptop_ai_guard/requirements.txt
laptop_ai_guard/requirements-windows-npu.txt
laptop_ai_guard/run_guard.py
```

## Files Not Pushed But Needed Locally

The following files are needed for the full Windows/X Elite NPU demo, but were
not pushed to GitHub.

| Purpose | Fresh-clone target path | Current laptop source path | Why not pushed |
| --- | --- | --- | --- |
| CavaFace ONNX model | `C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu\laptop_ai_guard\models\cavaface\cavaface.onnx` | `C:\Users\Public\Downloads\arduino\arduino-face-detection\laptop_ai_guard\models\cavaface\cavaface.onnx` | Large runtime model, 132 MB |
| MediaPipe face detector ONNX model | `C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu\laptop_ai_guard\models\media_pipe\media_pipe.onnx` | `C:\Users\Public\Downloads\arduino\arduino-face-detection\laptop_ai_guard\models\media_pipe\media_pipe.onnx` | Runtime model asset |
| Demo known-face database | `C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu\laptop_ai_guard\known_faces\embeddings.npz` | `C:\Users\Public\Downloads\arduino\arduino-face-detection\laptop_ai_guard\known_faces\embeddings.npz` | Private biometric face embeddings |

The working package that originally supplied the model files is also local only:

```text
C:\Users\Public\Downloads\arduino\arduino-face-detection\face_ detection_package_24_4_2026
```

Useful files inside that package:

```text
C:\Users\Public\Downloads\arduino\arduino-face-detection\face_ detection_package_24_4_2026\face_ detection_package_24_4_2026\models\cavaface\cavaface.onnx
C:\Users\Public\Downloads\arduino\arduino-face-detection\face_ detection_package_24_4_2026\face_ detection_package_24_4_2026\models\media_pipe\media_pipe.onnx
C:\Users\Public\Downloads\arduino\arduino-face-detection\face_ detection_package_24_4_2026\face_ detection_package_24_4_2026\known_faces\Rajath.npy
C:\Users\Public\Downloads\arduino\arduino-face-detection\face_ detection_package_24_4_2026\face_ detection_package_24_4_2026\known_faces\Shivay.npy
C:\Users\Public\Downloads\arduino\arduino-face-detection\face_ detection_package_24_4_2026\face_ detection_package_24_4_2026\known_faces\Surya.npy
```

The current local `embeddings.npz` contains:

```text
Rajath: 10 samples
Shivay: 1 sample
Surya: 10 samples
Total: 21 embeddings
```

You do not have to copy `embeddings.npz` if you prefer to enroll people from the
dashboard using the `Add Known Face` tab.

## Files Not Pushed And Not Needed From GitHub

These are generated locally and should stay out of GitHub:

```text
laptop_ai_guard\.venv\
laptop_ai_guard\captures\
laptop_ai_guard\models\
laptop_ai_guard\known_faces\*.npz
.codex_tmp\
*.log
```

Notes:

- `laptop_ai_guard\.venv\` is recreated during Python setup.
- `laptop_ai_guard\captures\` is created when the demo saves recognition frames.
- `.codex_tmp\` was used on this laptop for temporary Arduino CLI/tooling and a clean push repo.
- `_qnn.log` and similar logs are diagnostic output only.

## Hardware Needed

```text
Arduino UNO Q
Modulino Distance
Modulino Buzzer
USB cable
Windows ARM64 laptop with Snapdragon X Elite / compatible NPU
Chrome or Edge with camera access
```

Connect the Modulino Distance and Modulino Buzzer to the UNO Q Qwiic chain. The
order does not matter because both modules are I2C devices.

## Step 1: Clone The GitHub Repo

Open PowerShell:

```powershell
cd C:\Users\Public\Downloads\arduino
git clone https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu.git
cd C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu
```

## Step 2: Create The Python Environment

Use native Windows ARM64 Python.

```powershell
python -c "import platform; print(platform.machine())"
```

Expected output:

```text
ARM64
```

Create and activate the virtual environment:

```powershell
python -m venv laptop_ai_guard\.venv
.\laptop_ai_guard\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r laptop_ai_guard\requirements-windows-npu.txt
```

## Step 3: Copy The Required Model Files

Create the model folders:

```powershell
New-Item -ItemType Directory -Force laptop_ai_guard\models\cavaface
New-Item -ItemType Directory -Force laptop_ai_guard\models\media_pipe
```

If you are setting up on the same laptop where the demo was prepared, copy from
the previous working directory:

```powershell
Copy-Item `
  "C:\Users\Public\Downloads\arduino\arduino-face-detection\laptop_ai_guard\models\cavaface\cavaface.onnx" `
  "C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu\laptop_ai_guard\models\cavaface\cavaface.onnx"

Copy-Item `
  "C:\Users\Public\Downloads\arduino\arduino-face-detection\laptop_ai_guard\models\media_pipe\media_pipe.onnx" `
  "C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu\laptop_ai_guard\models\media_pipe\media_pipe.onnx"
```

If you only have the original working package, copy from there instead:

```powershell
Copy-Item `
  "C:\Users\Public\Downloads\arduino\arduino-face-detection\face_ detection_package_24_4_2026\face_ detection_package_24_4_2026\models\cavaface\cavaface.onnx" `
  "C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu\laptop_ai_guard\models\cavaface\cavaface.onnx"

Copy-Item `
  "C:\Users\Public\Downloads\arduino\arduino-face-detection\face_ detection_package_24_4_2026\face_ detection_package_24_4_2026\models\media_pipe\media_pipe.onnx" `
  "C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu\laptop_ai_guard\models\media_pipe\media_pipe.onnx"
```

Verify the files:

```powershell
Get-Item laptop_ai_guard\models\cavaface\cavaface.onnx
Get-Item laptop_ai_guard\models\media_pipe\media_pipe.onnx
```

## Step 4: Set Up Known Faces

You have two options.

### Option A: Enroll From The Dashboard

This is recommended for a fresh demo machine.

1. Start the app using the command in Step 8.
2. Open `http://127.0.0.1:8765/`.
3. Go to `Add Known Face`.
4. Enter the person name.
5. Capture 4, 6, or 8 samples.
6. Confirm the person appears under `Known Faces`.

This creates:

```text
laptop_ai_guard\known_faces\embeddings.npz
```

### Option B: Copy The Existing Demo Database

Use this only if you intentionally want the same local demo people from this
laptop.

```powershell
New-Item -ItemType Directory -Force laptop_ai_guard\known_faces

Copy-Item `
  "C:\Users\Public\Downloads\arduino\arduino-face-detection\laptop_ai_guard\known_faces\embeddings.npz" `
  "C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu\laptop_ai_guard\known_faces\embeddings.npz"
```

Verify:

```powershell
@'
import numpy as np
data = np.load("laptop_ai_guard/known_faces/embeddings.npz", allow_pickle=False)
names = [str(x) for x in data["names"].tolist()]
print(data["embeddings"].shape)
print(sorted(set(names)))
'@ | .\laptop_ai_guard\.venv\Scripts\python.exe -
```

Expected for the current copied database:

```text
(21, 512)
['Rajath', 'Shivay', 'Surya']
```

## Step 5: Install Arduino IDE / UNO Q Support

Install Arduino IDE if it is not already installed:

```text
https://www.arduino.cc/en/software
```

Then install or verify:

```text
Arduino UNO Q board support
Arduino_Modulino library
Arduino_RouterBridge library
```

The firmware sketch is:

```text
C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu\firmware\arduino_q_face_guard\arduino_q_face_guard.ino
```

## Step 6: Upload The Firmware

The simplest path is Arduino IDE:

1. Open Arduino IDE.
2. Open `firmware\arduino_q_face_guard\arduino_q_face_guard.ino`.
3. Select the Arduino UNO Q board.
4. Select the UNO Q port.
5. Upload the sketch.

If using Arduino CLI, the command shape is:

```powershell
arduino-cli compile --fqbn arduino:zephyr:unoq firmware\arduino_q_face_guard
arduino-cli upload -p COM3 --fqbn arduino:zephyr:unoq firmware\arduino_q_face_guard
```

On the working demo laptop, the board was:

```text
Port: COM3
Serial number: 2344639082
FQBN: arduino:zephyr:unoq
```

After upload, the UNO Q matrix should show module/RPC status. The laptop app
expects the firmware to expose RouterBridge methods such as:

```text
face_guard_ping
face_guard_status
read_distance_mm
buzz_unknown
```

## Step 7: Quick Model And DB Smoke Test

From the repo root:

```powershell
@'
from pathlib import Path
import sys, numpy as np
sys.path.insert(0, str(Path("laptop_ai_guard").resolve()))
from face_engine import CavaFaceRecognizer, FaceDatabase

r = CavaFaceRecognizer(face_detector="mediapipe", model_runtime="onnx-qnn")
emb = r.runtime.predict_features(np.full((160,160,3), 127, dtype=np.uint8))
print("runtime:", r.runtime_description)
print("embedding:", emb.shape, "norm:", np.linalg.norm(emb))

db = FaceDatabase.load("laptop_ai_guard/known_faces/embeddings.npz")
print("db:", db.embeddings.shape, sorted(set(db.names)))
'@ | .\laptop_ai_guard\.venv\Scripts\python.exe -
```

Expected:

```text
runtime: ... QNNExecutionProvider ...
embedding: (512,) norm: near 1.0
db: (N, 512) [...]
```

If no known-face database has been enrolled yet, `db` may be `(0, 512)`. That is
fine for first setup; every face will be unknown until enrollment.

## Step 8: Run The Retail Demo

Use this from the repo root:

```powershell
.\laptop_ai_guard\.venv\Scripts\python.exe -u laptop_ai_guard\run_guard.py `
  --hardware-source routerbridge `
  --camera-source browser `
  --browser-timeout 180 `
  --face-detector mediapipe `
  --model-runtime onnx-qnn `
  --threshold 0.50 `
  --proximity-threshold-mm 700 `
  --trigger-cooldown 2 `
  --poll-interval 0.25
```

If automatic ADB discovery does not work, pass the ADB path explicitly. On the
prepared laptop it was:

```powershell
.\laptop_ai_guard\.venv\Scripts\python.exe -u laptop_ai_guard\run_guard.py `
  --hardware-source routerbridge `
  --adb-path .\.codex_tmp\arduino-data\packages\arduino\tools\adb\32.0.0\adb.exe `
  --camera-source browser `
  --browser-timeout 180 `
  --face-detector mediapipe `
  --model-runtime onnx-qnn `
  --threshold 0.50 `
  --proximity-threshold-mm 700 `
  --trigger-cooldown 2 `
  --poll-interval 0.25
```

For a normal Arduino IDE install, ADB is often under:

```text
%LOCALAPPDATA%\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe
```

## Step 9: Open The Dashboard

Open:

```text
http://127.0.0.1:8765/
```

Do not open this file directly:

```text
laptop_ai_guard\demo_dashboard.html
```

The direct `file:///` preview can draw the UI, but it cannot call the Python
APIs for `Known Faces` or `Add Known Face`.

Dashboard views:

```text
Live Demo        Customer-facing sensor/AI/buzzer flow
Known Faces      Current names and sample counts in embeddings.npz
Add Known Face   Guided camera enrollment into embeddings.npz
```

## Step 10: Demo Script For Store Staff

1. Start the Python app.
2. Open `http://127.0.0.1:8765/`.
3. Allow camera access.
4. Confirm the dashboard says camera connected.
5. Confirm `Known Faces` shows enrolled people, or add one.
6. Return to `Live Demo`.
7. Bring a hand/object close to the Modulino Distance sensor.
8. Watch the screen move from distance detection to face check.
9. Known face: UI shows known match and buzzer stays quiet.
10. Unknown face: UI shows unknown visitor and buzzer sounds.

## Troubleshooting

### Known Faces Shows Offline Or Zero

Make sure the page URL is:

```text
http://127.0.0.1:8765/
```

If it is `file:///.../demo_dashboard.html`, the page cannot read the local
database.

### RouterBridge Method Not Available

Re-upload:

```text
firmware\arduino_q_face_guard\arduino_q_face_guard.ino
```

The board must run this sketch for `face_guard_ping` and related RPC methods to
exist.

### Camera Page Opens But No Frames Arrive

1. Allow camera access in the browser.
2. Keep the dashboard tab open.
3. Restart the Python app.
4. Reopen `http://127.0.0.1:8765/`.

### Model Load Fails

Check that these files exist:

```text
laptop_ai_guard\models\cavaface\cavaface.onnx
laptop_ai_guard\models\media_pipe\media_pipe.onnx
```

### GitHub Repo Does Not Include Models Or Known Faces

This is intentional. Models are large runtime assets and known faces are
biometric data. Copy the models locally and enroll/copy the known-face database
as described above.

