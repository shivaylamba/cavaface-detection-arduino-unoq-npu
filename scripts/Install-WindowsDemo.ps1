#requires -Version 5.1
<#
.SYNOPSIS
Installs the Arduino UNO Q local AI face demo on a Windows ARM64 laptop.

.DESCRIPTION
This script is intended for repeatable setup across demo laptops. It installs
desktop dependencies, clones or updates the GitHub repo, creates the Python
virtual environment, copies local model/database assets from a prepared bundle,
installs Arduino CLI/IDE/App Lab support, optionally compiles/uploads firmware,
and creates one-click demo launchers.

Run from an elevated PowerShell when possible.
#>
[CmdletBinding()]
param(
    [string]$InstallRoot = "C:\ArduinoFaceDemo",
    [string]$RepoUrl = "https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu.git",
    [string]$Branch = "main",
    [string]$AssetsPath = "",
    [string]$AssetsUrl = "https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu/releases/latest/download/ArduinoFaceDemoAssets.zip",
    [string]$GitHubToken = $env:GITHUB_TOKEN,
    [ValidateSet("mobilefacenet", "cavaface")]
    [string]$RecognitionModel = "mobilefacenet",
    [ValidateSet("routerbridge", "serial")]
    [string]$HardwareSource = "routerbridge",
    [string]$ArduinoPort = "auto",
    [string]$Fqbn = "arduino:zephyr:unoq",
    [int]$ProximityThresholdMm = 700,
    [double]$FaceThreshold = 0.50,
    [switch]$UseCurrentDirectory,
    [switch]$SkipWinget,
    [switch]$SkipPythonInstall,
    [switch]$SkipGitInstall,
    [switch]$SkipChromeInstall,
    [switch]$SkipArduinoIde,
    [switch]$SkipArduinoCli,
    [switch]$SkipAppLab,
    [switch]$SkipArduinoPackages,
    [switch]$SkipFirmwareCompile,
    [switch]$UploadFirmware,
    [switch]$SkipAssetDownload,
    [switch]$SkipSmokeTest,
    [switch]$NoDesktopShortcuts,
    [switch]$Force,
    [string]$AppLabArm64Url = "https://downloads.arduino.cc/AppLab/Stable/ArduinoAppLab_0.8.0_Windows_arm64_installer.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:Warnings = New-Object System.Collections.Generic.List[string]
$script:LastExternalExitCode = 0

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "    OK  $Message" -ForegroundColor Green
}

function Add-SetupWarning {
    param([string]$Message)
    $script:Warnings.Add($Message) | Out-Null
    Write-Host "    WARN $Message" -ForegroundColor Yellow
}

function Invoke-External {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$false)][string[]]$Arguments = @(),
        [switch]$AllowFailure
    )
    Write-Host "    > $FilePath $($Arguments -join ' ')" -ForegroundColor DarkGray
    & $FilePath @Arguments
    $exit = $LASTEXITCODE
    $script:LastExternalExitCode = $exit
    if ($exit -ne 0 -and -not $AllowFailure) {
        throw "Command failed with exit code $exit`: $FilePath $($Arguments -join ' ')"
    }
    if ($AllowFailure) {
        return $exit
    }
}

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Install-WingetPackage {
    param(
        [string]$Id,
        [string]$DisplayName,
        [string]$Architecture = ""
    )
    if ($SkipWinget) {
        Add-SetupWarning "Skipping winget install for $DisplayName."
        return
    }
    if (-not (Test-CommandExists "winget")) {
        Add-SetupWarning "winget is not available. Install $DisplayName manually."
        return
    }

    $args = @(
        "install", "--id", $Id, "--exact",
        "--accept-package-agreements", "--accept-source-agreements",
        "--silent"
    )
    if ($Architecture) {
        $args += @("--architecture", $Architecture)
    }

    $exit = Invoke-External -FilePath "winget" -Arguments $args -AllowFailure
    if ($exit -eq 0) {
        Write-Ok "$DisplayName installed or already present."
    } else {
        Add-SetupWarning "winget could not install $DisplayName. Continue after installing it manually."
    }
    Refresh-ProcessPath
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

function Get-RepoNameFromUrl {
    param([string]$Url)
    $leaf = Split-Path $Url -Leaf
    if ($leaf.EndsWith(".git")) {
        return $leaf.Substring(0, $leaf.Length - 4)
    }
    return $leaf
}

function Get-TargetRepoPath {
    if ($UseCurrentDirectory) {
        return (Resolve-Path ".").Path
    }
    $repoName = Get-RepoNameFromUrl -Url $RepoUrl
    return (Join-Path $InstallRoot $repoName)
}

function Ensure-Repo {
    param([string]$RepoDir)
    Write-Step "Preparing repository"
    if ($UseCurrentDirectory) {
        if (-not (Test-Path (Join-Path $RepoDir "laptop_ai_guard\run_guard.py"))) {
            throw "-UseCurrentDirectory was set, but $RepoDir does not look like the demo repo."
        }
        Write-Ok "Using current repository without git update: $RepoDir"
        return
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $RepoDir -Parent) | Out-Null

    if ((Test-Path (Join-Path $RepoDir ".git")) -and -not $Force) {
        Write-Host "    Updating existing repo at $RepoDir"
        Invoke-External -FilePath "git" -Arguments @("-C", $RepoDir, "fetch", "origin")
        Invoke-External -FilePath "git" -Arguments @("-C", $RepoDir, "checkout", $Branch)
        $exit = Invoke-External -FilePath "git" -Arguments @("-C", $RepoDir, "pull", "--ff-only", "origin", $Branch) -AllowFailure
        if ($exit -ne 0) {
            Add-SetupWarning "Could not fast-forward the repo. Resolve local changes or rerun with -Force into a clean folder."
        }
    } elseif (Test-Path $RepoDir) {
        if (-not $Force) {
            throw "$RepoDir exists but is not a git repo. Use -Force or choose a different -InstallRoot."
        }
        Add-SetupWarning "Removing non-git install directory because -Force was set: $RepoDir"
        Remove-Item -LiteralPath $RepoDir -Recurse -Force
        Invoke-External -FilePath "git" -Arguments @("clone", "--branch", $Branch, $RepoUrl, $RepoDir)
    } else {
        Invoke-External -FilePath "git" -Arguments @("clone", "--branch", $Branch, $RepoUrl, $RepoDir)
    }
    Write-Ok "Repository ready: $RepoDir"
}

function Get-AssetsRoot {
    param([string]$RepoDir)
    if ($AssetsPath) {
        return (Resolve-Path $AssetsPath).Path
    }
    if ($SkipAssetDownload) {
        return ""
    }
    if (-not $AssetsUrl) {
        return ""
    }

    Write-Step "Downloading runtime assets"
    $assetRoot = Join-Path (Split-Path $RepoDir -Parent) "_runtime_assets"
    $zipPath = Join-Path (Split-Path $RepoDir -Parent) "ArduinoFaceDemoAssets.zip"
    if (Test-Path $assetRoot) {
        Remove-Item -LiteralPath $assetRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $assetRoot | Out-Null

    $headers = @{}
    if ($GitHubToken) {
        $headers["Authorization"] = "Bearer $GitHubToken"
        $headers["Accept"] = "application/octet-stream"
    }
    Write-Host "    Downloading $AssetsUrl"
    try {
        if ($headers.Count -gt 0) {
            Invoke-WebRequest -Uri $AssetsUrl -Headers $headers -OutFile $zipPath -UseBasicParsing
        } else {
            Invoke-WebRequest -Uri $AssetsUrl -OutFile $zipPath -UseBasicParsing
        }
    } catch {
        throw "Could not download runtime assets from $AssetsUrl. Upload ArduinoFaceDemoAssets.zip to a GitHub Release, pass -AssetsPath, or rerun with a valid -AssetsUrl. Details: $($_.Exception.Message)"
    }

    Expand-Archive -LiteralPath $zipPath -DestinationPath $assetRoot -Force
    Write-Ok "Runtime assets downloaded and expanded to $assetRoot"
    return $assetRoot
}

function Get-PythonCandidate {
    $candidates = @()
    if (Test-CommandExists "py") {
        $candidates += [pscustomobject]@{ Exe = "py"; Args = @("-3.11") }
    }
    foreach ($base in @($env:LOCALAPPDATA, $env:ProgramFiles)) {
        if (-not $base) { continue }
        $paths = Get-ChildItem -Path $base -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "Python311|Python312|Python313|Python" } |
            Select-Object -First 8
        foreach ($p in $paths) {
            $candidates += [pscustomobject]@{ Exe = $p.FullName; Args = @() }
        }
    }
    if (Test-CommandExists "python") {
        $candidates += [pscustomobject]@{ Exe = "python"; Args = @() }
    }

    foreach ($candidate in $candidates) {
        try {
            $out = & $candidate.Exe @($candidate.Args + @("-c", "import platform,sys; print(sys.version.split()[0]); print(platform.machine())")) 2>$null
            if ($LASTEXITCODE -eq 0 -and $out.Count -ge 2) {
                return [pscustomobject]@{
                    Exe = $candidate.Exe
                    Args = $candidate.Args
                    Version = [string]$out[0]
                    Machine = [string]$out[1]
                }
            }
        } catch {
            continue
        }
    }
    return $null
}

function Invoke-Python {
    param(
        [Parameter(Mandatory=$true)]$Python,
        [string[]]$Arguments
    )
    Invoke-External -FilePath $Python.Exe -Arguments @($Python.Args + $Arguments)
}

function Ensure-PythonVenv {
    param([string]$RepoDir)
    Write-Step "Preparing Python ARM64 environment"
    $python = Get-PythonCandidate
    if (-not $python) {
        throw "Python was not found after installation. Install native Python 3.11 ARM64 and rerun."
    }
    Write-Ok "Python $($python.Version), platform $($python.Machine)"
    if ($python.Machine -ne "ARM64") {
        Add-SetupWarning "Python is reporting '$($python.Machine)', not ARM64. QNN/NPU wheels may not install correctly."
    }

    $venvDir = Join-Path $RepoDir "laptop_ai_guard\.venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Invoke-Python -Python $python -Arguments @("-m", "venv", $venvDir)
    }
    Invoke-External -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-External -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", (Join-Path $RepoDir "laptop_ai_guard\requirements-windows-npu.txt"))
    Write-Ok "Python virtual environment ready."
    return $venvPython
}

function Find-AssetFile {
    param(
        [string]$Root,
        [string[]]$RelativeCandidates,
        [string]$FileName
    )
    if (-not $Root) { return $null }
    if (-not (Test-Path $Root)) { return $null }

    foreach ($rel in $RelativeCandidates) {
        $candidate = Join-Path $Root $rel
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    $found = Get-ChildItem -Path $Root -Recurse -File -Filter $FileName -ErrorAction SilentlyContinue |
        Sort-Object FullName |
        Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

function Copy-AssetIfFound {
    param(
        [string]$AssetsRoot,
        [string[]]$RelativeCandidates,
        [string]$FileName,
        [string]$Destination,
        [int64]$MinimumBytes,
        [switch]$Required
    )
    $source = Find-AssetFile -Root $AssetsRoot -RelativeCandidates $RelativeCandidates -FileName $FileName
    if ($source) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
        Copy-Item -LiteralPath $source -Destination $Destination -Force
        $size = (Get-Item -LiteralPath $Destination).Length
        if ($size -lt $MinimumBytes) {
            throw "Copied $Destination but it is only $size bytes. The model/database asset looks incomplete."
        }
        Write-Ok "Copied $(Split-Path $Destination -Leaf) from $source"
        return $true
    }

    if ($Required) {
        throw "Required asset not found: $FileName. Provide -AssetsPath pointing at the prepared demo-assets folder."
    }
    Add-SetupWarning "Optional asset not found: $FileName"
    return $false
}

function Ensure-Assets {
    param([string]$RepoDir)
    Write-Step "Copying model and known-face assets"
    $root = ""
    if ($AssetsPath) {
        $root = (Resolve-Path $AssetsPath).Path
        Write-Host "    Asset bundle: $root"
    } else {
        Add-SetupWarning "No -AssetsPath supplied. The script will only validate existing local assets."
    }

    $mobileModel = Join-Path $RepoDir "laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx"
    $mobileData = Join-Path $RepoDir "laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx.data"
    $mediaModel = Join-Path $RepoDir "laptop_ai_guard\models\media_pipe\media_pipe.onnx"
    $cavaModel = Join-Path $RepoDir "laptop_ai_guard\models\cavaface\cavaface.onnx"
    $mobileDb = Join-Path $RepoDir "laptop_ai_guard\known_faces_mobilefacenet\embeddings.npz"
    $cavaDb = Join-Path $RepoDir "laptop_ai_guard\known_faces\embeddings.npz"

    if ($root) {
        Copy-AssetIfFound -AssetsRoot $root -FileName "mobilefacenet.onnx" -Destination $mobileModel -MinimumBytes 1000000 -Required:($RecognitionModel -eq "mobilefacenet") -RelativeCandidates @(
            "laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx",
            "models\mobilefacenet\mobilefacenet.onnx"
        ) | Out-Null
        Copy-AssetIfFound -AssetsRoot $root -FileName "mobilefacenet.onnx.data" -Destination $mobileData -MinimumBytes 1000000 -Required:($RecognitionModel -eq "mobilefacenet") -RelativeCandidates @(
            "laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx.data",
            "models\mobilefacenet\mobilefacenet.onnx.data"
        ) | Out-Null
        Copy-AssetIfFound -AssetsRoot $root -FileName "media_pipe.onnx" -Destination $mediaModel -MinimumBytes 100000 -Required -RelativeCandidates @(
            "laptop_ai_guard\models\media_pipe\media_pipe.onnx",
            "models\media_pipe\media_pipe.onnx"
        ) | Out-Null
        Copy-AssetIfFound -AssetsRoot $root -FileName "cavaface.onnx" -Destination $cavaModel -MinimumBytes 10000000 -Required:($RecognitionModel -eq "cavaface") -RelativeCandidates @(
            "laptop_ai_guard\models\cavaface\cavaface.onnx",
            "models\cavaface\cavaface.onnx"
        ) | Out-Null
        Copy-AssetIfFound -AssetsRoot $root -FileName "embeddings.npz" -Destination $mobileDb -MinimumBytes 100 -RelativeCandidates @(
            "laptop_ai_guard\known_faces_mobilefacenet\embeddings.npz",
            "known_faces_mobilefacenet\embeddings.npz"
        ) | Out-Null
        Copy-AssetIfFound -AssetsRoot $root -FileName "embeddings.npz" -Destination $cavaDb -MinimumBytes 100 -RelativeCandidates @(
            "laptop_ai_guard\known_faces\embeddings.npz",
            "known_faces\embeddings.npz"
        ) | Out-Null
    }

    $required = @($mediaModel)
    if ($RecognitionModel -eq "mobilefacenet") {
        $required += @($mobileModel, $mobileData)
    } else {
        $required += @($cavaModel)
    }
    foreach ($file in $required) {
        if (-not (Test-Path $file)) {
            throw "Missing required runtime asset: $file"
        }
        Write-Ok "Validated asset: $file"
    }
    if (-not (Test-Path $mobileDb) -and $RecognitionModel -eq "mobilefacenet") {
        Add-SetupWarning "No MobileFaceNet known-face DB found. Enroll known faces from the dashboard before demoing known matches."
    }
    if (-not (Test-Path $cavaDb) -and $RecognitionModel -eq "cavaface") {
        Add-SetupWarning "No CavaFace known-face DB found. Enroll known faces from the dashboard before demoing known matches."
    }
}

function Find-ArduinoCli {
    if (Test-CommandExists "arduino-cli") { return "arduino-cli" }
    $candidates = @(
        "$env:ProgramFiles\Arduino CLI\arduino-cli.exe",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\ArduinoSA.CLI_Microsoft.Winget.Source_8wekyb3d8bbwe\arduino-cli.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    $found = Get-ChildItem -Path $env:LOCALAPPDATA,$env:ProgramFiles -Recurse -Filter arduino-cli.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

function Find-Adb {
    $roots = @(
        (Join-Path $env:LOCALAPPDATA "Arduino15\packages\arduino\tools\adb"),
        (Join-Path $env:USERPROFILE "AppData\Local\Arduino15\packages\arduino\tools\adb")
    )
    foreach ($root in $roots) {
        if (Test-Path $root) {
            $adb = Get-ChildItem -Path $root -Recurse -Filter adb.exe -ErrorAction SilentlyContinue |
                Sort-Object FullName -Descending |
                Select-Object -First 1
            if ($adb) { return $adb.FullName }
        }
    }
    return $null
}

function Install-AppLab {
    if ($SkipAppLab) { return }
    Write-Step "Installing Arduino App Lab"
    $installers = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs","$env:ProgramFiles" -Recurse -Filter "*App Lab*.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($installers) {
        Write-Ok "Arduino App Lab appears to be installed."
        return
    }
    $download = Join-Path $env:TEMP "ArduinoAppLab_Windows_arm64_installer.exe"
    Write-Host "    Downloading $AppLabArm64Url"
    Invoke-WebRequest -Uri $AppLabArm64Url -OutFile $download -UseBasicParsing
    $process = Start-Process -FilePath $download -ArgumentList "/S" -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        Add-SetupWarning "Arduino App Lab installer exited with code $($process.ExitCode). Install manually from https://www.arduino.cc/en/software if needed."
    } else {
        Write-Ok "Arduino App Lab installer completed."
    }
}

function Ensure-ArduinoPackages {
    param([string]$RepoDir)
    if ($SkipArduinoCli) { return $null }
    Write-Step "Preparing Arduino CLI, UNO Q core, and libraries"
    $cli = Find-ArduinoCli
    if (-not $cli) {
        Add-SetupWarning "arduino-cli was not found. Firmware compile/upload will be skipped."
        return $null
    }

    if (-not $SkipArduinoPackages) {
        Invoke-External -FilePath $cli -Arguments @("config", "init") -AllowFailure | Out-Null
        Invoke-External -FilePath $cli -Arguments @("core", "update-index")
        Invoke-External -FilePath $cli -Arguments @("core", "install", "arduino:zephyr")
        Invoke-External -FilePath $cli -Arguments @("lib", "install", "Arduino_Modulino") -AllowFailure | Out-Null
        Invoke-External -FilePath $cli -Arguments @("lib", "install", "Arduino_RouterBridge") -AllowFailure | Out-Null
    }

    if (-not $SkipFirmwareCompile) {
        Invoke-External -FilePath $cli -Arguments @("compile", "--fqbn", $Fqbn, (Join-Path $RepoDir "firmware\arduino_q_face_guard"))
        Write-Ok "Firmware compiled."
    }

    if ($UploadFirmware) {
        $port = $ArduinoPort
        if ($port -eq "auto") {
            $boardList = & $cli board list 2>$null
            $portLine = $boardList | Where-Object { $_ -match "COM\d+" } | Select-Object -First 1
            if ($portLine -match "(COM\d+)") {
                $port = $Matches[1]
            }
        }
        if (-not $port -or $port -eq "auto") {
            throw "Could not auto-detect Arduino COM port. Rerun with -ArduinoPort COM3 or upload through Arduino IDE."
        }
        Invoke-External -FilePath $cli -Arguments @("upload", "-p", $port, "--fqbn", $Fqbn, (Join-Path $RepoDir "firmware\arduino_q_face_guard"))
        Write-Ok "Firmware upload requested on $port."
    }
    return $cli
}

function Write-Launchers {
    param([string]$RepoDir)
    Write-Step "Creating launchers"
    $runPs1 = Join-Path $RepoDir "Run-Demo.ps1"
    $runBat = Join-Path $RepoDir "Run-Demo.bat"
    $enrollBat = Join-Path $RepoDir "Enroll-KnownFace.bat"
    $recognition = $RecognitionModel
    $hardware = $HardwareSource
    $threshold = [string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0:0.00}", $FaceThreshold)

    $runContent = @"
`$ErrorActionPreference = "Stop"
`$RepoRoot = Split-Path -Parent `$MyInvocation.MyCommand.Path
Set-Location -LiteralPath `$RepoRoot
`$python = Join-Path `$RepoRoot "laptop_ai_guard\.venv\Scripts\python.exe"
if (-not (Test-Path `$python)) { throw "Python venv not found. Run scripts\Install-WindowsDemo.ps1 first." }
`$args = @(
  "-u", "laptop_ai_guard\run_guard.py",
  "--hardware-source", "$hardware",
  "--camera-source", "browser",
  "--browser-timeout", "180",
  "--recognition-model", "$recognition",
  "--face-detector", "mediapipe",
  "--model-runtime", "onnx-qnn",
  "--threshold", "$threshold",
  "--proximity-threshold-mm", "$ProximityThresholdMm",
  "--trigger-cooldown", "2",
  "--poll-interval", "0.25"
)
if ("$hardware" -eq "routerbridge") {
  `$adb = Get-ChildItem -Path "`$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\*\adb.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
  if (`$adb) { `$args += @("--adb-path", `$adb.FullName) }
}
& `$python @args
Read-Host "Press Enter to close"
"@
    Set-Content -LiteralPath $runPs1 -Value $runContent -Encoding UTF8

    $batContent = @"
@echo off
cd /d "%~dp0"
powershell.exe -NoExit -ExecutionPolicy Bypass -File "%~dp0Run-Demo.ps1"
"@
    Set-Content -LiteralPath $runBat -Value $batContent -Encoding ASCII

    $enrollContent = @"
@echo off
cd /d "%~dp0"
set /p PERSON_NAME=Enter name to enroll: 
if "%PERSON_NAME%"=="" exit /b 1
"%~dp0laptop_ai_guard\.venv\Scripts\python.exe" laptop_ai_guard\enroll_faces.py --camera --samples 8 --recognition-model $recognition --face-detector mediapipe --model-runtime onnx-qnn --name "%PERSON_NAME%"
pause
"@
    Set-Content -LiteralPath $enrollBat -Value $enrollContent -Encoding ASCII

    if (-not $NoDesktopShortcuts) {
        $desktop = [Environment]::GetFolderPath("Desktop")
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path $desktop "Local AI Face Demo.lnk"))
        $shortcut.TargetPath = $runBat
        $shortcut.WorkingDirectory = $RepoDir
        $shortcut.Description = "Start the Arduino UNO Q local AI face demo"
        $shortcut.Save()
    }
    Write-Ok "Launchers written to $RepoDir"
}

function Run-SmokeTest {
    param([string]$RepoDir, [string]$VenvPython)
    if ($SkipSmokeTest) { return }
    Write-Step "Running smoke test"
    Invoke-External -FilePath $VenvPython -Arguments @("-m", "py_compile", (Join-Path $RepoDir "laptop_ai_guard\face_engine.py"), (Join-Path $RepoDir "laptop_ai_guard\run_guard.py"), (Join-Path $RepoDir "laptop_ai_guard\enroll_faces.py"))

    $testScript = @"
from pathlib import Path
import sys, numpy as np
sys.path.insert(0, str(Path("laptop_ai_guard").resolve()))
from face_engine import CavaFaceRecognizer, MobileFaceNetRecognizer, FaceDatabase
model = "$RecognitionModel"
cls = MobileFaceNetRecognizer if model == "mobilefacenet" else CavaFaceRecognizer
r = cls(face_detector="mediapipe", model_runtime="onnx-qnn")
emb = r.runtime.predict_features(np.full((160, 160, 3), 127, dtype=np.uint8))
print("runtime:", r.runtime_description)
print("embedding:", emb.shape, "norm:", float(np.linalg.norm(emb)))
db_path = "laptop_ai_guard/known_faces_mobilefacenet/embeddings.npz" if model == "mobilefacenet" else "laptop_ai_guard/known_faces/embeddings.npz"
db = FaceDatabase.load(db_path)
print("db:", db.embeddings.shape, sorted(set(db.names)))
"@
    $tmp = Join-Path $env:TEMP "face_demo_smoke_test.py"
    Set-Content -LiteralPath $tmp -Value $testScript -Encoding UTF8
    Push-Location $RepoDir
    try {
        Invoke-External -FilePath $VenvPython -Arguments @($tmp)
    } finally {
        Pop-Location
    }
    Write-Ok "Smoke test completed."
}

Write-Host "Arduino UNO Q Local AI Face Demo installer" -ForegroundColor White
Write-Host "Current user: $env:USERNAME"
Write-Host "Admin shell:  $(Test-IsAdmin)"

if (-not (Test-IsAdmin)) {
    Add-SetupWarning "This is not an elevated PowerShell. winget and silent installers may prompt or fail."
}

Write-Step "Installing desktop tools"
if (-not $SkipPythonInstall) { Install-WingetPackage -Id "Python.Python.3.11" -DisplayName "Python 3.11" -Architecture "arm64" }
if (-not $SkipGitInstall) { Install-WingetPackage -Id "Git.Git" -DisplayName "Git" }
if (-not $SkipChromeInstall) { Install-WingetPackage -Id "Google.Chrome" -DisplayName "Google Chrome" }
if (-not $SkipArduinoIde) { Install-WingetPackage -Id "ArduinoSA.IDE.stable" -DisplayName "Arduino IDE" }
if (-not $SkipArduinoCli) { Install-WingetPackage -Id "ArduinoSA.CLI" -DisplayName "Arduino CLI" }
Install-AppLab

Refresh-ProcessPath
if (-not (Test-CommandExists "git")) {
    throw "Git is still not available. Install Git and rerun."
}

$repoDir = Get-TargetRepoPath
Ensure-Repo -RepoDir $repoDir
$venvPython = Ensure-PythonVenv -RepoDir $repoDir
$resolvedAssetsPath = Get-AssetsRoot -RepoDir $repoDir
$AssetsPath = $resolvedAssetsPath
Ensure-Assets -RepoDir $repoDir
$arduinoCli = Ensure-ArduinoPackages -RepoDir $repoDir
Write-Launchers -RepoDir $repoDir
Run-SmokeTest -RepoDir $repoDir -VenvPython $venvPython

Write-Step "Setup complete"
Write-Host "Repo:       $repoDir"
Write-Host "Launcher:   $(Join-Path $repoDir 'Run-Demo.bat')"
Write-Host "Dashboard:  http://127.0.0.1:8765/"
$adb = Find-Adb
if ($adb) {
    Write-Host "ADB:        $adb"
} else {
    Add-SetupWarning "ADB was not found yet. It is normally installed with the Arduino UNO Q core."
}
if ($script:Warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Warnings to review:" -ForegroundColor Yellow
    foreach ($w in $script:Warnings) {
        Write-Host " - $w" -ForegroundColor Yellow
    }
}
