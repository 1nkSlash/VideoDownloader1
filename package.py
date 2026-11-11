#!/usr/bin/env python3
"""После PyInstaller: собирает release/VideoDownloader/ (всё вшито: ffmpeg, deno, yt-dlp) и архив."""
import os, shutil, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
H = os.path.dirname(os.path.abspath(__file__))
os.chdir(H)
out = os.path.join("release", "VideoDownloader")
shutil.rmtree("release", ignore_errors=True)
os.makedirs(out)
if sys.platform == "darwin":
    shutil.copytree("dist/VideoDownloader.app", os.path.join(out, "VideoDownloader.app"), symlinks=True)
else:
    # onedir: dist/VideoDownloader/ целиком (exe + _internal с ffmpeg, deno и yt-dlp внутри)
    shutil.copytree("dist/VideoDownloader", out, dirs_exist_ok=True, symlinks=True)
name = {"win32": "windows", "darwin": "mac"}.get(sys.platform, "linux")
if sys.platform == "darwin":
    os.system(f'cd release && ditto -c -k --keepParent VideoDownloader VideoDownloader-{name}.zip')
elif sys.platform == "win32":
    shutil.make_archive(os.path.join("release", f"VideoDownloader-{name}"), "zip", "release", "VideoDownloader")
else:
    shutil.make_archive(os.path.join("release", f"VideoDownloader-{name}"), "gztar", "release", "VideoDownloader")
print("Готово: release/VideoDownloader/ и архив в release/")
