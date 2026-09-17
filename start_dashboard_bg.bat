@echo off
rem ---------------------------------------------------------------------------
rem Start the local dashboard DETACHED.
rem
rem Why this exists: start_dashboard.bat runs python in the calling console and
rem ends with pause, so the window - and any agent tool call that launched it -
rem stays blocked for as long as the server lives, and dies with that console.
rem This script returns as soon as the port answers, leaving the server in its
rem own process, so it survives the caller (Hermes session, cmd window, ssh).
rem
rem Output goes to local.log / local.log.err. The logger writes to stderr, so
rem .err is the file with content. A hidden window leaves no other trace, and an
rem unexplained stop once left nothing to read afterwards.
rem
rem Usage:
rem   start_dashboard_bg.bat          start (replaces a stale listener on the port)
rem   start_dashboard_bg.bat open     also open the browser
rem
rem Messages are ASCII on purpose: a .bat is read in the console codepage and
rem non-ASCII text turns into mojibake there.
rem ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
set "HERE=C:\AI\Work_Folders\News_Macros\live_news_dashboard"
set "PORT=8765"
set "INTERVAL=30"
set "PYEXE="
set "PYVER="
set "OLD="

cd /d "%HERE%" 2>nul || (echo dashboard: directory not found: %HERE% & exit /b 1)

rem Resolve one usable interpreter up front. The project is standard library only,
rem so any Python 3 works; keep the absolute path for the spawn below.
for %%c in ("py -3" "python" "python3") do (
  if not defined PYEXE (
    for /f "delims=" %%e in ('%%~c -c "import sys,sqlite3,urllib.request;print(sys.executable)" 2^>nul') do (
      if exist "%%e" (set "PYEXE=%%e") else (set "PYEXE=")
    )
    if defined PYEXE (
      for /f "delims=" %%v in ('%%~c -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%v"
    )
  )
)
if not defined PYEXE (echo dashboard: no working python found & exit /b 1)

rem Report and clear whatever already holds the port. A stale listener makes the
rem new process exit on "port in use" while this script would report success.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT%" ^| findstr /i "LISTENING"') do (
  if not defined OLD set "OLD=%%p"
  taskkill /f /pid %%p >nul 2>&1
)
if defined OLD echo dashboard: replaced previous listener pid !OLD!

rem Spawn detached with no console at all, then verify the port. The spawn lives in
rem a Python helper because a hidden Start-Process child inherits this console, and
rem whatever launched this script would then wait for the server to exit. The helper
rem also rolls local.log / local.log.err to *.prev and opens them for the child.
set "DASH_PORT=%PORT%"
set "DASH_INTERVAL=%INTERVAL%"
"%PYEXE%" run_dashboard_bg.py
if errorlevel 1 (echo dashboard: spawn failed & exit /b 1)

rem Return only once the port actually answers, so a silent startup failure is visible.
for /l %%i in (1,1,20) do (
  for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT%" ^| findstr /i "LISTENING"') do (
    echo dashboard: listening on http://127.0.0.1:%PORT% ^(pid %%p, python %PYVER%^)
    echo dashboard: log at %HERE%\local.log.err
    if /i "%~1"=="open" start "" "http://127.0.0.1:%PORT%"
    exit /b 0
  )
  rem ping rather than timeout: timeout needs a console and returns immediately
  rem when stdin is redirected, which would spin this loop without any wait.
  ping -n 2 127.0.0.1 >nul 2>&1
)

echo dashboard: FAILED - no listener on port %PORT% after 40s
if exist "local.log.err" powershell -NoProfile -Command "Get-Content 'local.log.err' -Tail 12" 2>nul
exit /b 1
