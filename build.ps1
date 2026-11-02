$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    python -m unittest tests test_mobile test_module_export -v
    if($LASTEXITCODE){throw 'Tests failed'}
    python -m PyInstaller --noconfirm --clean --onedir --windowed --name DolbyBuiltinPatcher --distpath dist --workpath build --add-data 'assets;assets' --collect-all customtkinter app.py
    if($LASTEXITCODE){throw 'EXE build failed'}
} finally {Pop-Location}
