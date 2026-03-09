@echo off
REM Batch script wrapper for start.ps1
REM This allows double-clicking to start the system

echo Starting MCPFlightBooking System...
powershell -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
