#!/usr/bin/env python3
"""Скачивает статические ffmpeg, ffprobe и deno для текущей ОС в папку bin/ (перед сборкой).
Всё это вшивается в программу, поэтому пользователю ничего ставить не нужно."""
import io, os, platform, shutil, stat, sys, tarfile, urllib.request, zipfile

try:  # Windows-раннеры GitHub печатают в cp1252 и падают на кириллице
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
UA = {"User-Agent": "Mozilla/5.0 build-script"}
machine = platform.machine().lower()
arm = machine in ("arm64", "aarch64")


def get(url):
    print("  ->", url, flush=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


def put(name, data):
    p = os.path.join(BIN, name)
    with open(p, "wb") as f:
        f.write(data)
    os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def have_all():
    ext = ".exe" if sys.platform == "win32" else ""
    return all(os.path.isfile(os.path.join(BIN, n + ext)) for n in ("ffmpeg", "ffprobe", "deno"))


def win():
    z = zipfile.ZipFile(io.BytesIO(get(
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip")))
    for n in z.namelist():
        b = os.path.basename(n)
        if b in ("ffmpeg.exe", "ffprobe.exe"):
            put(b, z.read(n))


def linux():
    arch = "arm64" if arm else "amd64"
    t = tarfile.open(fileobj=io.BytesIO(get(
        f"https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-{arch}-static.tar.xz")), mode="r:xz")
    for m in t.getmembers():
        b = os.path.basename(m.name)
        if m.isfile() and b in ("ffmpeg", "ffprobe"):
            put(b, t.extractfile(m).read())


def mac():
    arch = "arm64" if arm else "amd64"
    # (ffmpeg, ffprobe) — по очереди пробуем источники; первый — родные сборки под архитектуру
    sources = [
        (f"https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/ffmpeg.zip",
         f"https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/ffprobe.zip"),
        ("https://evermeet.cx/ffmpeg/getrelease/zip",
         "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"),
    ]
    for u_ffmpeg, u_ffprobe in sources:
        try:
            for name, url in (("ffmpeg", u_ffmpeg), ("ffprobe", u_ffprobe)):
                z = zipfile.ZipFile(io.BytesIO(get(url)))
                member = next(n for n in z.namelist() if os.path.basename(n) == name)
                put(name, z.read(member))
            return
        except Exception as e:
            print("  источник не сработал:", e, flush=True)


def deno():
    """JS-рантайм для yt-dlp (решение n-challenge YouTube). Тот же набор сборок, что и в программе."""
    if sys.platform == "win32":
        asset = "deno-x86_64-pc-windows-msvc.zip"
    elif sys.platform == "darwin":
        asset = "deno-aarch64-apple-darwin.zip" if arm else "deno-x86_64-apple-darwin.zip"
    else:
        asset = "deno-aarch64-unknown-linux-gnu.zip" if arm else "deno-x86_64-unknown-linux-gnu.zip"
    z = zipfile.ZipFile(io.BytesIO(get("https://github.com/denoland/deno/releases/latest/download/" + asset)))
    name = "deno.exe" if sys.platform == "win32" else "deno"
    put(name, z.read(name))


if __name__ == "__main__":
    os.makedirs(BIN, exist_ok=True)
    if have_all():
        print("ffmpeg/ffprobe/deno уже в bin/ — пропускаю загрузку"); sys.exit(0)
    ext = ".exe" if sys.platform == "win32" else ""
    if not all(os.path.isfile(os.path.join(BIN, n + ext)) for n in ("ffmpeg", "ffprobe")):
        print("Скачиваю ffmpeg для", sys.platform, machine)
        {"win32": win, "darwin": mac}.get(sys.platform, linux)()
    if not os.path.isfile(os.path.join(BIN, "deno" + ext)):
        print("Скачиваю deno для", sys.platform, machine)
        deno()
    if not have_all():
        sys.exit("ОШИБКА: ffmpeg/ffprobe/deno не скачались. Положите их в bin/ вручную.")
    print("Готово:", os.listdir(BIN))
