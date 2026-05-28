param(
  [string]$GodotExe = "",
  [string]$GodotVersion = "4.6.2",
  [string]$GodotStatus = "stable",
  [string]$OutputDir = "dist\standalone",
  [switch]$SkipDownload,
  [switch]$Clean
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$backendOut = "dist\backend"
$godotOut = "dist\godot"

& (Join-Path $PSScriptRoot "build_backend_windows.ps1") -OutputDir $backendOut -OutputName "WargameKRUSKBackend.exe" -Clean

$godotArgs = @{
  GodotVersion = $GodotVersion
  GodotStatus = $GodotStatus
  OutputDir = $godotOut
  OutputName = "WargameKRUSK.exe"
}
if ($GodotExe) { $godotArgs["GodotExe"] = $GodotExe }
if ($SkipDownload) { $godotArgs["SkipDownload"] = $true }
& (Join-Path $PSScriptRoot "build_godot_windows.ps1") @godotArgs

$resolvedOutputDir = Join-Path $repoRoot $OutputDir
if ($Clean -and (Test-Path -LiteralPath $resolvedOutputDir)) {
  Remove-Item -LiteralPath $resolvedOutputDir -Recurse -Force
}
New-Item -ItemType Directory -Force $resolvedOutputDir | Out-Null
Remove-Item -LiteralPath (Join-Path $resolvedOutputDir "WargameKRUSKBackend.exe") -Force -ErrorAction SilentlyContinue

$godotFiles = @(
  (Join-Path $repoRoot "$godotOut\WargameKRUSK.exe"),
  (Join-Path $repoRoot "$godotOut\WargameKRUSK.pck")
)
foreach ($file in $godotFiles) {
  if (Test-Path -LiteralPath $file) {
    Copy-Item -LiteralPath $file -Destination $resolvedOutputDir -Force
  }
}

$backendBundle = Join-Path $repoRoot "$backendOut\WargameKRUSKBackend"
$backendExe = Join-Path $backendBundle "WargameKRUSKBackend.exe"
$standaloneBackendDir = Join-Path $resolvedOutputDir "backend"
if (Test-Path -LiteralPath $backendExe) {
  if (Test-Path -LiteralPath $standaloneBackendDir) {
    Remove-Item -LiteralPath $standaloneBackendDir -Recurse -Force
  }
  New-Item -ItemType Directory -Force $standaloneBackendDir | Out-Null
  Copy-Item -Path (Join-Path $backendBundle "*") -Destination $standaloneBackendDir -Recurse -Force
} else {
  $oneFileBackendExe = Join-Path $repoRoot "$backendOut\WargameKRUSKBackend.exe"
  if (-not (Test-Path -LiteralPath $oneFileBackendExe)) {
    throw "Backend executable missing: $backendExe"
  }
  New-Item -ItemType Directory -Force $standaloneBackendDir | Out-Null
  Copy-Item -LiteralPath $oneFileBackendExe -Destination $standaloneBackendDir -Force
}

$launcherPath = Join-Path $resolvedOutputDir "Run-WargameKRUSK.cmd"
@'
@echo off
setlocal
cd /d "%~dp0"
start "" "%~dp0WargameKRUSK.exe"
'@ | Set-Content -LiteralPath $launcherPath -Encoding ASCII

$readmePath = Join-Path $resolvedOutputDir "README_STANDALONE.txt"
@'
Wargame KRUSK standalone package

Run:
  - Launch WargameKRUSK.exe or Run-WargameKRUSK.cmd.
  - The Godot client automatically starts backend\WargameKRUSKBackend.exe.

Files:
  - WargameKRUSK.exe / WargameKRUSK.pck: Godot client.
  - backend\: Python/FastAPI backend standalone bundle.

Network:
  - The backend binds to 127.0.0.1:8765 by default.
  - If startup fails, check backend\logs\wargame_backend.log.
'@ | Set-Content -LiteralPath $readmePath -Encoding UTF8

$zipPath = Join-Path $repoRoot "dist\WargameKRUSK-standalone.zip"
$fallbackZipPath = Join-Path $repoRoot "dist\WargameKRUSK-standalone-current.zip"
$archivePath = $zipPath
$zipRemoved = $true
if (Test-Path -LiteralPath $zipPath) {
  $zipRemoved = $false
  for ($i = 0; $i -lt 5; $i++) {
    try {
      Remove-Item -LiteralPath $zipPath -Force -ErrorAction Stop
      $zipRemoved = $true
      break
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
}
if (-not $zipRemoved) {
  Write-Warning "Could not replace $zipPath because another process is using it. Writing fallback archive: $fallbackZipPath"
  $archivePath = $fallbackZipPath
}
if (Test-Path -LiteralPath $archivePath) { Remove-Item -LiteralPath $archivePath -Force }
Compress-Archive -Path (Join-Path $resolvedOutputDir "*") -DestinationPath $archivePath -Force

Write-Host "Combined standalone package ready: $resolvedOutputDir"
Write-Host "Combined archive ready: $archivePath"

