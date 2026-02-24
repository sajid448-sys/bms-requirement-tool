@echo off
cd /d "%~dp0"

echo Building...
docker compose build
if errorlevel 1 exit /b 1

echo Starting containers...
docker compose up -d
if errorlevel 1 exit /b 1

echo Waiting for server...
timeout /t 3 /nobreak >nul

start "" "http://localhost:5000"
echo Browser opened. Server is running (docker compose up -d). To stop: docker compose down
