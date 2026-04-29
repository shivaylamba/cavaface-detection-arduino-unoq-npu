# Arduino Project Hub Submission Draft

This markdown file is a copy-paste draft for submitting the project to Arduino
Project Hub.

The wording is intentionally vendor-neutral. It does not name a specific company
or customer. It describes the project as a local AI + physical computing demo
using Arduino UNO Q, Modulino components, and a Windows ARM64 laptop running
face recognition on the NPU.

## Project Hub Field: Content Type

```text
Showcase
```

Alternative:

```text
Tutorial
```

Use `Showcase` if the submission is mainly a demo of what was built. Use
`Tutorial` if you want to include every setup step and expect other makers to
reproduce it end to end.

## Project Hub Field: Name

```text
AI Guard Demo with Arduino UNO Q, Modulino Sensors, and Local NPU Face Recognition
```

Shorter option:

```text
AI Guard Demo on Arduino UNO Q with Local Face Recognition
```

## Project Hub Field: Intro

```text
Build a proximity-triggered face recognition demo where Arduino UNO Q senses a person nearby and a laptop NPU runs local AI before driving a physical buzzer response.
```

## Project Hub Field: Skill Level

```text
Advanced
```

Reason: the project combines Arduino firmware, RouterBridge communication,
browser camera capture, local Python runtime, ONNX Runtime QNN, and NPU model
execution.

## Project Hub Field: Tags

Arduino Project Hub recommends a maximum of three tags and advises using tags
for what the project achieves, not simply the component names.

Suggested tags:

```text
Edge AI
Computer Vision
Interactive Demo
```

Alternative tags:

```text
Machine Learning
Physical Computing
Smart Access
```

## Project Hub Field: Components And Supplies

Add these to the Project Hub components section.

| Quantity | Component | Notes |
| --- | --- | --- |
| 1 | Arduino UNO Q | Runs the firmware and communicates with the laptop through RouterBridge. |
| 1 | Modulino Distance | Detects when a person or object is close enough to trigger recognition. |
| 1 | Modulino Buzzer | Provides a physical alert for unknown faces or failure states. |
| 1 | Qwiic cable chain | Connects Modulino components to the UNO Q I2C/Qwiic chain. |
| 1 | USB cable | Connects the UNO Q to the laptop. |
| 1 | Windows ARM64 laptop with Snapdragon X Elite or compatible NPU | Runs the browser dashboard, CavaFace model, and MediaPipe detector. |
| 1 | Laptop camera or USB webcam | Provides live face frames through the browser dashboard. |

## Project Hub Field: Software Apps And Online Services

Add these to the Project Hub software/tools section.

| Software / Tool | Purpose |
| --- | --- |
| Arduino IDE | Uploads the UNO Q firmware. |
| Python 3 on Windows ARM64 | Runs the local demo app. |
| ONNX Runtime QNN | Runs CavaFace and the MediaPipe detector with QNN/NPU support. |
| Browser with camera support | Opens the local dashboard and streams camera frames to Python. |
| GitHub | Hosts the source code. |

Optional:

| Software / Tool | Purpose |
| --- | --- |
| Arduino CLI | Alternative firmware build/upload path. |
| NumPy | Stores and loads known-face embeddings. |

## Project Hub Field: Cover Image Notes

Use a high-resolution photo of the final working setup.

Suggested cover image composition:

```text
Laptop screen showing the AI Guard Demo dashboard
Arduino UNO Q visible next to the laptop
Modulino Distance and Modulino Buzzer connected on the Qwiic chain
No company logos or customer-identifying information
Good lighting, no text overlay
```

Suggested additional images:

```text
1. Close-up of Arduino UNO Q with Modulino Distance and Buzzer.
2. Screenshot of the dashboard showing Live Demo.
3. Screenshot of Known Faces screen with generic demo names.
4. Screenshot of Add Known Face screen.
5. Photo of the distance-trigger interaction.
```

## Project Hub Field: Project Description

### Overview

This project demonstrates how Arduino hardware and a laptop AI runtime can work
together in a physical, interactive demo.

The Arduino UNO Q watches a Modulino Distance sensor. When a person or object
comes close enough, the laptop captures a camera frame from a local browser
dashboard. A MediaPipe face detector finds the face, CavaFace converts the face
into a 512-dimensional embedding, and the app compares that embedding against a
local known-face database.

If the face matches a known person, the dashboard shows a trusted match and the
buzzer stays quiet. If the face is unknown, the dashboard shows an alert and the
laptop calls the UNO Q firmware to sound the Modulino Buzzer.

The result is a compact demonstration of edge AI, sensor input, local NPU
inference, and physical output.

### What This Project Shows

This demo is useful because it connects four ideas that are often shown
separately:

```text
1. A physical sensor detects a real-world interaction.
2. Arduino firmware exposes that sensor data to a laptop.
3. A local AI model runs on the laptop NPU.
4. The AI result controls a physical actuator.
```

The dashboard is designed for non-technical demonstrations. Instead of showing
only terminal logs, it shows the live camera, distance reading, face match
status, known-face database, and buzzer decision in one browser UI.

### Architecture

```text
Person approaches
       |
       v
Modulino Distance sensor
       |
       v
Arduino UNO Q firmware
       |
       v
RouterBridge over USB
       |
       v
Python app on Windows ARM64 laptop
       |
       +--> Browser dashboard streams camera frames
       |
       +--> MediaPipe ONNX face detector
       |
       +--> CavaFace ONNX model through ONNX Runtime QNN
       |
       +--> Local known-face embedding database
       |
       v
Known or unknown decision
       |
       v
Modulino Buzzer response
```

### Why Use Arduino UNO Q Here?

The UNO Q handles the physical side of the interaction. It reads the Modulino
Distance sensor, exposes status and distance readings through RouterBridge, and
controls the Modulino Buzzer. This keeps the hardware interaction simple and
reliable while allowing the laptop to do heavier AI inference.

The laptop handles camera capture, local face detection, face embedding, and
matching. This split is practical for demos because the person presenting the
project can show both sides clearly: the Arduino board reacts to the physical
world, and the laptop runs local AI.

### Dashboard Views

The browser dashboard has three views:

```text
Live Demo
Known Faces
Add Known Face
```

`Live Demo` is the main demonstration screen. It shows:

```text
Live camera preview
Distance sensor reading
Current AI decision
Match score
Buzzer state
Four-step hardware-to-AI flow
```

`Known Faces` shows the current local embedding database. It displays the names
and the number of face samples saved for each known person.

`Add Known Face` is a guided enrollment screen. The operator enters a display
name, chooses the number of samples, and the app captures live camera frames.
Those frames are converted into CavaFace embeddings and appended to the local
database.

This is enrollment, not neural-network retraining. The CavaFace model stays
fixed. The demo simply adds more local face templates to compare against.

### Privacy And Safety Notes

This is a prototype demo. It is not a production access-control system.

Important limitations:

```text
It does not include liveness detection.
It does not prove identity.
It stores local biometric embeddings.
It should not be used for security-critical decisions.
It should only enroll people with consent.
```

For public demos, use generic demo names, avoid saving unnecessary face images,
and explain that all matching in this prototype happens locally.

## Project Hub Section: Step-By-Step Build

### Step 1: Clone The Repository

```powershell
cd C:\Users\Public\Downloads\arduino
git clone https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu.git
cd C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu
```

### Step 2: Create The Python Environment

Use native Windows ARM64 Python.

```powershell
python -c "import platform; print(platform.machine())"
```

Expected:

```text
ARM64
```

Create and install the app environment:

```powershell
python -m venv laptop_ai_guard\.venv
.\laptop_ai_guard\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r laptop_ai_guard\requirements-windows-npu.txt
```

### Step 3: Add The Local Model Files

The GitHub repository does not include the ONNX model files because they are
runtime assets and the CavaFace model is large.

The app expects:

```text
laptop_ai_guard\models\cavaface\cavaface.onnx
laptop_ai_guard\models\media_pipe\media_pipe.onnx
```

Create the folders:

```powershell
New-Item -ItemType Directory -Force laptop_ai_guard\models\cavaface
New-Item -ItemType Directory -Force laptop_ai_guard\models\media_pipe
```

Copy the ONNX files from the working model package or local backup into those
paths.

### Step 4: Upload The Arduino Firmware

Open Arduino IDE and load:

```text
firmware\arduino_q_face_guard\arduino_q_face_guard.ino
```

Select the Arduino UNO Q board and the correct port, then upload the sketch.

The firmware provides RouterBridge methods used by the laptop app:

```text
face_guard_ping
face_guard_status
distance_found
buzzer_found
threshold_mm
set_threshold_mm
read_distance_mm
buzz_unknown
buzz_fault
buzz_test
```

### Step 5: Run The Demo App

From the repository root:

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

If the app cannot find ADB automatically, pass the ADB path:

```powershell
.\laptop_ai_guard\.venv\Scripts\python.exe -u laptop_ai_guard\run_guard.py `
  --hardware-source routerbridge `
  --adb-path "%LOCALAPPDATA%\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe" `
  --camera-source browser `
  --browser-timeout 180 `
  --face-detector mediapipe `
  --model-runtime onnx-qnn `
  --threshold 0.50 `
  --proximity-threshold-mm 700 `
  --trigger-cooldown 2 `
  --poll-interval 0.25
```

### Step 6: Open The Dashboard

Open:

```text
http://127.0.0.1:8765/
```

Do not open the HTML file directly with a `file:///` URL. The static file can
draw the page, but it cannot read known faces or enroll new ones because those
features are served by the local Python app.

### Step 7: Add A Known Face

1. Open the dashboard.
2. Go to `Add Known Face`.
3. Enter a generic display name, such as `Demo Staff 1`.
4. Choose 4, 6, or 8 samples.
5. Face the camera.
6. Click `Add Known Face`.
7. Confirm the name appears under `Known Faces`.

This creates or updates:

```text
laptop_ai_guard\known_faces\embeddings.npz
```

### Step 8: Run The Physical Demo

1. Go to `Live Demo`.
2. Keep the browser tab open.
3. Bring a hand or object close to the Modulino Distance sensor.
4. Watch the distance value update.
5. The laptop runs face detection and CavaFace.
6. If the face is known, the UI shows a match and the buzzer stays quiet.
7. If the face is unknown, the UI shows an alert and the buzzer sounds.

## Project Hub Section: Code

Link the GitHub repository:

```text
https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu
```

Important files:

```text
firmware/arduino_q_face_guard/arduino_q_face_guard.ino
laptop_ai_guard/run_guard.py
laptop_ai_guard/face_engine.py
laptop_ai_guard/demo_dashboard.html
laptop_ai_guard/enroll_faces.py
```

### Firmware Summary

The firmware initializes the Modulino Distance and Modulino Buzzer modules. It
starts RouterBridge on boot and exposes RPC methods for the laptop app.

The laptop can ask for distance readings:

```text
read_distance_mm
```

It can also command the buzzer:

```text
buzz_unknown
buzz_fault
buzz_test
```

### Python App Summary

`run_guard.py` starts a local browser dashboard, receives camera frames, polls
the UNO Q over RouterBridge, runs recognition, updates the UI, and triggers the
buzzer when needed.

`face_engine.py` contains:

```text
MediaPipe ONNX face detection
CavaFace ONNX preprocessing
ONNX Runtime QNN session setup
Known-face database loading and matching
```

`demo_dashboard.html` contains the UI for:

```text
Live Demo
Known Faces
Add Known Face
```

## Project Hub Section: Schematics

The hardware wiring is intentionally simple because the modules use the Qwiic
chain.

```text
Arduino UNO Q Qwiic connector
        |
        v
Modulino Distance
        |
        v
Modulino Buzzer
```

The UNO Q connects to the laptop over USB.

```text
Laptop USB port <---- USB cable ----> Arduino UNO Q
```

Suggested schematic image:

```text
Laptop running dashboard
USB to Arduino UNO Q
UNO Q Qwiic chain to Modulino Distance and Modulino Buzzer
```

## Project Hub Section: Downloadable Files

Recommended downloadable files:

```text
README.md
SETUP.md
firmware/arduino_q_face_guard/arduino_q_face_guard.ino
laptop_ai_guard/run_guard.py
laptop_ai_guard/demo_dashboard.html
```

Do not upload:

```text
laptop_ai_guard\models\
laptop_ai_guard\known_faces\embeddings.npz
laptop_ai_guard\captures\
laptop_ai_guard\.venv\
.codex_tmp\
```

## Project Hub Section: Troubleshooting

### The Known Faces Screen Shows Offline

Open:

```text
http://127.0.0.1:8765/
```

Do not open:

```text
file:///.../demo_dashboard.html
```

### RouterBridge Method Not Available

The board is probably running a different sketch. Re-upload:

```text
firmware\arduino_q_face_guard\arduino_q_face_guard.ino
```

### Model Fails To Load

Verify:

```text
laptop_ai_guard\models\cavaface\cavaface.onnx
laptop_ai_guard\models\media_pipe\media_pipe.onnx
```

### No Camera Frames

1. Open the local dashboard URL.
2. Allow camera access in the browser.
3. Keep the tab open.
4. Restart the Python app if needed.

### Buzzer Does Not Sound

1. Check the Modulino Buzzer is connected on the Qwiic chain.
2. Reboot the UNO Q.
3. Re-upload the firmware.
4. Run the app again and check the dashboard hardware status.

## Suggested Project Hub Work Attribution

If Project Hub asks for work attribution, use:

```text
This project combines Arduino UNO Q firmware, Modulino sensor input, a local Python dashboard, ONNX Runtime QNN, MediaPipe face detection, and CavaFace embeddings. The source code is available in the linked GitHub repository.
```

## Suggested Closing Paragraph

This project is a compact example of how edge AI can become physical and
interactive. The Arduino UNO Q handles sensor input and actuator output, while
the laptop runs local AI inference on the NPU. The dashboard makes the full
sensor-to-AI-to-hardware flow visible for demonstrations, workshops, and future
experiments.
