param(
  [string]$GodotExe = "",
  [string]$GodotVersion = "4.6.2",
  [string]$GodotStatus = "stable",
  [string]$Preset = "Windows Desktop",
  [string]$ProjectDir = "godot",
  [string]$OutputDir = "dist\godot",
  [string]$OutputName = "WargameKRUSK.exe",
  [switch]$SkipDownload
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$versionTag = "$GodotVersion-$GodotStatus"
$templateVersion = "$GodotVersion.$GodotStatus"
$toolRoot = Join-Path $repoRoot ".omx\tools\godot-$versionTag"
$downloadRoot = Join-Path $repoRoot ".omx\downloads"
New-Item -ItemType Directory -Force $toolRoot, $downloadRoot, $OutputDir | Out-Null

function Download-FileIfMissing([string]$Url, [string]$Path) {
  if (Test-Path -LiteralPath $Path) { return }
  if ($SkipDownload) { throw "Missing $Path and -SkipDownload was specified." }
  Write-Host "Downloading $Url"
  Invoke-WebRequest -Uri $Url -OutFile $Path
}

if (-not $GodotExe) {
  $candidate = Get-ChildItem -Path $toolRoot -Recurse -Filter "Godot_v${GodotVersion}-${GodotStatus}_win64_console.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $candidate) {
    $candidate = Get-ChildItem -Path $toolRoot -Recurse -Filter "Godot_v${GodotVersion}-${GodotStatus}_win64.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  }
  if ($candidate) { $GodotExe = $candidate.FullName }
}

if (-not $GodotExe) {
  $editorZip = Join-Path $downloadRoot "Godot_v${GodotVersion}-${GodotStatus}_win64.exe.zip"
  $editorUrl = "https://github.com/godotengine/godot-builds/releases/download/$versionTag/Godot_v${GodotVersion}-${GodotStatus}_win64.exe.zip"
  Download-FileIfMissing $editorUrl $editorZip
  Expand-Archive -LiteralPath $editorZip -DestinationPath $toolRoot -Force
  $candidate = Get-ChildItem -Path $toolRoot -Recurse -Filter "Godot_v${GodotVersion}-${GodotStatus}_win64.exe" | Select-Object -First 1
  if (-not $candidate) { throw "Godot editor executable not found after extracting $editorZip" }
  $GodotExe = $candidate.FullName
}

$templateDir = Join-Path $env:APPDATA "Godot\export_templates\$templateVersion"
$releaseTemplate = Join-Path $templateDir "windows_release_x86_64.exe"
if (-not (Test-Path -LiteralPath $releaseTemplate)) {
  if ($SkipDownload) { throw "Missing export templates at $templateDir and -SkipDownload was specified." }
  New-Item -ItemType Directory -Force $templateDir | Out-Null
  $tpz = Join-Path $downloadRoot "Godot_v${GodotVersion}-${GodotStatus}_export_templates.tpz"
  $templateUrl = "https://github.com/godotengine/godot-builds/releases/download/$versionTag/Godot_v${GodotVersion}-${GodotStatus}_export_templates.tpz"
  Download-FileIfMissing $templateUrl $tpz
  $zip = Join-Path $downloadRoot "Godot_v${GodotVersion}-${GodotStatus}_export_templates.zip"
  Copy-Item -LiteralPath $tpz -Destination $zip -Force
  $extractRoot = Join-Path $downloadRoot "templates-$versionTag"
  if (Test-Path -LiteralPath $extractRoot) { Remove-Item -LiteralPath $extractRoot -Recurse -Force }
  Expand-Archive -LiteralPath $zip -DestinationPath $extractRoot -Force
  $templates = Join-Path $extractRoot "templates"
  if (-not (Test-Path -LiteralPath $templates)) { throw "Template archive did not contain a templates directory." }
  Copy-Item -Path (Join-Path $templates "*") -Destination $templateDir -Recurse -Force
}

$outputExe = Join-Path (Resolve-Path $OutputDir).Path $OutputName
$outputRoot = (Resolve-Path $OutputDir).Path
Get-ChildItem -LiteralPath $outputRoot -Filter "*.TMP" -File -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "Using Godot: $GodotExe"
Write-Host "Using export template: $releaseTemplate"
Write-Host "Exporting preset '$Preset' to $outputExe"
& $GodotExe --headless --path $ProjectDir --export-release $Preset $outputExe
$exitCode = $LASTEXITCODE
if ($null -eq $exitCode) { $exitCode = 0 }
if ($exitCode -ne 0) { throw "Godot export failed with exit code $exitCode" }
if (-not (Test-Path -LiteralPath $outputExe)) { throw "Expected output executable was not created: $outputExe" }

$zipPath = Join-Path $outputRoot "WargameKRUSK-windows-x86_64.zip"
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Compress-Archive -Path (Join-Path $outputRoot "*") -DestinationPath $zipPath -Force
Write-Host "Standalone build ready: $outputExe"
Write-Host "Packaged archive ready: $zipPath"
