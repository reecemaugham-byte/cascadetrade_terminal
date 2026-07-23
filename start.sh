#!/bin/bash
echo "Starting Roleigh QuanTrader Worker..."
while true; do
    python worker.py
    echo "Worker crashed! Restarting in 10 seconds..."
    sleep 10
done
