#requires -Version 5.1
<#
.SYNOPSIS
Publishes the Windows demo runtime asset bundle to a GitHub Release.

.DESCRIPTION
This script expects GitHub CLI (`gh`) to be installed and authenticated with
permission to create releases/upload assets in the target repository.
#>
[CmdletBinding()]
param(
    [string]$Repo = "shivaylamba/cavaface-detection-arduino-unoq-npu",
    [string]$Tag = "runtime-assets",
    [string]$Title = "Runtime assets for Windows demo",
    [string]$SourceRepo = "",
    [string]$OutputPath = "C:\ArduinoFaceDemoAssets",
    [switch]$IncludeKnownFaces,
    [switch]$PublicBiometricDataAcknowledged
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($IncludeKnownFaces -and -not $PublicBiometricDataAcknowledged) {
    throw "Known-face databases contain biometric embeddings. Rerun with -PublicBiometricDataAcknowledged only if you intentionally want those embeddings in the GitHub release."
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI `gh` was not found. Install it with: winget install --id GitHub.cli --exact"
}

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$prepareScript = Join-Path $scriptDir "Prepare-WindowsDemoAssets.ps1"
if (-not (Test-Path $prepareScript)) {
    throw "Could not find $prepareScript"
}

$prepareArgs = @("-ExecutionPolicy", "Bypass", "-File", $prepareScript, "-OutputPath", $OutputPath, "-Zip")
if ($SourceRepo) { $prepareArgs += @("-SourceRepo", $SourceRepo) }
if ($IncludeKnownFaces) { $prepareArgs += "-IncludeKnownFaces" }

& powershell.exe @prepareArgs
if ($LASTEXITCODE -ne 0) {
    throw "Asset bundle creation failed."
}

$zipPath = "$OutputPath.zip"
if (-not (Test-Path $zipPath)) {
    throw "Expected zip was not created: $zipPath"
}

$releaseExists = $false
& gh release view $Tag --repo $Repo *> $null
if ($LASTEXITCODE -eq 0) { $releaseExists = $true }

if (-not $releaseExists) {
    & gh release create $Tag --repo $Repo --title $Title --notes "Runtime ONNX model assets for the Windows fleet installer. These files are intentionally distributed as release assets instead of normal git files."
    if ($LASTEXITCODE -ne 0) { throw "Failed to create GitHub release $Tag." }
}

& gh release upload $Tag $zipPath --repo $Repo --clobber
if ($LASTEXITCODE -ne 0) { throw "Failed to upload $zipPath to release $Tag." }

Write-Host "Uploaded asset bundle."
Write-Host "Installer URL:"
Write-Host "https://github.com/$Repo/releases/latest/download/ArduinoFaceDemoAssets.zip"

