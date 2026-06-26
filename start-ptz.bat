@echo off
pushd "%~dp0"
echo Starting Pocket PTZ panel...
python ptz-server.py
pause
