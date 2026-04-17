#!/bin/bash
cd /opt/myapp
source venv/bin/activate

# Kill any existing instance (optional safety)
pkill -f "python app.py" || true

# Start app in background
nohup python app.py > app.log 2>&1 &
echo $! > app.pid

echo "App started"