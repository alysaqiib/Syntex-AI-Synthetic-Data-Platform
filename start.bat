@echo off
echo ========================================================
echo   Starting SYNTEX - Synthetic Data Platform (HackDataV2)
echo ========================================================
echo.

start "Syntex Backend (FastAPI)" cmd /k "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 2 > nul
start "Syntex Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo Backend running on http://localhost:8000
echo Frontend running on http://localhost:5173
echo.
