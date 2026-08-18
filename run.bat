@echo off
start "Pausal 3000" wsl.exe bash -lc "cd /mnt/d/projects/paushal_3000 && .venv/bin/python app.py"
timeout /t 2 /nobreak >nul
start http://localhost:5000
