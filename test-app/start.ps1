cd E:\appctl\test-app

# Kill existing
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Start in background
Start-Process python -ArgumentList "app.py" -NoNewWindowcd E:\appctl\test-app

# Kill existing
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Start in background
Start-Process python -ArgumentList "app.py" -NoNewWindow