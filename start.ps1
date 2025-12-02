# Start script for MCPFlightBooking system
# This script starts all required services in separate terminals

Write-Host "Starting MCPFlightBooking System..." -ForegroundColor Cyan
Write-Host ""

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start Flight API (Backend Database)
Write-Host "[1/3] Starting Flight API on port 8000..." -ForegroundColor Green
$backendDir = Join-Path $rootDir "src\backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendDir'; Write-Host 'Flight API Server' -ForegroundColor Cyan; python -m uvicorn flight_api:app --reload --port 8000"

# Wait a bit for backend to start
Start-Sleep -Seconds 3

# Start Backend Server (Gemini + MCP)
Write-Host "[2/3] Starting Gemini + MCP Server on port 8001..." -ForegroundColor Green
$backendServerDir = Join-Path $rootDir "src\backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendServerDir'; Write-Host 'Gemini + MCP Server' -ForegroundColor Magenta; python -m uvicorn server:app --reload --port 8001"

# Wait a bit for frontend to start
Start-Sleep -Seconds 3

# Open the webpage
Write-Host "[3/3] Opening webpage..." -ForegroundColor Green
$frontendDir = Join-Path $rootDir "src\frontend"
$indexPath = Join-Path $frontendDir "index.html"
Start-Process $indexPath

Write-Host ""
Write-Host "All services started successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Services running:" -ForegroundColor Cyan
Write-Host "  - Flight API:        http://localhost:8000" -ForegroundColor White
Write-Host "  - Gemini + MCP:      http://localhost:8001" -ForegroundColor White
Write-Host "  - Frontend:          Browser opened" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C in each terminal window to stop the servers." -ForegroundColor Yellow
