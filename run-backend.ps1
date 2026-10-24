# Convenience wrapper: sets up the venv on first run, then runs the one-command backend.
#   Same thing, by hand:  cd backend ; .\.venv\Scripts\python.exe manage.py start_local
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot 'backend')
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Creating backend\.venv ...'
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.13+ is required (python not found).' }
}
& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
& .\.venv\Scripts\python.exe manage.py start_local
