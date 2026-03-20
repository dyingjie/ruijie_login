@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%USERPROFILE%\miniconda3\envs\ruijie\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] No configured Python found at "%PYTHON_EXE%".
    exit /b 1
)
"%PYTHON_EXE%" -m ruijie_login status %*
