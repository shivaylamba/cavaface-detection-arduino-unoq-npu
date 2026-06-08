#requires -Version 5.1
<#
.SYNOPSIS
Installs laptop prerequisites for the Edge AI Workshop with Snapdragon AI PC and Arduino UNO Q.

.DESCRIPTION
Use this on each fresh Windows Snapdragon laptop before the workshop. It installs
the development tools, Arduino tools, VS Code extensions, App Lab, optional Edge
Impulse CLI, and writes a setup report. It does not flash the UNO Q base image
or complete App Lab onboarding because those steps require board-specific UI
interaction and should be verified manually per kit.
#>
[CmdletBinding()]
param(
    [string]$InstallRoot = "C:\ArduinoEdgeAIWorkshop",
    [string]$AppLabArm64Url = "https://downloads.arduino.cc/AppLab/Stable/ArduinoAppLab_0.8.0_Windows_arm64_installer.exe",
    [switch]$SkipWinget,
    [switch]$SkipPython,
    [switch]$SkipGit,
    [switch]$SkipChrome,
    [switch]$SkipVSCode,
    [switch]$SkipArduinoIde,
    [switch]$SkipArduinoCli,
    [switch]$SkipAppLab,
    [switch]$SkipVSCodeExtensions,
    [switch]$SkipArduinoPackages,
    [switch]$SkipNode,
    [switch]$SkipEdgeImpulseCli,
    [switch]$NoDesktopShortcut
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:Warnings = New-Object System.Collections.Generic.List[string]

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

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
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

function Invoke-External {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$false)][string[]]$Arguments = @(),
        [switch]$AllowFailure
    )
    Write-Host "    > $FilePath $($Arguments -join ' ')" -ForegroundColor DarkGray
    & $FilePath @Arguments
    $exit = $LASTEXITCODE
    if ($exit -ne 0 -and -not $AllowFailure) {
        throw "Command failed with exit code $exit`: $FilePath $($Arguments -join ' ')"
    }
    if ($AllowFailure) { return $exit }
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
        Add-SetupWarning "winget is missing. Install $DisplayName manually."
        return
    }

    $args = @(
        "install", "--id", $Id, "--exact",
        "--accept-package-agreements", "--accept-source-agreements",
        "--silent"
    )
    if ($Architecture) { $args += @("--architecture", $Architecture) }

    $exit = Invoke-External -FilePath "winget" -Arguments $args -AllowFailure
    if ($exit -eq 0) {
        Write-Ok "$DisplayName installed or already present."
    } else {
        Add-SetupWarning "winget could not install $DisplayName. Install it manually if required."
    }
    Refresh-ProcessPath
}

function Install-AppLab {
    if ($SkipAppLab) { return }
    Write-Step "Installing Arduino App Lab"
    $existing = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs","$env:ProgramFiles" -Recurse -Filter "*App Lab*.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($existing) {
        Write-Ok "Arduino App Lab appears to be installed."
        return
    }
    $download = Join-Path $env:TEMP "ArduinoAppLab_Windows_arm64_installer.exe"
    Write-Host "    Downloading $AppLabArm64Url"
    Invoke-WebRequest -Uri $AppLabArm64Url -OutFile $download -UseBasicParsing
    $process = Start-Process -FilePath $download -ArgumentList "/S" -Wait -PassThru
    if ($process.ExitCode -eq 0) {
        Write-Ok "Arduino App Lab installer completed."
    } else {
        Add-SetupWarning "Arduino App Lab installer exited with code $($process.ExitCode). Install manually from Arduino software downloads."
    }
}

function Install-VSCodeExtensions {
    if ($SkipVSCodeExtensions) { return }
    Write-Step "Installing VS Code extensions"
    if (-not (Test-CommandExists "code")) {
        Add-SetupWarning "VS Code command `code` is not available yet. Open VS Code once or install extensions manually."
        return
    }
    $extensions = @(
        "ms-vscode-remote.remote-ssh",
        "ms-python.python",
        "ms-vscode.cpptools"
    )
    foreach ($extension in $extensions) {
        Invoke-External -FilePath "code" -Arguments @("--install-extension", $extension, "--force") -AllowFailure | Out-Null
    }
    Write-Ok "VS Code workshop extensions requested."
}

function Find-ArduinoCli {
    if (Test-CommandExists "arduino-cli") { return "arduino-cli" }
    $found = Get-ChildItem -Path $env:LOCALAPPDATA,$env:ProgramFiles -Recurse -Filter arduino-cli.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

function Install-ArduinoPackages {
    if ($SkipArduinoCli -or $SkipArduinoPackages) { return }
    Write-Step "Installing Arduino UNO Q core and workshop libraries"
    $cli = Find-ArduinoCli
    if (-not $cli) {
        Add-SetupWarning "arduino-cli was not found. Install UNO Q core/libraries manually in Arduino IDE."
        return
    }
    Invoke-External -FilePath $cli -Arguments @("config", "init") -AllowFailure | Out-Null
    Invoke-External -FilePath $cli -Arguments @("core", "update-index") -AllowFailure | Out-Null
    Invoke-External -FilePath $cli -Arguments @("core", "install", "arduino:zephyr") -AllowFailure | Out-Null
    Invoke-External -FilePath $cli -Arguments @("lib", "install", "Arduino_Modulino") -AllowFailure | Out-Null
    Invoke-External -FilePath $cli -Arguments @("lib", "install", "Arduino_RouterBridge") -AllowFailure | Out-Null
    Write-Ok "Arduino CLI package install commands completed."
}

function Install-EdgeImpulseCli {
    if ($SkipEdgeImpulseCli) { return }
    Write-Step "Installing Edge Impulse CLI"
    if (-not (Test-CommandExists "npm")) {
        Add-SetupWarning "npm is not available. Edge Impulse CLI skipped. Install Node.js LTS or use Edge Impulse Studio in the browser."
        return
    }
    Invoke-External -FilePath "npm" -Arguments @("install", "-g", "edge-impulse-cli") -AllowFailure | Out-Null
    if (Test-CommandExists "edge-impulse-uploader") {
        Write-Ok "Edge Impulse CLI appears to be installed."
    } else {
        Add-SetupWarning "Edge Impulse CLI install was requested, but edge-impulse-uploader is not on PATH yet. Reopen PowerShell and check again."
    }
}

function Write-WorkshopFiles {
    Write-Step "Creating workshop workspace"
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "starter") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "data") | Out-Null

    $readme = @"
# Edge AI Workshop Workspace

Use this folder during the workshop.

Suggested flow:

1. Open Arduino App Lab.
2. Connect to the assigned Arduino UNO Q.
3. Verify SSH access.
4. Run the instructor-provided sensor check script.
5. Capture gesture CSV files into the data folder.
6. Upload data to Edge Impulse.
7. Train, deploy, and test live inference.

Manual per-kit checks still required:

- UNO Q appears in App Lab.
- UNO Q base Debian image is current.
- UNO Q is connected to workshop Wi-Fi.
- SSH works.
- Modulino Movement sensor returns accelerometer/gyroscope data.
"@
    Set-Content -LiteralPath (Join-Path $InstallRoot "README.md") -Value $readme -Encoding UTF8

    $checkScript = @"
`$ErrorActionPreference = "Continue"
Write-Host "Workshop laptop verification"
Write-Host "============================"
foreach (`$cmd in @("git", "python", "code", "arduino-cli", "node", "npm", "edge-impulse-uploader")) {
  `$found = Get-Command `$cmd -ErrorAction SilentlyContinue
  if (`$found) {
    Write-Host "[OK] `$cmd -> `$(`$found.Source)"
  } else {
    Write-Host "[MISSING] `$cmd"
  }
}
Write-Host ""
Write-Host "Arduino boards:"
`$cli = Get-Command arduino-cli -ErrorAction SilentlyContinue
if (`$cli) { arduino-cli board list } else { Write-Host "arduino-cli missing" }
Write-Host ""
Write-Host "Open Edge Impulse in browser: https://studio.edgeimpulse.com/"
"@
    Set-Content -LiteralPath (Join-Path $InstallRoot "Verify-WorkshopLaptop.ps1") -Value $checkScript -Encoding UTF8

    $runBat = @"
@echo off
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "%~dp0Verify-WorkshopLaptop.ps1"
pause
"@
    Set-Content -LiteralPath (Join-Path $InstallRoot "Verify-WorkshopLaptop.bat") -Value $runBat -Encoding ASCII

    if (-not $NoDesktopShortcut) {
        $desktop = [Environment]::GetFolderPath("Desktop")
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path $desktop "Verify Edge AI Workshop Laptop.lnk"))
        $shortcut.TargetPath = Join-Path $InstallRoot "Verify-WorkshopLaptop.bat"
        $shortcut.WorkingDirectory = $InstallRoot
        $shortcut.Description = "Verify Edge AI workshop laptop prerequisites"
        $shortcut.Save()
    }
    Write-Ok "Workshop workspace ready: $InstallRoot"
}

function Write-SetupReport {
    Write-Step "Writing setup report"
    $report = Join-Path $InstallRoot "WORKSHOP_SETUP_REPORT.txt"
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Edge AI Workshop laptop setup report")
    $lines.Add("Created: $(Get-Date -Format o)")
    $lines.Add("Computer: $env:COMPUTERNAME")
    $lines.Add("User: $env:USERNAME")
    $lines.Add("")
    foreach ($cmd in @("git", "python", "code", "arduino-cli", "node", "npm", "edge-impulse-uploader")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) {
            $lines.Add("[OK] $cmd -> $($found.Source)")
        } else {
            $lines.Add("[MISSING] $cmd")
        }
    }
    if ($script:Warnings.Count -gt 0) {
        $lines.Add("")
        $lines.Add("Warnings:")
        foreach ($warning in $script:Warnings) {
            $lines.Add("- $warning")
        }
    }
    Set-Content -LiteralPath $report -Value $lines -Encoding UTF8
    Write-Ok "Report written: $report"
}

Write-Host "Edge AI Workshop laptop prerequisite installer" -ForegroundColor White
Write-Host "Admin shell: $(Test-IsAdmin)"
if (-not (Test-IsAdmin)) {
    Add-SetupWarning "Run PowerShell as Administrator for best results."
}

Write-Step "Installing laptop software"
if (-not $SkipGit) { Install-WingetPackage -Id "Git.Git" -DisplayName "Git" }
if (-not $SkipPython) { Install-WingetPackage -Id "Python.Python.3.11" -DisplayName "Python 3.11 ARM64" -Architecture "arm64" }
if (-not $SkipChrome) { Install-WingetPackage -Id "Google.Chrome" -DisplayName "Google Chrome" }
if (-not $SkipVSCode) { Install-WingetPackage -Id "Microsoft.VisualStudioCode" -DisplayName "Visual Studio Code" }
if (-not $SkipArduinoIde) { Install-WingetPackage -Id "ArduinoSA.IDE.stable" -DisplayName "Arduino IDE" }
if (-not $SkipArduinoCli) { Install-WingetPackage -Id "ArduinoSA.CLI" -DisplayName "Arduino CLI" }
if (-not $SkipNode) { Install-WingetPackage -Id "OpenJS.NodeJS.LTS" -DisplayName "Node.js LTS" }

Refresh-ProcessPath
Install-AppLab
Refresh-ProcessPath
Install-VSCodeExtensions
Install-ArduinoPackages
Refresh-ProcessPath
Install-EdgeImpulseCli
Write-WorkshopFiles
Write-SetupReport

Write-Step "Automated setup complete"
Write-Host "Workspace: $InstallRoot"
Write-Host "Next manual step: open Arduino App Lab, connect the UNO Q, complete board onboarding/update, connect Wi-Fi, verify SSH, and run the IMU sensor check."
if ($script:Warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Warnings to review:" -ForegroundColor Yellow
    foreach ($warning in $script:Warnings) {
        Write-Host " - $warning" -ForegroundColor Yellow
    }
}

