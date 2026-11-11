#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Нужен Python с Tk (python.org или `brew install python-tk`)
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-build.txt
python fetch_ffmpeg.py
pyinstaller --noconfirm --clean VideoDownloader.spec
codesign --force --deep --sign - dist/VideoDownloader.app || true
python package.py
echo "Готово: release/VideoDownloader/ (всё вшито: ffmpeg, deno, yt-dlp — ничего ставить не нужно)"
echo "Первый запуск: xattr -cr VideoDownloader.app (или ПКМ → Открыть)"
