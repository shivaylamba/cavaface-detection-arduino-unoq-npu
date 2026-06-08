# Edge AI Workshop Setup Action Plan

This document is for preparing brand-new Snapdragon AI PCs and brand-new Arduino
UNO Q boards for the 4-hour hands-on workshop:

```text
Edge AI Workshop — Snapdragon AI PC + Arduino UNO Q
Gesture Detection End-to-End
```

The workshop setup is different from the face-recognition demo setup. For this
workshop, you do not need MobileFaceNet, CavaFace, MediaPipe ONNX models, known
face databases, or the face-guard firmware.

The workshop focuses on:

```text
Modulino Movement / IMU data -> Edge Impulse training -> deploy to UNO Q -> live inference
```

## Short Answer

Yes, both the laptop and the UNO Q should be prepared before the workshop.

Do not plan to do full first-time setup during the 4-hour workshop. The workshop
time should be used for learning the pipeline, collecting data, training, and
running inference, not for installing tools, updating board images, resolving
USB drivers, or fighting Wi-Fi.

## What Must Be Prepared

Each student pair gets one kit:

```text
1 Snapdragon AI PC
1 Arduino UNO Q
1 Modulino Movement sensor
1 USB-C data cable
1 USB-C hub / power adapter as required
```

For this gesture-detection workshop, the important sensor is the **Modulino
Movement** module. Modulino Distance is not a substitute for this workshop,
because gesture detection needs accelerometer/gyroscope data.

## Laptop Setup Required

Prepare every Snapdragon AI PC with:

```text
Arduino App Lab
Visual Studio Code
VS Code Remote - SSH extension
VS Code Python extension
VS Code C/C++ extension
Google Chrome or Microsoft Edge
Git
Python 3.11 or newer
Arduino CLI, optional but recommended
Arduino IDE, optional but useful as fallback
```

Also verify:

```text
App Lab launches
VS Code launches
VS Code extensions are installed
Browser can access Edge Impulse
Git works from PowerShell
Python works from PowerShell
Laptop can connect to workshop Wi-Fi
```

Recommended laptop checks:

```powershell
python --version
git --version
code --version
arduino-cli version
```

## UNO Q Setup Required

Prepare every UNO Q with:

```text
Latest supported UNO Q Debian image / system image
First-time App Lab setup completed
SSH access verified
Board visible in Arduino App Lab
Board connected to workshop Wi-Fi
Basic Python execution verified on the Linux side
Modulino Movement connected and detected
Basic IMU sensor-read script tested
```

The UNO Q should not be handed to students in a completely uninitialized state.
The first boot, update, and pairing process can take time and can fail because
of Wi-Fi, USB cable, firewall, driver, or account issues.

## Do We Need To Flash The UNO Q Beforehand?

For this workshop, "flash" can mean two different things:

1. Board/system setup
2. Workshop application deployment

### 1. Board/System Setup

Yes, this should be done beforehand.

Every UNO Q should be initialized, updated, visible in App Lab, reachable over
SSH, and able to run a basic script.

### 2. Workshop Application Deployment

Usually, do not pre-deploy the final gesture model.

Students are supposed to collect their own IMU data, train their own Edge
Impulse model, deploy it, and test live inference. If you pre-deploy the final
model, you remove a major learning outcome.

What you should pre-load instead:

```text
Starter scripts
Sensor check script
Data capture script
Example CSV format
Optional backup pre-trained model for emergencies
```

## Recommended Pre-Workshop State

At the start of Block 2, students should be able to:

```text
Open Arduino App Lab
See their UNO Q
Open a terminal / SSH session
Run a basic IMU sensor check
See accel/gyro values changing when they move the module
```

That is the right starting point for a 4-hour workshop.

## What Students Should Still Do During The Workshop

Students should do:

```text
Collect gesture samples
Upload CSV data to Edge Impulse
Create impulse
Train model
Inspect confusion matrix
Deploy trained model back to UNO Q
Run live inference
Debug poor predictions
Optionally trigger buzzer/servo/status output
```

Students should not spend workshop time doing:

```text
Installing App Lab
Installing VS Code
Installing extensions
Updating UNO Q system image
Fixing SSH setup
Fighting captive portal Wi-Fi
Finding USB drivers
Creating Edge Impulse accounts from scratch
```

## Workshop Preparation Timeline

### T-7 Days

Prepare one golden kit:

```text
1 laptop
1 UNO Q
1 Modulino Movement
```

Complete the full workflow once:

```text
App Lab connection
SSH access
Raw IMU read
CSV capture
Edge Impulse upload
Impulse creation
Training
Deployment
Live inference
```

Freeze the working versions of:

```text
Arduino App Lab
VS Code extensions
Python version
Starter scripts
UNO Q system image
Edge Impulse project settings
```

### T-3 Days

Prepare all laptops:

```text
Install App Lab
Install VS Code
Install VS Code extensions
Install Git
Install Python
Install browser
Connect to workshop Wi-Fi
Verify Edge Impulse access
```

Prepare all UNO Q boards:

```text
First boot complete
System updated if required
App Lab detects board
SSH verified
Workshop Wi-Fi configured
Movement sensor check passes
```

### T-1 Day

Run a kit-by-kit check:

```text
Laptop boots
App Lab opens
UNO Q detected
SSH works
Movement sensor connected
IMU values print
Browser opens Edge Impulse
Starter files are present
Power supplies and cables are packed
```

Label each kit:

```text
Kit 01 Laptop + UNO Q 01
Kit 02 Laptop + UNO Q 02
...
```

Keep laptop and UNO Q pairs together after verification.

## Day-Of Setup Plan

Before students enter:

```text
Power on all laptops
Connect each UNO Q
Open App Lab on each laptop
Confirm board appears
Run the basic IMU sensor check on 2-3 random kits
Confirm Wi-Fi has no captive portal
Confirm Edge Impulse is reachable
Keep spare cables and 2-5 spare kits ready
```

During Block 2 setup, students should only need to:

```text
Open App Lab
Connect to their assigned UNO Q
Run the provided sensor-check script
Observe IMU values
```

## Minimum Workshop Laptop Installer

For a workshop-only laptop, use the workshop prerequisite installer. It installs
the laptop-side tools, creates a workspace, and writes a verification report. It
does not install the face demo models or face demo launchers.

Run PowerShell as Administrator:

```powershell
cd C:\Users\Public\Downloads
git clone https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu.git
cd C:\Users\Public\Downloads\cavaface-detection-arduino-unoq-npu

Set-ExecutionPolicy -Scope Process Bypass -Force

.\scripts\Install-WorkshopPrereqs.ps1
```

The script automates:

```text
Git
Python 3.11 ARM64
Google Chrome
Visual Studio Code
Arduino IDE
Arduino CLI
Arduino App Lab ARM64 installer
Node.js LTS
Edge Impulse CLI
VS Code extensions: Remote SSH, Python, C++
Arduino UNO Q core
Arduino_Modulino library
Arduino_RouterBridge library
Local workshop workspace and verification report
```

It creates:

```text
C:\ArduinoEdgeAIWorkshop
C:\ArduinoEdgeAIWorkshop\Verify-WorkshopLaptop.bat
C:\ArduinoEdgeAIWorkshop\WORKSHOP_SETUP_REPORT.txt
Desktop\Verify Edge AI Workshop Laptop.lnk
```

If you want a lighter setup and plan to use only the Edge Impulse web UI, skip
Node.js and Edge Impulse CLI:

```powershell
.\scripts\Install-WorkshopPrereqs.ps1 -SkipNode -SkipEdgeImpulseCli
```

The manual equivalent is below.

Recommended software:

```powershell
winget install --id Git.Git --exact --accept-package-agreements --accept-source-agreements
winget install --id Python.Python.3.11 --exact --architecture arm64 --accept-package-agreements --accept-source-agreements
winget install --id Microsoft.VisualStudioCode --exact --accept-package-agreements --accept-source-agreements
winget install --id Google.Chrome --exact --accept-package-agreements --accept-source-agreements
winget install --id ArduinoSA.IDE.stable --exact --accept-package-agreements --accept-source-agreements
winget install --id ArduinoSA.CLI --exact --accept-package-agreements --accept-source-agreements
winget install --id OpenJS.NodeJS.LTS --exact --accept-package-agreements --accept-source-agreements
```

Install VS Code extensions:

```powershell
code --install-extension ms-vscode-remote.remote-ssh
code --install-extension ms-python.python
code --install-extension ms-vscode.cpptools
```

Install Edge Impulse CLI if you want command-line upload/download workflows:

```powershell
npm install -g edge-impulse-cli
```

Arduino App Lab may need to be installed from Arduino's Windows ARM installer
if it is not available through the package manager.

## What Still Requires Manual Work

The installer cannot fully automate these steps because they require physical
board state, account login, browser permissions, or App Lab UI interaction:

```text
Connect each UNO Q with a USB-C data cable
Open Arduino App Lab
Complete first-time UNO Q onboarding
Apply board image/update prompts if App Lab shows them
Connect UNO Q to the workshop Wi-Fi
Confirm Windows firewall prompts for App Lab/mdns-discovery
Verify SSH access into the UNO Q
Connect the Modulino Movement sensor
Run the instructor-provided raw IMU sensor check
Confirm accelerometer/gyroscope values change when moved
Log into Edge Impulse Studio
Create or join the correct Edge Impulse project
```

These should be done during pre-workshop preparation, not during the 4-hour
session.

## Recommended Workshop Repo Structure

Keep a separate workshop folder from the face demo:

```text
workshop/
  README.md
  scripts/
    sensor_check.py
    capture_imu_csv.py
    live_inference.py
  edge_impulse/
    upload_notes.md
    impulse_settings.md
  examples/
    sample_wave.csv
    sample_circle.csv
    sample_idle.csv
```

The student-facing material should be simple:

```text
1. Connect board
2. Run sensor check
3. Capture data
4. Upload to Edge Impulse
5. Train
6. Deploy
7. Test live inference
```

## Risk Register

| Risk | Mitigation |
| --- | --- |
| App Lab does not detect UNO Q | Pre-test every kit; keep spare USB-C data cables |
| Wi-Fi captive portal breaks UNO Q access | Use a dedicated SSID with no captive portal |
| Edge Impulse accounts slow down onboarding | Create accounts/projects before workshop or use shared prepared accounts |
| Students spend too long collecting data | Provide strict sample count and timing |
| Model performs poorly | Teach it as debugging; keep backup sample dataset |
| UNO Q system update takes too long | Update boards before the day |
| VS Code extension install fails | Install extensions before the day |

## Final Recommendation

For this workshop, prepare **both**:

```text
Laptop: all development tools installed and tested
UNO Q: initialized, updated, App Lab connected, SSH working, IMU sensor check tested
```

Do not pre-train the final student model. Do pre-load starter scripts and keep a
backup dataset/model ready.

The workshop should begin at the point where students can immediately run:

```text
Read raw IMU values
Capture gesture samples
Train in Edge Impulse
Deploy back to UNO Q
Run live inference
```
