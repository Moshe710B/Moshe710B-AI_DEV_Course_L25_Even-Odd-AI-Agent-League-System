# Start League - Opens all agents in separate windows
# Run this from the project root directory

$projectRoot = $PSScriptRoot

# Start League Manager
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\agents\league_manager'; python main.py"

# Wait a bit for League Manager to start
Start-Sleep -Seconds 2

# Start Referees
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\agents\referee_REF01'; python main.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\agents\referee_REF02'; python main.py"

# Wait a bit for Referees to register
Start-Sleep -Seconds 2

# Start Players
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\agents\player_P01'; python main.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\agents\player_P02'; python main.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\agents\player_P03'; python main.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\agents\player_P04'; python main.py"

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "  All agents started!" -ForegroundColor Green
Write-Host "  Watch the League Manager window for results" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Host "League will start automatically after all agents register (about 10 seconds)"
Write-Host ""
Write-Host "Press Ctrl+C in each window to stop agents"
