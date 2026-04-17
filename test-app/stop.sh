#!/bin/bash
cd /opt/myapp

if [ -f app.pid ]; then
    kill $(cat app.pid) || true
    rm app.pid
fi

# fallback kill
pkill -f "python app.py" || true

echo "App stopped"