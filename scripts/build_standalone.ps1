param(
  [ValidateSet("windows", "mac")]
  [string]$Target = "windows"
)

$ErrorActionPreference = "Stop"
$py = if (Test-Path .\.venv\Scripts\python.exe) { ".\.venv\Scripts\python.exe" } else { "python" }
& $py -m pip install -e . pyinstaller

$name = "wargame_kursk"
& $py -m PyInstaller --noconfirm --clean --name $name --paths src --collect-data wargame --add-data "DEM_data_1;DEM_data_1" src\wargame\main.py
Write-Host "Build complete under dist/$name. Cross-OS builds must be run on the target OS or CI runner."
