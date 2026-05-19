param(
  [string]$Python = "py -3.12",
  [switch]$KeepExisting
)

$ErrorActionPreference = "Stop"

$venv = Join-Path (Get-Location) ".venv"
if ((Test-Path -LiteralPath $venv) -and -not $KeepExisting) {
  $resolved = (Resolve-Path -LiteralPath $venv).Path
  $cwd = (Resolve-Path -LiteralPath (Get-Location)).Path
  if (-not $resolved.StartsWith($cwd)) { throw "Refusing to remove outside workspace: $resolved" }
  Remove-Item -LiteralPath $resolved -Recurse -Force
}

# Accept either a plain executable path ("python") or a py-launcher command ("py -3.12").
$parts = $Python -split " "
$exe = $parts[0]
$argv = @($parts | Select-Object -Skip 1)

& $exe @argv -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "Venv ready on:"
& .\.venv\Scripts\python.exe --version
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
