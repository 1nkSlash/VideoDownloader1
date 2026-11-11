# -*- mode: python ; coding: utf-8 -*-
# Единый spec для Windows / macOS / Linux.  Запуск: pyinstaller VideoDownloader.spec
import os, sys
from PyInstaller.utils.hooks import collect_all

APP = "VideoDownloader"
datas, binaries, hiddenimports = [], [], []

# Всё вшито в сборку, чтобы для запуска ничего не нужно было ставить и скачивать:
#   yt-dlp + yt-dlp-ejs (пакеты Python), ffmpeg/ffprobe/deno (папка bin/ внутри сборки).
# Обновлённый yt-dlp из кнопки «Обновить» кладётся в профиль пользователя и перекрывает вшитый.
for pkg in ("yt_dlp", "yt_dlp_ejs", "certifi", "mutagen", "websockets",
            "requests", "urllib3", "brotli", "Cryptodome"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception as e:
        print(f"[spec] пропуск {pkg}: {e}")

# версия вшитого yt-dlp: по ней программа решает, не устарела ли скачанная в профиль копия
import yt_dlp.version
os.makedirs("build", exist_ok=True)
with open(os.path.join("build", "bundled_ytdlp_version.txt"), "w", encoding="utf-8") as _f:
    _f.write(yt_dlp.version.__version__)
datas.append((os.path.join("build", "bundled_ytdlp_version.txt"), "."))

# ffmpeg, ffprobe, deno (их кладёт в bin/ fetch_ffmpeg.py) — как данные, а не binaries:
# PyInstaller не трогает такие файлы (не анализирует, не стрипает), права на запуск сохраняются.
_missing = [n for n in ("ffmpeg", "ffprobe", "deno")
            if not os.path.isfile(os.path.join("bin", n + (".exe" if sys.platform == "win32" else "")))]
if _missing:
    raise SystemExit(f"[spec] в bin/ нет: {', '.join(_missing)} — сначала запустите python fetch_ffmpeg.py")
for _n in os.listdir("bin"):
    if os.path.isfile(os.path.join("bin", _n)):
        datas.append((os.path.join("bin", _n), "bin"))

# yt-dlp может подгружаться из профиля пользователя (обновление) и не виден анализатору PyInstaller,
# поэтому все стандартные модули, которые он импортирует (xml.etree, html.parser, sqlite3 ...), добавляем явно.
# Берём список из цикла принудительных импортов в начале ytdl_gui.py + запасной минимум.
import ast
_src = open("ytdl_gui.py", encoding="utf-8").read()
for _node in ast.parse(_src).body:
    if isinstance(_node, ast.For) and isinstance(_node.iter, (ast.Tuple, ast.List)):
        hiddenimports += [e.value.strip() for e in _node.iter.elts
                          if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        break
hiddenimports += [
    "xml", "xml.etree", "xml.etree.ElementTree", "xml.dom", "xml.dom.minidom", "xml.sax",
    "html", "html.parser", "html.entities", "http", "http.client", "http.cookiejar", "http.cookies",
    "sqlite3", "ssl", "secrets", "unicodedata", "mimetypes", "optparse", "netrc", "uuid", "zlib",
    "hashlib", "hmac", "struct", "difflib", "email.utils", "email.message", "encodings.idna",
    "urllib.request", "urllib.parse", "urllib.error", "concurrent.futures", "ctypes", "ctypes.util",
    "ctypes.wintypes", "shlex", "tempfile", "platform", "socketserver", "http.server", "zipfile", "tarfile",
]
hiddenimports = sorted(set(hiddenimports))

icon = None
for cand in ("icon.ico" if sys.platform == "win32" else
             "icon.icns" if sys.platform == "darwin" else "icon.png",):
    if os.path.isfile(cand):
        icon = cand

a = Analysis(["ytdl_gui.py"], pathex=["."], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
             excludes=[], noarchive=False)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    # .app: onedir (onefile внутри .app медленный и ломает подпись)
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP,
              console=False, icon=icon)
    coll = COLLECT(exe, a.binaries, a.datas, name=APP)
    app = BUNDLE(coll, name=f"{APP}.app", icon=icon,
                 bundle_identifier="com.videodownloader.app",
                 info_plist={"CFBundleName": APP, "CFBundleDisplayName": APP,
                             "CFBundleShortVersionString": "1.0.0",
                             "NSHighResolutionCapable": True})
else:
    # Windows / Linux: onedir. Один файл пришлось бы распаковывать целиком (~250 МБ с ffmpeg и deno)
    # в temp при КАЖДОМ запуске — это секунды ожидания. Папка запускается мгновенно и работает офлайн.
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP,
              console=False, icon=icon, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name=APP, upx=False)
