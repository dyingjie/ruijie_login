@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "SCRIPT_DIR=%~dp0"
set "LOG_DIR=%SCRIPT_DIR%logs"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss-fff" 2^>nul') do set "STAMP=%%I"
if not defined STAMP (
    set "STAMP=%DATE: =0%_%TIME: =0%"
    set "STAMP=%STAMP:/=-%"
    set "STAMP=%STAMP::=-%"
    set "STAMP=%STAMP:.=-%"
)
set "STAMP=%STAMP%-%RANDOM%"
set "LOG_FILE=%LOG_DIR%\status-%STAMP%.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

call :resolve_python
if errorlevel 1 (
    call :log ERROR No usable Python found. Set PYTHON_EXE in the task or install Python in a common location.
    exit /b 1
)

call :log INFO Starting status command with %PYTHON_CMD%
%PYTHON_CMD% -m ruijie_login %* status >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
call :log INFO Command finished with exit code %EXIT_CODE%
exit /b %EXIT_CODE%

:resolve_python
if defined PYTHON_EXE if exist "%PYTHON_EXE%" (
    set "PYTHON_CMD="%PYTHON_EXE%""
    exit /b 0
)

for %%I in (
    "%SCRIPT_DIR%.venv\Scripts\python.exe"
    "%SCRIPT_DIR%venv\Scripts\python.exe"
    "%USERPROFILE%\miniconda3\envs\ruijie\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) do (
    if exist "%%~I" (
        set "PYTHON_CMD="%%~I""
        exit /b 0
    )
)

for %%C in (py.exe python.exe) do (
    for /f "delims=" %%I in ('where.exe %%C 2^>nul') do (
        echo %%~I | findstr /i "\\WindowsApps\\" >nul
        if errorlevel 1 (
            if /i "%%~nxI"=="py.exe" (
                set "PYTHON_CMD=py -3"
            ) else (
                set "PYTHON_CMD="%%~I""
            )
            exit /b 0
        )
    )
)

exit /b 1

:log
>> "%LOG_FILE%" echo [%date% %time%] [%~1] %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9
exit /b 0
