#!/bin/bash

pip install -r requirements.txt 

echo "Checking for processes on port 8510..."
PORT_PID=$(lsof -ti:8510)

if [ ! -z "$PORT_PID" ]; then
    echo "Found process $PORT_PID running on port 8510. Terminating..."
    kill -9 $PORT_PID
    echo "Process terminated."
else
    echo "No process found running on port 8510."
fi

sleep 2

echo "Starting Streamlit application..."

streamlit run app.py --server.port 8510 &

NEW_PID=$!
echo "Streamlit started with PID: $NEW_PID"