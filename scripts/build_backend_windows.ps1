param(
  [string]$OutputDir = "dist\backend",
  [string]$OutputName = "WargameKRUSKBackend.exe",
  [string]$PythonExe = "",
  [string]$PyInstallerExe = "",
  [switch]$OneFile,
  [switch]$Clean
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

if (-not $PythonExe) {
  $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $venvPython) {
    $PythonExe = $venvPython
  } else {
    $PythonExe = "python"
  }
}

if (-not $PyInstallerExe) {
  $venvPyInstaller = Join-Path $repoRoot ".venv\Scripts\pyinstaller.exe"
  if (Test-Path -LiteralPath $venvPyInstaller) {
    $PyInstallerExe = $venvPyInstaller
  }
}

if ($Clean) {
  $buildRoot = Join-Path $repoRoot "build\pyinstaller-backend"
  if (Test-Path -LiteralPath $buildRoot) { Remove-Item -LiteralPath $buildRoot -Recurse -Force }
  if (Test-Path -LiteralPath $OutputDir) { Remove-Item -LiteralPath $OutputDir -Recurse -Force }
}

$resolvedOutputDir = Join-Path $repoRoot $OutputDir
New-Item -ItemType Directory -Force $resolvedOutputDir | Out-Null

$workPath = Join-Path $repoRoot "build\pyinstaller-backend"
$specPath = Join-Path $repoRoot "build\pyinstaller-spec"
New-Item -ItemType Directory -Force $workPath, $specPath | Out-Null

$entryPoint = Join-Path $repoRoot "src\wargame\main.py"
$sourcePath = Join-Path $repoRoot "src"
$configData = "$(Join-Path $repoRoot 'src\wargame\config');wargame\config"
$scenarioData = "$(Join-Path $repoRoot 'src\wargame\scenarios');wargame\scenarios"
$terrainData = "$(Join-Path $repoRoot 'DEM_data_1');DEM_data_1"

$baseArgs = @(
  "--noconfirm",
  "--clean",
  "--name", [IO.Path]::GetFileNameWithoutExtension($OutputName),
  "--console",
  "--paths", $sourcePath,
  "--distpath", $resolvedOutputDir,
  "--workpath", $workPath,
  "--specpath", $specPath,
  "--add-data", $configData,
  "--add-data", $scenarioData,
  "--add-data", $terrainData,
  "--collect-submodules", "uvicorn",
  "--collect-submodules", "uvicorn.protocols",
  "--collect-submodules", "uvicorn.lifespan",
  "--collect-submodules", "uvicorn.loops",
  "--collect-submodules", "watchfiles",
  "--hidden-import", "yaml",
  $entryPoint
)
if ($OneFile) {
  $baseArgs = @("--onefile") + $baseArgs
}

Write-Host "Building standalone Python backend..."
if ($OneFile) {
  Write-Host "Backend bundle mode: onefile"
} else {
  Write-Host "Backend bundle mode: onedir (more reliable for clean target machines)"
}
if ($PyInstallerExe) {
  Write-Host "Using PyInstaller: $PyInstallerExe"
  & $PyInstallerExe @baseArgs
} else {
  Write-Host "Using Python module PyInstaller via: $PythonExe"
  & $PythonExe -m PyInstaller @baseArgs
}

$exitCode = $LASTEXITCODE
if ($null -eq $exitCode) { $exitCode = 0 }
if ($exitCode -ne 0) { throw "PyInstaller failed with exit code $exitCode" }

$bundleName = [IO.Path]::GetFileNameWithoutExtension($OutputName)
if ($OneFile) {
  $builtExe = Join-Path $resolvedOutputDir ($bundleName + ".exe")
  $targetExe = Join-Path $resolvedOutputDir $OutputName
} else {
  $builtExe = Join-Path (Join-Path $resolvedOutputDir $bundleName) ($bundleName + ".exe")
  $targetExe = Join-Path (Join-Path $resolvedOutputDir $bundleName) $OutputName
}
if (-not (Test-Path -LiteralPath $builtExe)) {
  throw "Expected backend executable was not created: $builtExe"
}
if ($builtExe -ne $targetExe) {
  Move-Item -LiteralPath $builtExe -Destination $targetExe -Force
}

Write-Host "Standalone backend ready: $targetExe"
