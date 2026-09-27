$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    python -m unittest tests -v
    if($LASTEXITCODE){throw 'Tests failed'}
    python -m PyInstaller --noconfirm --clean --onedir --windowed --name DolbyBuiltinPatcher --distpath dist --workpath build --add-data 'assets;assets' --collect-all customtkinter app.py
    if($LASTEXITCODE){throw 'EXE build failed'}
} finally {Pop-Location}
