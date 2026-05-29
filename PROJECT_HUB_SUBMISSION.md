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
Local AI Face Demo with Arduino UNO Q, Modulino Sensors, and Local NPU Face Recognition
```

Shorter option:

```text
Local AI Face Demo on Arduino UNO Q with Local Face Recognition
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
Laptop screen showing the Local AI Face Demo dashboard
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

The Arduino UNO Q is a great way to connect physical sensing with local AI. In
this project, the board listens to a Modulino Distance sensor and uses a
Modulino Buzzer as the physical output. A Windows ARM64 laptop runs the heavier
computer vision work locally on its NPU.

The demo works like this: when somebody comes close to the distance sensor, the
Arduino UNO Q reports the distance to the laptop. The laptop captures a frame
from the browser camera, detects the face with a MediaPipe ONNX detector, and
then runs CavaFace through ONNX Runtime QNN to create a face embedding. That
embedding is compared with a local known-face database.

If the person is recognized, the dashboard shows a trusted match and the buzzer
stays quiet. If the person is not recognized, the dashboard shows an unknown
face alert and the Arduino UNO Q activates the Modulino Buzzer.

The goal is to make edge AI visible. Instead of showing only code or terminal
logs, the project shows the full path from a real-world sensor event to a local
AI decision and then back to a physical hardware response.

## Project Hub Section: Step-By-Step Tutorial

### Prerequisites

You need:

```text
Arduino UNO Q
Modulino Distance
Modulino Buzzer
Qwiic cables
USB cable
Windows ARM64 laptop with Snapdragon X Elite or compatible NPU
Laptop camera or USB webcam
Arduino IDE
Python 3 for Windows ARM64
```

You also need the local ONNX model assets:

```text
cavaface.onnx
media_pipe.onnx
```

The GitHub repository intentionally does not include those model files because
they are runtime assets. Keep them local unless you have confirmed the license
allows redistribution.

### Step 1: Clone The Demo Repository

Open PowerShell and clone the project:

```powershell
cd C:\Users\Public\Downloads\arduino
git clone https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu.git
cd C:\Users\Public\Downloads\arduino\cavaface-detection-arduino-unoq-npu
```

### Step 2: Create The Python Environment

Use native Windows ARM64 Python so the NPU runtime can load correctly.

```powershell
python -c "import platform; print(platform.machine())"
```

Expected output:

```text
ARM64
```

Create the virtual environment and install the demo dependencies:

```powershell
python -m venv laptop_ai_guard\.venv
.\laptop_ai_guard\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r laptop_ai_guard\requirements-windows-npu.txt
```

### Step 3: Add The CavaFace And MediaPipe Models

Create the model folders:

```powershell
New-Item -ItemType Directory -Force laptop_ai_guard\models\cavaface
New-Item -ItemType Directory -Force laptop_ai_guard\models\media_pipe
```

Copy the model files into these exact paths:

```text
laptop_ai_guard\models\cavaface\cavaface.onnx
laptop_ai_guard\models\media_pipe\media_pipe.onnx
```

The app uses the MediaPipe model to find faces and the CavaFace model to create
512-dimensional face embeddings.

### Step 4: Upload The Arduino UNO Q Firmware

Open Arduino IDE and load this sketch:

```text
firmware\arduino_q_face_guard\arduino_q_face_guard.ino
```

Select the Arduino UNO Q board and the correct port, then upload the sketch.

The firmware exposes the hardware to the laptop app through RouterBridge. The
important methods are:

```text
face_guard_ping
face_guard_status
read_distance_mm
set_threshold_mm
buzz_unknown
buzz_fault
buzz_test
```

### Step 5: Start The Local AI Demo

Run the demo app from the repository root:

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

If the app cannot find the Arduino ADB tool automatically, pass the path:

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

When the app starts, it opens a local browser dashboard:

```text
http://127.0.0.1:8765/
```

Allow camera access and keep the browser tab open.

### Step 6: Check The Live Demo Screen

The `Live Demo` screen shows the main demonstration:

```text
Camera preview
Distance sensor reading
Face match result
Match confidence
Buzzer decision
Sensor-to-AI-to-hardware flow
```

Move your hand toward the Modulino Distance sensor. When the distance goes
below the configured threshold, the app runs face detection and face matching.

### Step 7: Add A Known Face

Open the `Add Known Face` screen in the dashboard.

Enter a demo name, choose the number of samples, face the camera, and start the
capture. The app stores CavaFace embeddings in:

```text
laptop_ai_guard\known_faces\embeddings.npz
```

This does not retrain CavaFace. The model stays fixed. The app simply adds new
local face templates to the known-face database.

### Step 8: View The Known Faces Database

Open the `Known Faces` screen. It shows the names currently stored in the local
database and the number of embeddings saved for each name.

This makes the demo easier to explain because the audience can see who the app
is expected to recognize before the physical interaction starts.

### Step 9: Run The Physical Demo

Now run the full interaction:

```text
1. Open the Live Demo screen.
2. Keep the camera tab open.
3. Bring a hand or object close to the Modulino Distance sensor.
4. Watch the dashboard show that the sensor triggered recognition.
5. Let the app run MediaPipe face detection and CavaFace matching locally.
6. If the face is known, the dashboard shows a match and the buzzer remains off.
7. If the face is unknown, the dashboard shows an alert and the buzzer sounds.
```

### How The System Fits Together

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

### Why Is This Important?

This demo shows how small hardware interactions can become intelligent without
sending camera frames to the cloud. The Arduino UNO Q handles the real-world
sensor and buzzer interaction. The laptop runs the AI models locally using the
NPU. The browser dashboard makes the process understandable for people who do
not want to read logs or inspect code.

That makes the project a useful template for workshops, physical computing
demos, smart access experiments, and edge AI prototypes where sensor input,
local inference, and actuator output need to work together.

### Privacy And Safety Notes

This is a prototype demo, not a production security system.

Important limitations:

```text
It does not include liveness detection.
It does not prove legal identity.
It stores local biometric embeddings.
It should not be used for security-critical decisions.
It should only enroll people with consent.
```

For public demos, use generic demo names, avoid saving unnecessary face images,
and explain that the matching in this prototype happens locally.

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
