@echo off
rem Opens the backend and the frontend, each in its own window. Double-click this file,
rem or from PowerShell in this folder run:  .\run-all.bat
cd /d "%~dp0"
start "Auction backend" powershell -NoExit -ExecutionPolicy Bypass -File run-backend.ps1
start "Auction frontend" powershell -NoExit -ExecutionPolicy Bypass -File run-frontend.ps1
echo.
echo Frontend : http://localhost:5173   ^<-- open this one
echo Logins   : demo_buyer / demo_seller / demo_admin   password DemoPass12345!
