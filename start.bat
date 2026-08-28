@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv is missing. See README.md
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\run_all.py --source REAL
if errorlevel 1 (
  echo ERROR: update failed. Check logs\errors and logs\app.
  pause
  exit /b 1
)
start "Ozon Trend Radar" ".venv\Scripts\pythonw.exe" -m streamlit run app\dashboard.py --server.headless true --server.port 8501
timeout /t 4 /nobreak >nul
start "" "http://localhost:8501"
echo Dashboard started: http://localhost:8501
echo Close the browser or press any key to close this window.
pause >nul
