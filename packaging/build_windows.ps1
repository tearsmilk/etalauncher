# Build a single-file Eta.exe (Эта) on Windows with Python 3.11 + requirements-build.txt installed.
# Usage: pwsh packaging/build_windows.ps1   (APP_VERSION env overrides the version from eta/__init__.py)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$py = if ($env:PYTHON) { $env:PYTHON } else { "python" }
if (-not $env:APP_VERSION) { $env:APP_VERSION = & $py -c "import eta; print(eta.__version__)" }
$version = $env:APP_VERSION

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
New-Item -ItemType Directory build | Out-Null

& $py packaging/windows_meta.py $version
if ($LASTEXITCODE -ne 0) { throw "windows_meta.py failed" }

& $py -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyi packaging/Eta-windows.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = "dist/Eta.exe"
if (-not (Test-Path $exe)) { throw "no $exe" }

# smoke test: the frozen launcher runs its own headless checks (ETA_DATA → temp folder is set by the selftest)
$env:QT_QPA_PLATFORM = "offscreen"
& $exe --selftest
if ($LASTEXITCODE -ne 0) { throw "Eta.exe --selftest failed with $LASTEXITCODE" }
Remove-Item Env:QT_QPA_PLATFORM

Copy-Item $exe "dist/Eta-$version-windows-x64.exe"
Copy-Item packaging/README-windows.txt "dist/Прочти меня.txt"
Get-ChildItem dist | Format-Table Name, Length
