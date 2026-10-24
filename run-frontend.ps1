# Starts the React frontend on http://localhost:5173 (proxies /api, /ws, /media to the backend).
# Finds the backend port from backend\.port (written by run-backend.ps1) unless BACKEND_PORT is set.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot 'frontend')
if (-not (Test-Path 'node_modules')) { npm install }
npm run dev
