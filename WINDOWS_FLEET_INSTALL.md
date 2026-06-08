# Windows Fleet Install Guide

This guide is for setting up the full Arduino UNO Q local AI face demo on many
Windows Snapdragon laptops.

The installer automates:

- Git clone/update of the demo repo
- Python 3.11 ARM64 install through `winget`
- Python virtual environment setup
- ONNX Runtime QNN dependency install
- Arduino IDE install through `winget`
- Arduino CLI install through `winget`
- Arduino App Lab ARM64 installer download and install
- UNO Q board core and required Arduino libraries
- Runtime model/database asset copy
- Runtime model/database asset download from GitHub Releases
- Firmware compile, and optional firmware upload
- One-click desktop launcher creation

Arduino App Lab is not currently exposed as a `winget` package. The installer
downloads the Windows ARM64 NSIS installer from Arduino's software download
endpoint. The official Windows setup instructions are here:

```text
https://docs.arduino.cc/software/app-lab/setup/windows/
https://www.arduino.cc/en/software
```

## 1. Create Or Publish The Asset Bundle Once

Run this on the known-good laptop where the demo already works and the ignored
model files are present:

```powershell
cd C:\Users\Public\Downloads\arduino\arduino-face-detection

powershell.exe -ExecutionPolicy Bypass -File .\scripts\Prepare-WindowsDemoAssets.ps1 `
  -OutputPath C:\ArduinoFaceDemoAssets `
  -IncludeKnownFaces `
  -Zip
```

Copy either of these to a USB drive or network share:

```text
C:\ArduinoFaceDemoAssets
C:\ArduinoFaceDemoAssets.zip
```

If you do not want to copy biometric known-face embeddings, omit
`-IncludeKnownFaces`. The model files will still be copied, and staff can enroll
known people from the dashboard on each laptop.

Expected bundle contents:

```text
laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx
laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx.data
laptop_ai_guard\models\media_pipe\media_pipe.onnx
laptop_ai_guard\models\cavaface\cavaface.onnx                 optional
laptop_ai_guard\known_faces_mobilefacenet\embeddings.npz      optional
laptop_ai_guard\known_faces\embeddings.npz                    optional
MANIFEST.txt
```

### Option A: Upload The Asset Bundle To GitHub Releases

This is the recommended path for installing many laptops without USB.

Do not commit the ONNX models directly to git. The CavaFace model is over the
normal GitHub file-size limit, and large binary model files are better handled
as Release assets.

If you want the installer to download models from GitHub automatically, publish
the zip as a release asset named:

```text
ArduinoFaceDemoAssets.zip
```

You can do that manually from the GitHub Releases UI, or with GitHub CLI:

```powershell
winget install --id GitHub.cli --exact
gh auth login

.\scripts\Publish-WindowsDemoAssets.ps1
```

By default, the publisher includes the model files but not known-face databases.
Known-face databases contain biometric embeddings. Only include them if you are
intentionally distributing those exact enrolled identities:

```powershell
.\scripts\Publish-WindowsDemoAssets.ps1 `
  -IncludeKnownFaces `
  -PublicBiometricDataAcknowledged
```

After the asset is uploaded, the fleet installer can download it from:

```text
https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu/releases/latest/download/ArduinoFaceDemoAssets.zip
```

### Option B: Use USB Or Network Share

Use the folder or zip from `Prepare-WindowsDemoAssets.ps1` if the laptops will
not have reliable internet or if the assets should not be hosted on GitHub.

## 2. Run The Installer On Each Laptop

Open PowerShell as Administrator.

If the asset bundle is uploaded to GitHub Releases, you do not need
`-AssetsPath`:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force

cd C:\Path\To\Downloaded\Repo

.\scripts\Install-WindowsDemo.ps1 `
  -InstallRoot C:\ArduinoFaceDemo `
  -RecognitionModel mobilefacenet
```

If the release is private, set a token before running:

```powershell
$env:GITHUB_TOKEN = "YOUR_TOKEN_WITH_RELEASE_DOWNLOAD_ACCESS"
```

If your asset bundle is a folder on a USB drive:

```powershell
.\scripts\Install-WindowsDemo.ps1 `
  -InstallRoot C:\ArduinoFaceDemo `
  -AssetsPath E:\ArduinoFaceDemoAssets `
  -RecognitionModel mobilefacenet
```

If you want to compile and upload the UNO Q firmware during install:

```powershell
.\scripts\Install-WindowsDemo.ps1 `
  -InstallRoot C:\ArduinoFaceDemo `
  -RecognitionModel mobilefacenet `
  -UploadFirmware `
  -ArduinoPort COM3
```

If the UNO Q port differs, change `COM3`.

## 3. What The Installer Creates

Default repo location:

```text
C:\ArduinoFaceDemo\cavaface-detection-arduino-unoq-npu
```

One-click launchers:

```text
C:\ArduinoFaceDemo\cavaface-detection-arduino-unoq-npu\Run-Demo.bat
C:\ArduinoFaceDemo\cavaface-detection-arduino-unoq-npu\Run-Demo.ps1
C:\ArduinoFaceDemo\cavaface-detection-arduino-unoq-npu\Enroll-KnownFace.bat
Desktop\Local AI Face Demo.lnk
```

The dashboard opens at:

```text
http://127.0.0.1:8765/
```

## 4. Run The Demo

Double-click:

```text
Local AI Face Demo
```

or run:

```powershell
C:\ArduinoFaceDemo\cavaface-detection-arduino-unoq-npu\Run-Demo.bat
```

Allow camera access in the browser tab. Keep the tab open.

## 5. Enroll Known Faces

Use the dashboard `Add Known Face` tab, or double-click:

```text
Enroll-KnownFace.bat
```

Enrollment does not retrain the model. It captures face samples, creates
MobileFaceNet embeddings, and appends them to:

```text
laptop_ai_guard\known_faces_mobilefacenet\embeddings.npz
```

## 6. Installer Options

Common options:

```powershell
-AssetsPath E:\ArduinoFaceDemoAssets
-AssetsUrl https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu/releases/latest/download/ArduinoFaceDemoAssets.zip
-InstallRoot C:\ArduinoFaceDemo
-RecognitionModel mobilefacenet
-RecognitionModel cavaface
-HardwareSource routerbridge
-HardwareSource serial
-UploadFirmware
-ArduinoPort COM3
-SkipSmokeTest
-SkipAppLab
-SkipArduinoIde
-SkipFirmwareCompile
-NoDesktopShortcuts
```

For a faster rerun on a laptop that already has system tools installed:

```powershell
.\scripts\Install-WindowsDemo.ps1 `
  -InstallRoot C:\ArduinoFaceDemo `
  -AssetsPath E:\ArduinoFaceDemoAssets `
  -SkipPythonInstall `
  -SkipGitInstall `
  -SkipChromeInstall `
  -SkipArduinoIde `
  -SkipAppLab
```

## 7. Troubleshooting

### App Lab Is Not Installed

Arduino App Lab is installed from Arduino's ARM64 NSIS installer. If the silent
installer fails, install it manually from:

```text
https://www.arduino.cc/en/software
```

Choose the Windows 11 ARM installer.

### Model Smoke Test Fails

Check that these files exist:

```text
laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx
laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx.data
laptop_ai_guard\models\media_pipe\media_pipe.onnx
```

If they are missing, recreate the asset bundle from the working laptop and rerun
the installer with `-AssetsPath`.

### RouterBridge Method Not Available

Upload the firmware:

```text
firmware\arduino_q_face_guard\arduino_q_face_guard.ino
```

The laptop app expects methods such as:

```text
face_guard_ping
face_guard_status
read_distance_mm
buzz_unknown
```

### UNO Q Is Not Detected

Open Arduino App Lab once, connect the board with a USB-C data cable, and allow
Windows Defender access for `mdns-discovery.exe` if prompted. Arduino documents
this in the Windows App Lab setup guide:

```text
https://docs.arduino.cc/software/app-lab/setup/windows/
```
