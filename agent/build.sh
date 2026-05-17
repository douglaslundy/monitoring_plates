#!/usr/bin/env bash
# Build standalone Windows executable with PyInstaller
set -e

pip install pyinstaller opencv-python-headless requests

pyinstaller \
    --onefile \
    --name agent \
    --hidden-import=cv2 \
    main.py

echo "Executável gerado em dist/agent  (Linux/Mac) ou dist/agent.exe (Windows)"
