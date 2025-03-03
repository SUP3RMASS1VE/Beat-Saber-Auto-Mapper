@echo off
echo Starting...

REM Run the setup script with minimal output
python setup.py

REM Check if setup was successful
if %ERRORLEVEL% NEQ 0 (
    echo Setup failed.
    pause
    exit /b 1
)

REM Get FFmpeg path and add to PATH if it exists
for /f "tokens=*" %%i in ('where ffmpeg 2^>nul') do set FFMPEG_PATH=%%~dpi
if defined FFMPEG_PATH (
    set "PATH=%FFMPEG_PATH%;%PATH%"
    set "FFMPEG_ADDED_TO_PATH=true"
) else (
    REM Check if ffmpeg folder exists in the app directory
    if exist "ffmpeg\ffmpeg.exe" (
        set "PATH=%cd%\ffmpeg;%PATH%"
        set "FFMPEG_ADDED_TO_PATH=true"
    ) else (
        REM Check common FFmpeg installation locations
        if exist "C:\ffmpeg\ffmpeg.exe" (
            set "PATH=C:\ffmpeg;%PATH%"
            set "FFMPEG_ADDED_TO_PATH=true"
        ) else if exist "C:\Program Files\ffmpeg\ffmpeg.exe" (
            set "PATH=C:\Program Files\ffmpeg;%PATH%"
            set "FFMPEG_ADDED_TO_PATH=true"
        ) else if exist "%USERPROFILE%\ffmpeg\ffmpeg.exe" (
            set "PATH=%USERPROFILE%\ffmpeg;%PATH%"
            set "FFMPEG_ADDED_TO_PATH=true"
        ) else (
            set "FFMPEG_ADDED_TO_PATH=false"
        )
    )
)

REM Run the app with the environment properly set
python app.py

pause