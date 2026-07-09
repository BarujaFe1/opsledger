@echo off
setlocal
cd /d "%~dp0"

echo [OpsLedger] Starting API (8000) and Web (3000)...

if not exist "apps\api\.venv\Scripts\python.exe" (
  echo [OpsLedger] Creating API venv...
  py -3.12 -m venv "apps\api\.venv" 2>nul || python -m venv "apps\api\.venv"
  "apps\api\.venv\Scripts\python.exe" -m pip install -r "apps\api\requirements.txt"
)

if not exist "apps\web\node_modules" (
  echo [OpsLedger] Installing web dependencies...
  pushd apps\web
  call npm install
  popd
)

if not exist "apps\web\.env.local" (
  copy /Y "apps\web\.env.example" "apps\web\.env.local" >nul
)

if not exist "apps\api\data\demo\orders.csv" (
  echo [OpsLedger] Generating demo CSVs...
  "apps\api\.venv\Scripts\python.exe" "apps\api\scripts\generate_demo_data.py"
)

start "OpsLedger API" cmd /k "cd /d "%~dp0apps\api" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
timeout /t 2 /nobreak >nul
start "OpsLedger Web" cmd /k "cd /d "%~dp0apps\web" && npm run dev"

echo.
echo API:  http://127.0.0.1:8000/api/health
echo Web:  http://localhost:3000
echo Demo: http://localhost:3000/wizard?mode=demo
echo.
endlocal
