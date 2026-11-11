#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Debian/Ubuntu: sudo apt install python3-venv python3-tk binutils
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-build.txt
python fetch_ffmpeg.py
pyinstaller --noconfirm --clean VideoDownloader.spec
python package.py
echo "Готово: release/VideoDownloader/ (всё вшито: ffmpeg, deno, yt-dlp — ничего ставить не нужно)"
