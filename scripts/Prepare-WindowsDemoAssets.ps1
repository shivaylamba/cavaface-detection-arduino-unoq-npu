#requires -Version 5.1
<#
.SYNOPSIS
Creates a portable runtime asset bundle for the Windows demo installer.

.DESCRIPTION
Run this once on a known-good laptop where the ONNX models and optional known
face databases are already present. Copy the resulting folder or zip to a USB
drive or network share, then pass it to Install-WindowsDemo.ps1 with -AssetsPath.
#>
[CmdletBinding()]
param(
    [string]$SourceRepo = "",
    [string]$OutputPath = "C:\ArduinoFaceDemoAssets",
    [switch]$IncludeKnownFaces,
    [switch]$Zip
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $SourceRepo) {
    $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    $SourceRepo = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Copy-RequiredFile {
    param([string]$Source, [string]$Destination)
    if (-not (Test-Path $Source)) {
        throw "Missing required asset: $Source"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

if (Test-Path $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
$OutputPath = (Resolve-Path $OutputPath).Path

$files = @(
    "laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx",
    "laptop_ai_guard\models\mobilefacenet\mobilefacenet.onnx.data",
    "laptop_ai_guard\models\media_pipe\media_pipe.onnx"
)

$optional = @(
    "laptop_ai_guard\models\cavaface\cavaface.onnx"
)

if ($IncludeKnownFaces) {
    $optional += @(
        "laptop_ai_guard\known_faces_mobilefacenet\embeddings.npz",
        "laptop_ai_guard\known_faces\embeddings.npz"
    )
}

foreach ($rel in $files) {
    Copy-RequiredFile -Source (Join-Path $SourceRepo $rel) -Destination (Join-Path $OutputPath $rel)
}

foreach ($rel in $optional) {
    $src = Join-Path $SourceRepo $rel
    if (Test-Path $src) {
        New-Item -ItemType Directory -Force -Path (Split-Path (Join-Path $OutputPath $rel) -Parent) | Out-Null
        Copy-Item -LiteralPath $src -Destination (Join-Path $OutputPath $rel) -Force
    }
}

$manifest = Join-Path $OutputPath "MANIFEST.txt"
"Arduino UNO Q Local AI Face Demo asset bundle" | Set-Content -LiteralPath $manifest -Encoding UTF8
"Created: $(Get-Date -Format o)" | Add-Content -LiteralPath $manifest
"SourceRepo: $SourceRepo" | Add-Content -LiteralPath $manifest
"" | Add-Content -LiteralPath $manifest
Get-ChildItem -Path $OutputPath -Recurse -File |
    Where-Object { $_.FullName -ne $manifest } |
    Sort-Object FullName |
    ForEach-Object {
        $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
        $rel = $_.FullName.Substring($OutputPath.Length).TrimStart("\")
        "{0}`t{1}`t{2}" -f $hash.Hash, $_.Length, $rel
    } | Add-Content -LiteralPath $manifest

if ($Zip) {
    $zipPath = "$OutputPath.zip"
    if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Compress-Archive -Path (Join-Path $OutputPath "*") -DestinationPath $zipPath -Force
    Write-Host "Created asset zip: $zipPath"
}

Write-Host "Created asset bundle: $OutputPath"
Write-Host "Use with: scripts\Install-WindowsDemo.ps1 -AssetsPath `"$OutputPath`""
