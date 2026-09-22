@echo off
rem 一键起环境: 建虚拟环境 + 装依赖 + 起 Web
setlocal
where python >nul 2>nul || (echo [ERROR] python not found & exit /b 1)
python -m venv .venv
if errorlevel 1 (echo [ERROR] venv create failed & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (echo [ERROR] deps install failed & exit /b 1)
if not defined AGNES_API_KEY (
  echo [WARN] AGNES_API_KEY not set; LLM calls will fail.
  echo   Run:  set AGNES_API_KEY=sk-...   then re-run.
)
echo [OK] ready. Starting web on http://127.0.0.1:8000
python app.py
