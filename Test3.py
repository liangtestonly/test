
@echo off
title DMSP TLE Scheduler (Continuous 12h Cycle)
echo ====================================================================
echo 📡 DMSP SATELLITE TLE DOWNLOAD SCHEDULER LAUNCHER 📡
echo ====================================================================
echo.
echo [+] Activating Python Virtual Environment (.venv)...
set SCRIPT_DIR=%~dp0
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"

echo [+] Spawning separate, dedicated Console window...
echo [+] The TLE Scheduler will keep running continuously in the background.
echo.

:: Spawns the scheduler inside its own separate cmd window, keeping it isolated!
start "DMSP TLE Background Downloader" "%SCRIPT_DIR%.venv\Scripts\python.exe" -u "%SCRIPT_DIR%getalt\tle_test.py"

echo ====================================================================
echo [✓] SUCCESS: Separate Console Window Spawned Successfully!
echo [!] You can safely close THIS launcher window now.
echo ====================================================================
pause
