# Godot Standalone Build

Windows standalone export is configured in `godot/export_presets.cfg` with the preset `Windows Desktop`.

Build from the repository root:

```powershell
.\scripts\build_godot_windows.ps1
```

The script downloads a local Godot editor binary and matching export templates into ignored local folders when they are missing, then exports:

- `dist\godot\WargameKRUSK.exe`
- `dist\godot\WargameKRUSK.pck`
- `dist\godot\WargameKRUSK-windows-x86_64.zip`

Run the Python backend first, then launch the exported executable:

```powershell
.\.venv\Scripts\python.exe -m wargame.main --mode serve --host 127.0.0.1 --port 8765
.\dist\godot\WargameKRUSK.exe
```
