param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$venvPythonW = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
$marker = Join-Path $PSScriptRoot '.venv\behindwatch-requirements.sha256'
$digest = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
$needsInstall = -not (Test-Path -LiteralPath $marker)
if (-not $needsInstall) { $needsInstall = (Get-Content -LiteralPath $marker -Raw).Trim() -ne $digest }
if ((Test-Path -LiteralPath $venvPython) -and -not $needsInstall) {
    & $venvPython -c 'import cv2, mediapipe, PIL, pystray, cv2_enumerate_cameras'
    $needsInstall = $LASTEXITCODE -ne 0
}
if (-not (Test-Path -LiteralPath $venvPython) -or $needsInstall) {
    $pythonPath = $null
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $candidate = & py -3.12 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0) { $pythonPath = $candidate }
        } catch {
            # Missing Python 3.12 in the launcher must still allow the bundled runtime fallback.
            $pythonPath = $null
        }
    }
    if (-not $pythonPath -and (Test-Path -LiteralPath $bundled)) { $pythonPath = $bundled }
    if (-not $pythonPath -and (Get-Command python -ErrorAction SilentlyContinue)) {
        $pythonPath = (Get-Command python).Source
    }
    if (-not $pythonPath) { throw 'Python 3.12 x64 is required. Install Python 3.12 and run launch.cmd again.' }
    # Avoid nested quotes: Windows PowerShell 5 rewrites them when passing native arguments.
    & $pythonPath -c 'import sys; assert sys.version_info[:2] == (3,12) and sys.maxsize > 2**32'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 x64 is required.' }
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $pythonPath -m venv --without-pip (Join-Path $PSScriptRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Unable to create the local virtual environment.' }
    }
    # Use the bootstrap interpreter's pip so embedded Python does not need ensurepip.
    & $pythonPath -m pip --python $venvPython install --disable-pip-version-check -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check your network and rerun launch.cmd.' }
    Set-Content -LiteralPath $marker -Value $digest -Encoding ASCII
}
& $venvPython (Join-Path $PSScriptRoot 'download_models.py')
if ($LASTEXITCODE -ne 0) { throw 'Model download or integrity verification failed.' }
$env:MPLCONFIGDIR = Join-Path $PSScriptRoot '.runtime\matplotlib'
New-Item -ItemType Directory -Force -Path $env:MPLCONFIGDIR | Out-Null
if ($CheckOnly) { Write-Output 'BehindWatch runtime and models verified.'; exit 0 }
Start-Process -FilePath $venvPythonW -ArgumentList @('app.py') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
