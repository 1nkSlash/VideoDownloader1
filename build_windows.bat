@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m venv .venv || goto :err
call .venv\Scripts\activate.bat
python -m pip install -U pip
pip install -r requirements-build.txt || goto :err
python fetch_ffmpeg.py || goto :err
pyinstaller --noconfirm --clean VideoDownloader.spec || goto :err
python package.py || goto :err
echo.
echo Готово: release\VideoDownloader\ (всё вшито: ffmpeg, deno, yt-dlp — ничего ставить не нужно)
pause
exit /b 0
:err
echo ОШИБКА СБОРКИ
pause
exit /b 1
