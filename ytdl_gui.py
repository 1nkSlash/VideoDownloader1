#!/usr/bin/env python3
"""
Video Downloader с графическим интерфейсом (YouTube, Twitch и другие сайты,
которые поддерживает yt-dlp).

Портативная версия:
- Внешняя папка `lib` рядом с exe/скриптом с пакетом yt-dlp
- Внешняя папка `bin` рядом с exe/скриптом с бинарниками ffmpeg.exe / ffprobe.exe
- Прямое автообновление yt-dlp прямо из exe (скачивание свежего релиза с PyPI в папку `lib`)
"""

import base64
import ctypes
import glob
import importlib
import json
import os
import platform
import queue
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback
import tkinter as tk
import urllib.request
import zipfile
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from urllib.parse import quote

# Принудительно включаем все стандартные модули Python в сборку PyInstaller,
# чтобы внешний обновляемый yt_dlp из папки lib всегда имел к ним доступ
for _mod_name in (
    "asyncio", "cgi", "cmath", " cmd", "code", "codecs", "codeop", "collections",
    "colorsys", "compileall", "concurrent.futures", "configparser", "contextlib",
    "contextvars", "copy", "copyreg", "csv", "ctypes", "ctypes.wintypes", "dataclasses",
    "datetime", "decimal", "difflib", "dis", "email", "email.FeedParser", "email.header",
    "email.message", "email.parser", "email.utils", "encodings.idna", " encodings.punycode",
    "enum", "errno", "faulthandler", "filecmp", "fileinput", "fnmatch", "fractions",
    "ftplib", "functools", "gc", "genericpath", "getopt", "getpass", "gettext", "glob",
    "gzip", "hashlib", "heapq", "hmac", "html", "html.entities", "html.parser",
    "http", "http.client", "http.cookiejar", "http.cookies", "http.server",
    "imaplib", "imghdr", "imp", "importlib", "importlib.abc", "importlib.machinery",
    "importlib.metadata", "importlib.resources", "importlib.util", "inspect", "io",
    "ipaddress", "itertools", "json", "keyword", "linecache", "locale", "logging",
    "logging.handlers", "lzma", "mailbox", "mailcap", "marshal", "math", "mimetypes",
    "mmap", "modulefinder", "msilib", "msvcrt", "multiprocessing", "netrc", "nntplib",
    "ntpath", "nturl2path", "numbers", "opcode", "operator", "optparse", "os",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform",
    "plistlib", "poplib", "posixpath", "pprint", "profile", "pstats", "py_compile",
    "pyclbr", "pydoc", "queue", "quopri", "random", "re", "reprlib", "rlcompleter",
    "runpy", "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil",
    "signal", "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver",
    "sqlite3", "ssl", "stat", "statistics", "string", "stringprep", "struct",
    "subprocess", "sunau", "symtable", "sys", "sysconfig", "tabnanny", "tarfile",
    "telnetlib", "tempfile", "textwrap", "threading", "time", "timeit", "tkinter",
    "token", "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty",
    "types", "typing", "unicodedata", "unittest", "urllib", "urllib.error",
    "urllib.parse", "urllib.request", "urllib.response", "urllib.robotparser",
    "uu", "uuid", "venv", "warnings", "wave", "weakref", "webbrowser", "winreg",
    "winsound", "wsgiref", "wsgiref.handlers", "wsgiref.headers", "wsgiref.simple_server",
    "wsgiref.util", "xdrlib", "xml", "xml.dom", "xml.dom.minidom", "xml.dom.pulldom",
    "xml.etree", "xml.etree.ElementTree", "xml.parsers.expat", "xml.sax",
    "xml.sax.handler", "xml.sax.saxutils", "xml.sax.xmlreader", "xmlrpc",
    "xmlrpc.client", "xmlrpc.server", "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
    "certifi", "mutagen", "websockets", "urllib3", "requests", "brotli", "Cryptodome"
):
    try:
        importlib.import_module(_mod_name.strip())
    except Exception:
        pass

FROZEN = getattr(sys, "frozen", False)
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
PASTE_KEY = "Cmd+V" if IS_MAC else "Ctrl+V"
BASE_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
# На macOS внутри .app писать нельзя (подпись, App Translocation), поэтому lib/bin/auth
# собранного приложения лежат в ~/Library/Application Support/VideoDownloader
if FROZEN:
    # Всё необходимое (ffmpeg, yt-dlp, deno) вшито в сборку. DATA_DIR — только для обновлений
    # yt-dlp, которые перекрывают вшитую версию; лежит в профиле, рядом с программой не пишем.
    if IS_MAC:
        DATA_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "VideoDownloader")
    elif IS_WIN:
        DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA")
                                or os.path.join(os.path.expanduser("~"), "AppData", "Local"),
                                "VideoDownloader")
    else:
        DATA_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME")
                                or os.path.join(os.path.expanduser("~"), ".config"), "VideoDownloader")
else:
    DATA_DIR = BASE_DIR
# Вшитые в сборку утилиты (ffmpeg, ffprobe, deno): <папка распаковки PyInstaller>/bin
BUNDLE_DIR = getattr(sys, "_MEIPASS", None) if FROZEN else None
BUNDLED_BIN = os.path.join(BUNDLE_DIR, "bin") if BUNDLE_DIR else None
os.makedirs(DATA_DIR, exist_ok=True)
if FROZEN and IS_LINUX:
    _orig_ld = os.environ.get("LD_LIBRARY_PATH_ORIG")
    if _orig_ld is not None:
        os.environ["LD_LIBRARY_PATH"] = _orig_ld
    else:
        os.environ.pop("LD_LIBRARY_PATH", None)

if IS_WIN:
    FFMPEG_HINT = "ffmpeg должен быть вшит в программу — скачайте сборку заново или положите ffmpeg.exe в папку bin: " + os.path.join(DATA_DIR, "bin")
elif IS_MAC:
    FFMPEG_HINT = ("Установите ffmpeg командой «brew install ffmpeg» в Терминале "
                   "или положите ffmpeg в папку bin: " + os.path.join(DATA_DIR, "bin"))
else:
    FFMPEG_HINT = ("Установите ffmpeg через менеджер пакетов (например, «sudo apt install ffmpeg») "
                   "или положите его в папку bin: " + os.path.join(DATA_DIR, "bin"))

# Настройки, история и сохранённый вход в аккаунт — в профиле пользователя, а не рядом с exe:
# Windows: %LOCALAPPDATA%\\VideoDownloader, macOS: ~/Library/Application Support/VideoDownloader,
# Linux: ~/.config/VideoDownloader
if IS_WIN:
    CONFIG_DIR = os.path.join(os.environ.get("LOCALAPPDATA")
                              or os.path.join(os.path.expanduser("~"), "AppData", "Local"),
                              "VideoDownloader")
elif IS_MAC:
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "VideoDownloader")
else:
    CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME")
                              or os.path.join(os.path.expanduser("~"), ".config"), "VideoDownloader")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
# Библиотеки и утилиты хранятся прямо в папке с программой
LIB_DIR = os.path.join(DATA_DIR, "lib")
BIN_DIR = os.path.join(DATA_DIR, "bin")
# Сохранённый вход в аккаунт Google/YouTube: отдельный профиль браузера и файл сессии
AUTH_DIR = os.path.join(CONFIG_DIR, "auth")
AUTH_PROFILE = os.path.join(AUTH_DIR, "profile")
AUTH_COOKIES = os.path.join(AUTH_DIR, "youtube_cookies.txt")
HISTORY_PATH = os.path.join(CONFIG_DIR, "history.json")
HISTORY_MAX = 500
TARGET_OS_LABELS = {"auto": "Авто (эта система)", "windows": "Windows",
                    "macos": "macOS", "linux": "Linux"}
TARGET_OS_NOTES = {
    "auto": "Кодеки и контейнер — как выбрано выше. Имена файлов — под текущую систему.",
    "windows": "Имена файлов без символов, запрещённых в Windows/NTFS (удобно на флешку или диск "
               "для Windows). Кодеки — как выбрано выше.",
    "macos": "Для QuickTime/Музыки: видео всегда в mp4 с H.264 + AAC, аудио «оригинал» — m4a. "
             "Выше 1080p доступно только если у видео есть H.264.",
    "linux": "Без ограничений по кодекам и контейнерам. Имена файлов — как в Linux.",
}
MAX_SAFE_PARALLEL = 3
PARALLEL_NOTE = ("⚠ Больше 3 одновременных загрузок — рискованно: YouTube может сильно снизить "
                 "скорость, начать показывать капчу или временно заблокировать ваш IP-адрес "
                 "и аккаунт. Обычно хватает 1–2.")
STATE_LABEL = {"queued": "В очереди", "running": "Загрузка", "done": "Готово",
               "error": "Ошибка", "cancelled": "Отменено"}

os.makedirs(LIB_DIR, exist_ok=True)
os.makedirs(BIN_DIR, exist_ok=True)


def _migrate_old_files():
    """Переносит файлы из старых мест (домашняя папка, папка рядом с программой)."""
    home = os.path.expanduser("~")
    moves = [(os.path.join(home, ".ytdl_gui.json"), CONFIG_PATH),
             (os.path.join(home, ".ytdl_gui_history.json"), HISTORY_PATH),
             (os.path.join(DATA_DIR, "auth"), AUTH_DIR)]
    for old, new in moves:
        try:
            if os.path.exists(old) and not os.path.exists(new) \
                    and os.path.abspath(old) != os.path.abspath(new):
                shutil.move(old, new)
        except OSError:
            pass


_migrate_old_files()

if FROZEN:
    for _name in ("stdout", "stderr"):
        if getattr(sys, _name) is None:
            setattr(sys, _name, open(os.devnull, "w"))

# macOS: папка, в которой лежит VideoDownloader.app (там же может лежать папка bin с ffmpeg)
APP_DIR = (os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))
           if (IS_MAC and FROZEN) else BASE_DIR)
# Добавляем папки bin и BASE_DIR в PATH, чтобы подхватывались локальные ffmpeg/ffprobe/deno
_extra_paths = [BIN_DIR, os.path.join(APP_DIR, "bin"), BASE_DIR]
if BUNDLED_BIN:
    _extra_paths.insert(0, BUNDLED_BIN)   # вшитые ffmpeg/ffprobe/deno — в приоритете
if BUNDLE_DIR:
    _extra_paths.append(BUNDLE_DIR)
os.environ["PATH"] = os.pathsep.join(_extra_paths) + os.pathsep + os.environ.get("PATH", "")
if IS_MAC:
    # приложения, запущенные из Finder, не наследуют PATH из терминала — добавляем Homebrew/MacPorts
    for _d in ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"):
        if os.path.isdir(_d) and _d not in os.environ["PATH"].split(os.pathsep):
            os.environ["PATH"] += os.pathsep + _d

# Папка lib имеет наивысший приоритет, чтобы обновлённый yt-dlp перекрывал встроенный
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

MODE_VIDEO = "Видео"
MODE_AUDIO = "Только аудио"
AUDIO_ORIGINAL = "оригинал"
AUDIO_FORMATS = ["mp3", "m4a", "opus", "flac", "wav", AUDIO_ORIGINAL]
QUALITIES = [
    ("Максимальное", None),
    ("2160p (4K)", 2160),
    ("1440p (2K)", 1440),
    ("1080p (Full HD)", 1080),
    ("720p (HD)", 720),
    ("480p", 480),
    ("360p", 360),
    ("240p", 240),
    ("144p", 144),
]


def _version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v)))


def _make_opener(proxy=None):
    handlers = []
    if proxy and proxy.split("://")[0] in ("http", "https"):
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def fetch_latest_pypi_info(proxy=None):
    """Возвращает (version, wheel_url) последнего релиза yt-dlp с PyPI."""
    opener = _make_opener(proxy)
    req = urllib.request.Request(
        "https://pypi.org/pypi/yt-dlp/json",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VideoDownloader/1.0"}
    )
    with opener.open(req, timeout=20) as r:
        data = json.load(r)
    ver = data["info"]["version"]
    wheel_url = None
    for item in data.get("urls", []):
        if item.get("packagetype") == "bdist_wheel" and item.get("filename", "").endswith(".whl"):
            wheel_url = item.get("url")
            break
    return ver, wheel_url


def fetch_latest_version(proxy=None):
    ver, _ = fetch_latest_pypi_info(proxy)
    return ver


def install_or_update_ytdlp(proxy=None):
    """Скачивает свежий wheel-пакет yt-dlp напрямую с PyPI и распаковывает его в папку lib/.
    Работает автономно внутри .exe без установленного в системе Python и pip!"""
    try:
        ver, wheel_url = fetch_latest_pypi_info(proxy)
        if not wheel_url:
            raise RuntimeError("Не найден wheel-архив yt-dlp на PyPI.")

        opener = _make_opener(proxy)
        req = urllib.request.Request(
            wheel_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VideoDownloader/1.0"}
        )
        os.makedirs(LIB_DIR, exist_ok=True)
        tmp_whl = os.path.join(LIB_DIR, f"yt_dlp-{ver}.whl.tmp")
        with opener.open(req, timeout=120) as resp, open(tmp_whl, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)

        tmp_extract = os.path.join(LIB_DIR, "_extract_tmp")
        if os.path.exists(tmp_extract):
            shutil.rmtree(tmp_extract, ignore_errors=True)
        os.makedirs(tmp_extract, exist_ok=True)

        with zipfile.ZipFile(tmp_whl, "r") as zf:
            zf.extractall(tmp_extract)

        try:
            os.remove(tmp_whl)
        except OSError:
            pass

        # Заменяем старый yt_dlp и dist-info в папке lib на новую версию
        for item in os.listdir(LIB_DIR):
            if item == "_extract_tmp":
                continue
            if item == "yt_dlp" or (item.startswith("yt_dlp-") and item.endswith(".dist-info")):
                target_p = os.path.join(LIB_DIR, item)
                if os.path.isdir(target_p):
                    shutil.rmtree(target_p, ignore_errors=True)
                else:
                    try:
                        os.remove(target_p)
                    except OSError:
                        pass

        for item in os.listdir(tmp_extract):
            if item == "yt_dlp" or (item.startswith("yt_dlp-") and item.endswith(".dist-info")):
                shutil.move(os.path.join(tmp_extract, item), os.path.join(LIB_DIR, item))

        shutil.rmtree(tmp_extract, ignore_errors=True)
        importlib.invalidate_caches()
        return True, f"Успешно установлен yt-dlp {ver} в {LIB_DIR}"
    except Exception as e:  # noqa: BLE001
        # Если мы не в exe и есть системный pip — пробуем запасной вариант через pip
        if not FROZEN:
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--target", LIB_DIR,
                   "--disable-pip-version-check", "--no-warn-script-location", "yt-dlp[default]"]
            if proxy and proxy.split("://")[0] in ("http", "https"):
                cmd += ["--proxy", proxy]
            kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            try:
                r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace",
                                   timeout=600, stdin=subprocess.DEVNULL, **kw)
                importlib.invalidate_caches()
                if r.returncode == 0:
                    return True, (r.stdout + r.stderr).strip()
            except Exception:  # noqa: BLE001
                pass
        return False, str(e)


# ------------------------------------------- JS-рантайм и решатель n-challenge YouTube
# Без них YouTube отдаёт только картинки -> "Requested format is not available".
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VideoDownloader/1.0"}


def _pypi_json(package, version=None, proxy=None):
    url = f"https://pypi.org/pypi/{package}/" + (f"{version}/" if version else "") + "json"
    with _make_opener(proxy).open(urllib.request.Request(url, headers=_UA), timeout=20) as r:
        return json.load(r)


def _wheel_url(data):
    for item in data.get("urls", []):
        if item.get("packagetype") == "bdist_wheel" and item.get("filename", "").endswith(".whl"):
            return item.get("url")
    return None


def _required_ejs_version():
    """Версия yt-dlp-ejs, которую требует установленный в lib/ yt-dlp (или None)."""
    if LIB_DIR not in sys.path:   # lib не используется (вшитый yt-dlp новее) — его требования не важны
        return None
    for path in glob.glob(os.path.join(LIB_DIR, "yt_dlp-*.dist-info", "METADATA")):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                txt = f.read()
        except OSError:
            continue
        m = re.search(r"^Requires-Dist:\s*yt-dlp-ejs\s*==\s*([\w.]+)", txt, re.M | re.I)
        if m:
            return m.group(1)
    return None


def installed_ejs_version():
    for d in (glob.glob(os.path.join(LIB_DIR, "yt_dlp_ejs-*.dist-info")) if LIB_DIR in sys.path else []):
        if os.path.isdir(os.path.join(LIB_DIR, "yt_dlp_ejs")):
            return os.path.basename(d)[len("yt_dlp_ejs-"):-len(".dist-info")]
    try:
        import importlib.util
        if importlib.util.find_spec("yt_dlp_ejs") is not None:  # вшит в exe
            return "bundled"
    except Exception:  # noqa: BLE001
        pass
    return None


def install_ejs(proxy=None):
    """Скачивает пакет yt-dlp-ejs (скрипты-решатели) с PyPI в папку lib/."""
    try:
        want = _required_ejs_version()
        have = installed_ejs_version()
        if have and (want is None or want == have or have == "bundled"):
            return True, f"yt-dlp-ejs {have} уже установлен."
        data = _pypi_json("yt-dlp-ejs", want, proxy)
        ver = data["info"]["version"]
        url = _wheel_url(data)
        if not url:
            raise RuntimeError("Не найден wheel-архив yt-dlp-ejs на PyPI.")
        os.makedirs(LIB_DIR, exist_ok=True)
        tmp_whl = os.path.join(LIB_DIR, f"yt_dlp_ejs-{ver}.whl.tmp")
        with _make_opener(proxy).open(urllib.request.Request(url, headers=_UA), timeout=120) as resp, \
                open(tmp_whl, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)
        tmp_extract = os.path.join(LIB_DIR, "_extract_ejs_tmp")
        shutil.rmtree(tmp_extract, ignore_errors=True)
        os.makedirs(tmp_extract, exist_ok=True)
        with zipfile.ZipFile(tmp_whl, "r") as zf:
            zf.extractall(tmp_extract)
        try:
            os.remove(tmp_whl)
        except OSError:
            pass
        for item in os.listdir(LIB_DIR):
            if item == "yt_dlp_ejs" or (item.startswith("yt_dlp_ejs-") and item.endswith(".dist-info")):
                shutil.rmtree(os.path.join(LIB_DIR, item), ignore_errors=True)
        for item in os.listdir(tmp_extract):
            if item == "yt_dlp_ejs" or (item.startswith("yt_dlp_ejs-") and item.endswith(".dist-info")):
                shutil.move(os.path.join(tmp_extract, item), os.path.join(LIB_DIR, item))
        shutil.rmtree(tmp_extract, ignore_errors=True)
        importlib.invalidate_caches()
        return True, f"Установлен yt-dlp-ejs {ver}."
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def find_js_runtime():
    """Ищет JS-рантайм для yt-dlp. Возвращает (имя, путь) или None. bin/ уже в PATH."""
    for name in ("deno", "node", "bun"):
        exe = shutil.which(name)
        if exe:
            return name, exe
    return None


def _deno_asset():
    arm = platform.machine().lower() in ("arm64", "aarch64")
    if os.name == "nt":
        return "deno-x86_64-pc-windows-msvc.zip"
    if sys.platform == "darwin":
        return "deno-aarch64-apple-darwin.zip" if arm else "deno-x86_64-apple-darwin.zip"
    return "deno-aarch64-unknown-linux-gnu.zip" if arm else "deno-x86_64-unknown-linux-gnu.zip"


def install_deno(proxy=None):
    """Скачивает Deno (один exe) с GitHub в папку bin/."""
    try:
        url = "https://github.com/denoland/deno/releases/latest/download/" + _deno_asset()
        os.makedirs(BIN_DIR, exist_ok=True)
        tmp_zip = os.path.join(BIN_DIR, "deno.zip.tmp")
        with _make_opener(proxy).open(urllib.request.Request(url, headers=_UA), timeout=180) as resp, \
                open(tmp_zip, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)
        exe_name = "deno.exe" if os.name == "nt" else "deno"
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            with zf.open(exe_name) as src, open(os.path.join(BIN_DIR, exe_name), "wb") as dst:
                shutil.copyfileobj(src, dst)
        try:
            os.remove(tmp_zip)
        except OSError:
            pass
        if os.name != "nt":
            os.chmod(os.path.join(BIN_DIR, exe_name), 0o755)
        return True, f"Deno установлен в {BIN_DIR}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def js_needs_setup():
    if find_js_runtime() is None:
        return True
    have, want = installed_ejs_version(), _required_ejs_version()
    return have is None or (want is not None and have not in (want, "bundled"))


_LAST_IMPORT_ERR = ""


def _bundled_ytdlp_version():
    """Версия yt-dlp, вшитого в сборку (файл кладёт VideoDownloader.spec), или None."""
    if not BUNDLE_DIR:
        return None
    try:
        with open(os.path.join(BUNDLE_DIR, "bundled_ytdlp_version.txt"), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _lib_ytdlp_version():
    for d in glob.glob(os.path.join(LIB_DIR, "yt_dlp-*.dist-info")):
        return os.path.basename(d)[len("yt_dlp-"):-len(".dist-info")]
    return None


def _import_ytdlp():
    """Импортирует yt-dlp: из lib/ (если это обновление новее вшитого), иначе вшитый в программу."""
    global _LAST_IMPORT_ERR
    _b, _l = _bundled_ytdlp_version(), _lib_ytdlp_version()
    if _b and _l and _version_tuple(_l) <= _version_tuple(_b):
        # lib устарела (программу обновили) — вшитая версия не хуже, не даём lib её перекрывать
        while LIB_DIR in sys.path:
            sys.path.remove(LIB_DIR)
    elif LIB_DIR not in sys.path:
        sys.path.insert(0, LIB_DIR)
    for name in [n for n in list(sys.modules) if n == "yt_dlp" or n.startswith("yt_dlp.")]:
        del sys.modules[name]
    importlib.invalidate_caches()
    try:
        import yt_dlp as mod
        return mod
    except Exception as e1:  # noqa: BLE001
        _LAST_IMPORT_ERR = traceback.format_exc()
        if LIB_DIR in sys.path:
            sys.path.remove(LIB_DIR)
            for name in [n for n in list(sys.modules) if n == "yt_dlp" or n.startswith("yt_dlp.")]:
                del sys.modules[name]
            try:
                import yt_dlp as mod
                return mod
            except Exception:  # noqa: BLE001
                _LAST_IMPORT_ERR = traceback.format_exc()
                return None
        return None


yt_dlp = _import_ytdlp()

if yt_dlp is None:
    # Первый запуск: yt-dlp не вшит в программу — скачиваем его в папку lib автоматически
    _root = tk.Tk()
    _root.title("Video Downloader")
    _root.resizable(False, False)
    tk.Label(_root, text="Первый запуск: скачиваю yt-dlp в папку lib…\nПодождите несколько секунд.",
             padx=36, pady=26, font=("Segoe UI", 10)).pack()
    _root.update_idletasks()
    _root.geometry("+%d+%d" % ((_root.winfo_screenwidth() - _root.winfo_reqwidth()) // 2,
                               (_root.winfo_screenheight() - _root.winfo_reqheight()) // 3))
    _root.update()
    _ok, _out = install_or_update_ytdlp()
    if _ok:
        yt_dlp = _import_ytdlp()
    if yt_dlp is None:
        messagebox.showerror("Ошибка", "Не удалось скачать yt-dlp (нужен интернет):\n"
                             f"{_out}\n\nПричина импорта:\n{_LAST_IMPORT_ERR[-600:]}")
        sys.exit(1)
    _root.destroy()

YTDLP_VERSION = yt_dlp.version.__version__

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\[[0-9;]*m")


def strip_ansi(text):
    return ANSI_RE.sub("", str(text))


def site_name(url):
    u = url.lower()
    if "twitch.tv" in u:
        return "Twitch"
    if "youtu" in u:
        return "YouTube"
    return "другой сайт"


def build_video_format(container, height, compat=False):
    """Формат yt-dlp: лучшее качество не выше height (None = без ограничения).
    compat=True — H.264 + AAC в mp4 (воспроизводится в QuickTime на macOS/iOS)."""
    h = f"[height<={height}]" if height else ""
    if compat:
        return (f"bv*{h}[vcodec^=avc1]+ba[acodec^=mp4a]/bv*{h}[ext=mp4]+ba[ext=m4a]/"
                f"b{h}[ext=mp4]/bv*{h}+ba/b{h}/b")
    if container == "mp4":
        return f"bv*{h}[ext=mp4]+ba[ext=m4a]/bv*{h}+ba/b{h}/b"
    if container == "webm":
        return f"bv*{h}[ext=webm]+ba[ext=webm]/bv*{h}+ba/b{h}/b"
    return f"bv*{h}+ba/b{h}/b"


def find_ffmpeg():
    """Ищет ffmpeg: сначала в локальной папке bin/ и рядом с exe, затем в PATH и системе."""
    local_dirs = [BIN_DIR, os.path.join(APP_DIR, "bin"), BASE_DIR]
    if BUNDLED_BIN:
        local_dirs.insert(0, BUNDLED_BIN)
    if BUNDLE_DIR:
        local_dirs.append(BUNDLE_DIR)
    for d in local_dirs:
        if os.path.isfile(os.path.join(d, "ffmpeg.exe")) or os.path.isfile(os.path.join(d, "ffmpeg")):
            return d

    exe = shutil.which("ffmpeg")
    if exe:
        return os.path.dirname(exe)

    candidates = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidates += glob.glob(os.path.join(
            local, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "**", "bin"), recursive=True)
        candidates.append(os.path.join(local, "Microsoft", "WinGet", "Links"))
    candidates += [
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\ProgramData\chocolatey\bin",
    ]
    if IS_MAC:
        candidates += ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]
    for d in candidates:
        if os.path.isfile(os.path.join(d, "ffmpeg.exe")) or os.path.isfile(os.path.join(d, "ffmpeg")):
            return d
    return None


def _dpapi(data, encrypt):
    """Шифрование средствами Windows (DPAPI)."""
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    func = ctypes.windll.crypt32.CryptProtectData if encrypt else ctypes.windll.crypt32.CryptUnprotectData
    if not func(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("DPAPI error")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


_KEYCHAIN_SVC = "VideoDownloaderProxy"
_KEYCHAIN_ACC = "ytdl_gui"


def _keychain_set(text):
    r = subprocess.run(["security", "add-generic-password", "-U", "-a", _KEYCHAIN_ACC,
                        "-s", _KEYCHAIN_SVC, "-w", text],
                       capture_output=True, timeout=15, stdin=subprocess.DEVNULL)
    return r.returncode == 0


def _keychain_get():
    r = subprocess.run(["security", "find-generic-password", "-a", _KEYCHAIN_ACC,
                        "-s", _KEYCHAIN_SVC, "-w"],
                       capture_output=True, timeout=15, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        return ""
    return r.stdout.decode("utf-8", "replace").rstrip("\n")


def _libsecret_set(text):
    r = subprocess.run(["secret-tool", "store", "--label", "Video Downloader proxy",
                        "service", _KEYCHAIN_SVC, "account", _KEYCHAIN_ACC],
                       input=text.encode("utf-8"), capture_output=True, timeout=15)
    return r.returncode == 0


def _libsecret_get():
    r = subprocess.run(["secret-tool", "lookup", "service", _KEYCHAIN_SVC, "account", _KEYCHAIN_ACC],
                       capture_output=True, timeout=15, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        return ""
    return r.stdout.decode("utf-8", "replace").rstrip("\n")


def encrypt_secret(text):
    if not text:
        return ""
    if IS_LINUX and shutil.which("secret-tool"):
        try:
            if _libsecret_set(text):
                return "libsecret:"
        except Exception:  # noqa: BLE001
            pass
    if IS_MAC:
        try:
            if _keychain_set(text):
                return "keychain:"
        except Exception:  # noqa: BLE001
            pass
    raw = text.encode("utf-8")
    if os.name == "nt":
        try:
            return "dpapi:" + base64.b64encode(_dpapi(raw, True)).decode("ascii")
        except Exception:  # noqa: BLE001
            pass
    return "b64:" + base64.b64encode(raw).decode("ascii")


def decrypt_secret(token):
    if not token:
        return ""
    try:
        kind, _, payload = token.partition(":")
        if kind == "keychain":
            return _keychain_get()
        if kind == "libsecret":
            return _libsecret_get()
        raw = base64.b64decode(payload)
        if kind == "dpapi":
            raw = _dpapi(raw, False)
        return raw.decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""


# ------------------------------------------------- вход в аккаунт (Chromium + CDP)
LOGIN_URL = ("https://accounts.google.com/ServiceLogin?service=youtube&hl=ru"
             "&continue=https%3A%2F%2Fwww.youtube.com%2F")
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def find_chromium():
    """Ищет установленный Chrome / Edge / Brave и т.п. (любой браузер на движке Chromium)."""
    cands = []
    if os.name == "nt":
        roots = [os.environ.get(k, "") for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        rels = [r"Google\Chrome\Application\chrome.exe",
                r"Microsoft\Edge\Application\msedge.exe",
                r"BraveSoftware\Brave-Browser\Application\brave.exe",
                r"Vivaldi\Application\vivaldi.exe",
                r"Chromium\Application\chrome.exe"]
        for rel in rels:
            for root in roots:
                if root:
                    cands.append(os.path.join(root, rel))
    elif sys.platform == "darwin":
        cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                  "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
                  "/Applications/Chromium.app/Contents/MacOS/Chromium"]
        home_apps = os.path.join(os.path.expanduser("~"), "Applications")
        cands += [os.path.join(home_apps, rel) for rel in (
            "Google Chrome.app/Contents/MacOS/Google Chrome",
            "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "Brave Browser.app/Contents/MacOS/Brave Browser")]
    else:
        for n in ("google-chrome", "google-chrome-stable", "chrome", "microsoft-edge",
                  "microsoft-edge-stable", "brave-browser", "brave-browser-stable", "brave",
                  "vivaldi", "vivaldi-stable", "chromium", "chromium-browser"):
            w = shutil.which(n)
            if w:
                cands.append(w)
    return next((c for c in cands if os.path.isfile(c)), None)


def _free_port():
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


class _MiniWS:
    """Минимальный WebSocket-клиент (только ws://, без зависимостей) для протокола CDP."""

    def __init__(self, url, timeout=30):
        m = re.match(r"ws://([^/:]+):(\d+)(/.*)", url)
        if not m:
            raise ValueError("Некорректный адрес отладки браузера")
        host, port, path = m.group(1), int(m.group(2)), m.group(3)
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self._buf = b""
        self._id = 0
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
        while b"\r\n\r\n" not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("handshake failed")
            self._buf += chunk
        head, _, self._buf = self._buf.partition(b"\r\n\r\n")
        if b" 101" not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError("handshake rejected")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _recvn(self, n):
        while len(self._buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self._buf += chunk
        data, self._buf = self._buf[:n], self._buf[n:]
        return data

    def _send_frame(self, op, payload):
        hdr = bytearray([0x80 | op])
        ln = len(payload)
        if ln < 126:
            hdr.append(0x80 | ln)
        elif ln < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", ln)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", ln)
        mask = os.urandom(4)
        hdr += mask
        self.sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def recv(self):
        parts = []
        while True:
            b0, b1 = self._recvn(2)
            ln = b1 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._recvn(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._recvn(8))[0]
            payload = self._recvn(ln)
            op = b0 & 0x0F
            if op == 8:
                raise ConnectionError("closed")
            if op == 9:
                self._send_frame(0xA, payload)
                continue
            if op in (0, 1):
                parts.append(payload)
                if b0 & 0x80:
                    return b"".join(parts).decode("utf-8", "replace")

    def call(self, method, params=None):
        self._id += 1
        my_id = self._id
        self._send_frame(1, json.dumps({"id": my_id, "method": method,
                                        "params": params or {}}).encode())
        while True:
            msg = json.loads(self.recv())
            if msg.get("id") == my_id:
                if "error" in msg:
                    raise RuntimeError(str(msg["error"]))
                return msg.get("result", {})


def _is_google_cookie(c):
    d = c.get("domain", "").lstrip(".").lower()
    return d.endswith(("youtube.com", "google.com"))


def write_netscape_cookies(cookies, path):
    """Сохраняет cookies Google/YouTube в формате Netscape, который понимает yt-dlp."""
    far = int(time.time()) + 365 * 24 * 3600
    lines = ["# Netscape HTTP Cookie File",
             "# Сессия аккаунта. Не передавайте этот файл никому.", ""]
    for c in cookies:
        if not _is_google_cookie(c):
            continue
        dom = c["domain"]
        exp = c.get("expires", -1)
        exp = int(exp) if exp and exp > 0 else far
        lines.append("\t".join([
            ("#HttpOnly_" if c.get("httpOnly") else "") + dom,
            "TRUE" if dom.startswith(".") else "FALSE",
            c.get("path", "/"),
            "TRUE" if c.get("secure") else "FALSE",
            str(exp), c["name"], c["value"]]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def chromium_login(exe, proxy_arg, cancel_event, timeout=600):
    """Открывает браузер с отдельным профилем, ждёт входа пользователя в Google,
    сохраняет cookies в AUTH_COOKIES. Возвращает (ok, сообщение)."""
    os.makedirs(AUTH_PROFILE, exist_ok=True)
    port = _free_port()
    cmd = [exe, f"--user-data-dir={AUTH_PROFILE}", f"--remote-debugging-port={port}",
           "--no-first-run", "--no-default-browser-check"]
    if proxy_arg:
        cmd.append(proxy_arg)
    cmd.append(LOGIN_URL)
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError as e:
        return False, f"Не удалось запустить браузер: {e}"

    ws = None

    def shutdown():
        if ws is not None:
            try:
                ws._send_frame(1, json.dumps({"id": 9999, "method": "Browser.close"}).encode())
            except Exception:  # noqa: BLE001
                pass
            ws.close()
        try:
            proc.wait(timeout=8)
        except Exception:  # noqa: BLE001
            try:
                proc.terminate()
            except OSError:
                pass

    try:
        ws_url = None
        t0 = time.time()
        while time.time() - t0 < 25 and ws_url is None:
            if cancel_event.is_set():
                shutdown()
                return False, "Вход отменён."
            try:
                with _LOCAL_OPENER.open(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                    ws_url = json.load(r)["webSocketDebuggerUrl"]
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        if ws_url is None:
            shutdown()
            return False, ("Не удалось подключиться к браузеру. Если окно входа уже открыто "
                           "с прошлой попытки — закройте его и повторите.")
        ws = _MiniWS(ws_url)

        t0 = time.time()
        sid_seen = None
        yt_opened = False
        while True:
            if cancel_event.is_set():
                shutdown()
                return False, "Вход отменён."
            if time.time() - t0 > timeout:
                shutdown()
                return False, "Время ожидания входа истекло."
            try:
                cookies = ws.call("Storage.getCookies").get("cookies", [])
            except OSError:
                try:
                    proc.terminate()
                except OSError:
                    pass
                return False, "Окно браузера закрыто до завершения входа."
            google = [c for c in cookies if _is_google_cookie(c)]
            logged = any(c["name"] in ("SID", "__Secure-3PSID") for c in google)
            yt_ok = any(c["name"] == "LOGIN_INFO" and "youtube.com" in c["domain"] for c in google)
            if logged and yt_ok:
                break
            if logged:
                sid_seen = sid_seen or time.time()
                if not yt_opened and time.time() - sid_seen > 15:
                    yt_opened = True
                    try:
                        ws.call("Target.createTarget", {"url": "https://www.youtube.com/"})
                    except Exception:  # noqa: BLE001
                        pass
            cancel_event.wait(2)

        time.sleep(2)  # даём браузеру дописать все cookies
        cookies = ws.call("Storage.getCookies").get("cookies", [])
        write_netscape_cookies(cookies, AUTH_COOKIES)
        shutdown()
        return True, "Вход выполнен, сессия сохранена."
    except Exception as e:  # noqa: BLE001
        shutdown()
        return False, f"Ошибка при входе: {e}"


class Cancelled(Exception):
    pass


class QLogger:
    """Передаёт сообщения yt-dlp в окно лога."""

    def __init__(self, q, prefix=""):
        self.q = q
        self.prefix = prefix

    def debug(self, msg):
        if not msg.startswith("[debug]"):
            self.q.put(("log", self.prefix + strip_ansi(msg)))

    def info(self, msg):
        self.q.put(("log", self.prefix + strip_ansi(msg)))

    def warning(self, msg):
        self.q.put(("log", "ВНИМАНИЕ: " + self.prefix + strip_ansi(msg)))

    def error(self, msg):
        self.q.put(("log", "ОШИБКА: " + self.prefix + strip_ansi(msg)))


class Job:
    """Одна загрузка в очереди."""
    _next_id = 0

    def __init__(self, url, settings, fmt_label):
        Job._next_id += 1
        self.id = Job._next_id
        self.url = url
        self.s = dict(settings)
        self.fmt = fmt_label
        self.title = url
        self.state = "queued"      # queued / running / done / error / cancelled
        self.cancelling = False
        self.pct = 0.0
        self.info = ""
        self.error = ""
        self.filepath = None
        self.cancel_event = threading.Event()
        self.thread = None

    def reset(self):
        self.state = "queued"
        self.cancelling = False
        self.pct = 0.0
        self.info = ""
        self.error = ""
        self.filepath = None
        self.cancel_event = threading.Event()


# ------------------------------------------------------------------ тема
BG = "#0f1115"        # фон окна
CARD = "#171a21"      # карточки
INPUT = "#1f232c"     # поля ввода
BORDER = "#2a2f3a"    # рамки
HOVER = "#2c323e"     # наведение на кнопки
FG = "#e6e9ef"        # основной текст
MUTED = "#8b93a3"     # второстепенный текст
DIM = "#565d6b"       # отключённые элементы
ACCENT = "#6d5dfc"    # акцент
ACCENT_H = "#8274ff"  # акцент при наведении
LOG_BG = "#0b0d11"
GREEN = "#4ade80"
AMBER = "#fbbf24"
RED = "#f87171"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Downloader")
        self.geometry("1180x840")
        self.minsize(1040, 600)

        self.q = queue.Queue()
        self.jobs = []
        self.job_map = {}
        self.history = []
        self.idle_text = "Готов"
        self.update_busy = False
        self.js_busy = False
        self.auth_busy = False
        self.auth_cancel = threading.Event()

        if IS_MAC:
            # в Tk на macOS 1 pt = 1 px (72 dpi), шрифты выглядят мельче, чем в Windows
            try:
                self.tk.call("tk", "scaling", 1.3333)
            except tk.TclError:
                pass
            # Cmd+Q и «Выйти» из меню приложения должны сохранять настройки
            try:
                self.createcommand("::tk::mac::Quit", self._on_close)
            except tk.TclError:
                pass
        self._setup_theme()
        self._load_history()
        self._build_ui()
        self._setup_clipboard()
        self._load_config()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_queue)
        self.after(30, self._dark_titlebar)

        self._log("Сборка: paste-v4")
        self.ffmpeg_dir = find_ffmpeg()
        if self.ffmpeg_dir:
            self._log(f"ffmpeg найден: {self.ffmpeg_dir}")
        else:
            self._log("ВНИМАНИЕ: ffmpeg не найден в папке bin или в системе. "
                      + FFMPEG_HINT)
        if self.autoupdate_var.get():
            self.after(1500, lambda: self._check_update(auto=True))
        self.after(800, self._ensure_js)

    # ------------------------------------------------------------- theme
    def _dark_titlebar(self):
        """Тёмная строка заголовка окна в Windows 10/11."""
        if os.name != "nt":
            return
        try:
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            one = ctypes.c_int(1)
            for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(one), ctypes.sizeof(one))
            caption = ctypes.c_int(0x15110F)  # цвет заголовка (Win11), BGR от BG
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
        except Exception:  # noqa: BLE001
            pass

    def _setup_theme(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        self.configure(bg=BG)

        families = set(tkfont.families())

        def pick(*names, default):
            return next((n for n in names if n in families), default)

        ui = pick("Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Ubuntu", "Noto Sans", "Liberation Sans",
                  "Cantarell", "DejaVu Sans", default="TkDefaultFont")
        mono = pick("Cascadia Mono", "Consolas", "JetBrains Mono", "Menlo", "Ubuntu Mono",
                    "Noto Sans Mono", "Liberation Mono", "DejaVu Sans Mono",
                    default="TkFixedFont")
        self.f_ui = ui
        self.f_mono = mono
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(family=ui, size=10)
        tkfont.nametofont("TkFixedFont").configure(family=mono, size=9)

        self.option_add("*TCombobox*Listbox.background", INPUT)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.borderWidth", 0)
        self.option_add("*TCombobox*Listbox.relief", "flat")
        self.option_add("*TCombobox*Listbox.font", (ui, 10))

        s.configure(".", background=BG, foreground=FG, bordercolor=BORDER,
                    lightcolor=BG, darkcolor=BG, troughcolor=INPUT, focuscolor=BG,
                    font=(ui, 10))

        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Card.TLabel", background=CARD, foreground=FG)
        s.configure("Cap.TLabel", background=CARD, foreground=MUTED, font=(ui, 8, "bold"))
        s.configure("Title.TLabel", background=BG, foreground=FG, font=(ui, 20, "bold"))
        s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=(ui, 10))
        s.configure("Chip.TLabel", background=BG, foreground=MUTED, font=(ui, 9))
        s.configure("Status.TLabel", background=BG, foreground=MUTED, font=(ui, 10))

        field = dict(fieldbackground=INPUT, foreground=FG, insertcolor=FG,
                     bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                     selectbackground=ACCENT, selectforeground="#ffffff",
                     padding=(10, 8), relief="flat")
        s.configure("TEntry", **field)
        s.map("TEntry",
              bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)],
              fieldbackground=[("disabled", CARD)], foreground=[("disabled", DIM)])

        s.configure("TCombobox", arrowcolor=MUTED, background=INPUT, arrowsize=14, **field)
        s.map("TCombobox",
              fieldbackground=[("disabled", CARD), ("readonly", INPUT)],
              foreground=[("disabled", DIM), ("readonly", FG)],
              background=[("disabled", CARD), ("active", HOVER)],
              selectbackground=[("readonly", INPUT)], selectforeground=[("readonly", FG)],
              bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)], arrowcolor=[("disabled", DIM), ("active", FG)])

        s.configure("TButton", background=INPUT, foreground=FG, bordercolor=BORDER,
                    lightcolor=INPUT, darkcolor=INPUT, focuscolor=INPUT,
                    padding=(14, 8), relief="flat")
        s.map("TButton",
              background=[("disabled", CARD), ("pressed", BORDER), ("active", HOVER)],
              lightcolor=[("disabled", CARD), ("pressed", BORDER), ("active", HOVER)],
              darkcolor=[("disabled", CARD), ("pressed", BORDER), ("active", HOVER)],
              foreground=[("disabled", DIM)], bordercolor=[("disabled", BORDER)])

        s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT, focuscolor=ACCENT,
                    padding=(26, 10), font=(ui, 11, "bold"))
        s.map("Accent.TButton",
              background=[("disabled", "#262a44"), ("pressed", "#5a4be0"), ("active", ACCENT_H)],
              lightcolor=[("disabled", "#262a44"), ("pressed", "#5a4be0"), ("active", ACCENT_H)],
              darkcolor=[("disabled", "#262a44"), ("pressed", "#5a4be0"), ("active", ACCENT_H)],
              bordercolor=[("disabled", "#262a44"), ("active", ACCENT_H)],
              foreground=[("disabled", "#6b6f94")])

        s.configure("Ghost.TButton", background=BG, foreground=MUTED, bordercolor=BORDER,
                    lightcolor=BG, darkcolor=BG, focuscolor=BG, padding=(12, 6))
        s.map("Ghost.TButton",
              background=[("disabled", BG), ("active", INPUT)],
              lightcolor=[("disabled", BG), ("active", INPUT)],
              darkcolor=[("disabled", BG), ("active", INPUT)],
              foreground=[("disabled", DIM), ("active", FG)])

        s.configure("Seg.Toolbutton", background=INPUT, foreground=MUTED, bordercolor=BORDER,
                    lightcolor=INPUT, darkcolor=INPUT, focuscolor=INPUT,
                    padding=(22, 8), relief="flat", font=(ui, 10, "bold"))
        s.map("Seg.Toolbutton",
              background=[("selected", ACCENT), ("active", HOVER)],
              lightcolor=[("selected", ACCENT), ("active", HOVER)],
              darkcolor=[("selected", ACCENT), ("active", HOVER)],
              bordercolor=[("selected", ACCENT)],
              foreground=[("selected", "#ffffff"), ("active", FG)])

        s.configure("Card.TCheckbutton", background=CARD, foreground=FG, focuscolor=CARD,
                    indicatorbackground=INPUT, indicatorforeground="#ffffff",
                    upperbordercolor=BORDER, lowerbordercolor=BORDER,
                    indicatormargin=(0, 0, 8, 0), padding=(0, 3))
        s.map("Card.TCheckbutton",
              background=[("active", CARD)], foreground=[("disabled", DIM)],
              indicatorbackground=[("disabled", CARD), ("selected", ACCENT), ("active", HOVER)],
              indicatorforeground=[("disabled", DIM)],
              upperbordercolor=[("selected", ACCENT)], lowerbordercolor=[("selected", ACCENT)])

        s.layout("Dark.Horizontal.TProgressbar", [
            ("Horizontal.Progressbar.trough", {
                "sticky": "nswe",
                "children": [("Horizontal.Progressbar.pbar", {"side": "left", "sticky": "ns"})],
            })])
        s.configure("Dark.Horizontal.TProgressbar", troughcolor=INPUT, background=ACCENT,
                    bordercolor=INPUT, lightcolor=ACCENT, darkcolor=ACCENT, thickness=8)

        s.layout("Dark.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {
                "sticky": "ns",
                "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
            })])
        s.configure("Dark.Vertical.TScrollbar", troughcolor=LOG_BG, background="#2d333f",
                    bordercolor=LOG_BG, lightcolor="#2d333f", darkcolor="#2d333f",
                    gripcount=0, width=10)
        s.map("Dark.Vertical.TScrollbar",
              background=[("active", "#434b5c")], lightcolor=[("active", "#434b5c")],
              darkcolor=[("active", "#434b5c")])

        # Вкладки
        s.layout("TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
            ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                ("Notebook.label", {"side": "top", "sticky": ""})]})]})])
        s.configure("TNotebook", background=BG, bordercolor=BORDER, lightcolor=BG,
                    darkcolor=BG, borderwidth=1, tabmargins=(0, 0, 0, 0))
        s.configure("TNotebook.Tab", background=BG, foreground=MUTED, bordercolor=BG,
                    lightcolor=BG, darkcolor=BG, padding=(18, 9), font=(ui, 10, "bold"))
        # все вкладки на одном уровне: выбранная не "вырастает" (в теме clam она выше остальных)
        s.map("TNotebook.Tab",
              expand=[("selected", (0, 0, 0, 0))],
              padding=[("selected", (18, 9)), ("!selected", (18, 9))],
              background=[("selected", CARD), ("active", INPUT)],
              foreground=[("selected", FG), ("active", FG)],
              bordercolor=[("selected", BORDER)],
              lightcolor=[("selected", CARD)], darkcolor=[("selected", CARD)])

        # Таблицы (очередь, история)
        s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        s.configure("Treeview", background=LOG_BG, fieldbackground=LOG_BG, foreground=FG,
                    bordercolor=LOG_BG, lightcolor=LOG_BG, darkcolor=LOG_BG,
                    rowheight=28, borderwidth=0, font=(ui, 10))
        s.map("Treeview", background=[("selected", "#3a3f7a")],
              foreground=[("selected", "#ffffff")])
        s.configure("Treeview.Heading", background=CARD, foreground=MUTED, relief="flat",
                    bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD,
                    padding=(8, 7), font=(ui, 9, "bold"))
        s.map("Treeview.Heading", background=[("active", HOVER)])
        s.configure("TSeparator", background=BORDER)

    # ---------------------------------------------------------------- UI
    def _card(self, parent, **pack):
        outer = tk.Frame(parent, bg=BORDER)
        outer.pack(fill="x", **pack)
        inner = ttk.Frame(outer, style="Card.TFrame", padding=16)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return inner

    def _cap(self, parent, text, row, column, columnspan=1, pady=(0, 6)):
        lbl = ttk.Label(parent, text=text, style="Cap.TLabel")
        lbl.grid(row=row, column=column, columnspan=columnspan, sticky="w", pady=pady)
        return lbl

    def _make_tree(self, parent, cols):
        """Тёмная таблица со скроллбаром. cols: [(id, заголовок, ширина, выравнивание, stretch)]"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        wrap = tk.Frame(parent, bg=BORDER)
        wrap.grid(row=0, column=0, sticky="nsew")
        inner = tk.Frame(wrap, bg=LOG_BG)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        tree = ttk.Treeview(inner, columns=[c[0] for c in cols], show="headings",
                            selectmode="extended")
        for cid, text, width, anchor, stretch in cols:
            tree.heading(cid, text=text, anchor=anchor)
            tree.column(cid, width=width, minwidth=40, anchor=anchor, stretch=stretch)
        sb = ttk.Scrollbar(inner, command=tree.yview, style="Dark.Vertical.TScrollbar")
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 2), pady=2)
        tree.pack(side="left", fill="both", expand=True)
        for tag, color in (("queued", "#b6bdcb"), ("running", ACCENT_H), ("done", GREEN),
                           ("error", RED), ("cancelled", MUTED), ("cancelling", AMBER)):
            tree.tag_configure(tag, foreground=color)
        return tree

    def _build_ui(self):
        main = ttk.Frame(self, padding=(18, 14, 18, 10))
        main.pack(fill="both", expand=True)

        # --- Подвал
        foot = ttk.Frame(main)
        foot.pack(side="bottom", fill="x", pady=(10, 0))
        self.status_var = tk.StringVar(value=self.idle_text)
        ttk.Label(foot, textvariable=self.status_var, style="Status.TLabel").pack(side="left")

        # --- Две колонки: слева настройки, справа очередь / история / лог
        body = ttk.Frame(main)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        left = ttk.Notebook(body, width=450)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        right = ttk.Notebook(body)
        right.grid(row=0, column=1, sticky="nsew")
        self.right_nb = right

        # ================= Левая колонка: вкладка «Загрузка»
        t1 = ttk.Frame(left, style="Card.TFrame", padding=16)
        left.add(t1, text="Загрузка")
        t1.columnconfigure(0, weight=1)
        self._cap(t1, "ССЫЛКА (МОЖНО НЕСКОЛЬКО ЧЕРЕЗ ПРОБЕЛ)", 0, 0, 2)
        self.url_var = tk.StringVar()
        url_e = ttk.Entry(t1, textvariable=self.url_var)
        self.url_entry = url_e
        url_e.grid(row=1, column=0, sticky="ew")
        url_e.bind("<Return>", lambda e: self._add_to_queue())
        ttk.Button(t1, text="Вставить", command=self._paste).grid(row=1, column=1, padx=(8, 0))
        self._cap(t1, "ПАПКА ДЛЯ СОХРАНЕНИЯ", 2, 0, 2, pady=(14, 6))
        self.out_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        ttk.Entry(t1, textvariable=self.out_var).grid(row=3, column=0, sticky="ew")
        ttk.Button(t1, text="Обзор…", command=self._choose_dir).grid(
            row=3, column=1, padx=(8, 0))

        self.mode_var = tk.StringVar(value=MODE_VIDEO)
        seg = ttk.Frame(t1, style="Card.TFrame")
        seg.grid(row=4, column=0, columnspan=2, sticky="w", pady=(16, 12))
        for text in (MODE_VIDEO, MODE_AUDIO):
            ttk.Radiobutton(seg, text=text, value=text, variable=self.mode_var,
                            style="Seg.Toolbutton", command=self._on_mode,
                            takefocus=False).pack(side="left")

        opt = ttk.Frame(t1, style="Card.TFrame")
        opt.grid(row=5, column=0, columnspan=2, sticky="ew")
        opt.columnconfigure(0, weight=1, uniform="opt")
        opt.columnconfigure(1, weight=1, uniform="opt")
        self._cap(opt, "КАЧЕСТВО", 0, 0)
        self.fmt_label = self._cap(opt, "КОНТЕЙНЕР", 0, 1)
        self.quality_var = tk.StringVar(value=QUALITIES[0][0])
        self.quality_cb = ttk.Combobox(opt, textvariable=self.quality_var, state="readonly",
                                       values=[q[0] for q in QUALITIES])
        self.quality_cb.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.container_var = tk.StringVar(value="mkv")
        self.container_cb = ttk.Combobox(opt, textvariable=self.container_var,
                                         values=["mkv", "mp4", "webm"], state="readonly")
        self.container_cb.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        self.audio_var = tk.StringVar(value="mp3")
        self.audio_cb = ttk.Combobox(opt, textvariable=self.audio_var, values=AUDIO_FORMATS,
                                     state="readonly")
        self.audio_cb.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        self.audio_cb.grid_remove()

        chk = ttk.Frame(t1, style="Card.TFrame")
        chk.grid(row=6, column=0, columnspan=2, sticky="w", pady=(14, 0))
        self.playlist_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(chk, text="Весь плейлист", variable=self.playlist_var,
                        style="Card.TCheckbutton").pack(side="left", padx=(0, 22))
        self.subs_var = tk.BooleanVar(value=False)
        self.subs_cb = ttk.Checkbutton(chk, text="Субтитры", variable=self.subs_var,
                                       style="Card.TCheckbutton")
        self.subs_cb.pack(side="left")

        self.add_btn = ttk.Button(t1, text="Добавить в очередь", style="Accent.TButton",
                                  command=self._add_to_queue)
        self.add_btn.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(22, 0))
        ttk.Label(t1, style="Card.TLabel", foreground=MUTED, wraplength=400, justify="left",
                  text=f"Совет: скопируйте ссылку и нажмите {PASTE_KEY} в любом месте окна — "
                       "она сразу пойдёт в очередь и начнёт скачиваться. Загрузки идут по "
                       "очереди, не больше выбранного числа одновременно.").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # ================= Левая колонка: вкладка «Настройки»
        t2_outer = tk.Frame(left, bg=CARD)
        left.add(t2_outer, text="Настройки")
        t2_outer.columnconfigure(0, weight=1)
        t2_outer.rowconfigure(0, weight=1)
        self.settings_outer = t2_outer
        self.settings_canvas = tk.Canvas(t2_outer, bg=CARD, highlightthickness=0, bd=0,
                                         yscrollincrement=24, width=1, height=1)
        self.settings_canvas.grid(row=0, column=0, sticky="nsew")
        self.settings_vsb = ttk.Scrollbar(t2_outer, orient="vertical", style="Dark.Vertical.TScrollbar",
                                          command=self.settings_canvas.yview)
        self.settings_canvas.configure(yscrollcommand=self.settings_vsb.set)
        self.settings_scroll_on = False
        t2 = ttk.Frame(self.settings_canvas, style="Card.TFrame", padding=16)
        self.settings_inner = t2
        self.settings_win = self.settings_canvas.create_window((0, 0), window=t2, anchor="nw")
        t2.columnconfigure(0, weight=1)
        self.settings_canvas.bind("<Configure>", self._sync_settings_scroll)
        t2.bind("<Configure>", self._sync_settings_scroll)
        for _ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(_ev, self._settings_wheel, add="+")

        # -- одновременные загрузки
        self._cap(t2, "ОДНОВРЕМЕННЫЕ ЗАГРУЗКИ", 0, 0)
        prow = ttk.Frame(t2, style="Card.TFrame")
        prow.grid(row=1, column=0, sticky="w")
        self.parallel_var = tk.StringVar(value="2")
        self.parallel_cb = ttk.Combobox(prow, textvariable=self.parallel_var, width=5,
                                        state="readonly", values=[str(i) for i in range(1, 11)])
        self.parallel_cb.pack(side="left")
        self.parallel_cb.bind("<<ComboboxSelected>>", self._on_parallel)
        ttk.Label(prow, text="видео одновременно", style="Card.TLabel").pack(
            side="left", padx=(10, 0))
        blk = ttk.Frame(t2, style="Card.TFrame")
        blk.grid(row=2, column=0, sticky="ew")
        self.parallel_note = ttk.Label(blk, style="Card.TLabel", wraplength=380, justify="left",
                                       text=PARALLEL_NOTE)
        self.parallel_note.pack(anchor="w", pady=(8, 0))
        # -- под какую ОС скачивать
        orow = ttk.Frame(blk, style="Card.TFrame")
        orow.pack(anchor="w", fill="x", pady=(12, 0))
        ttk.Label(orow, text="Файлы для ОС", style="Card.TLabel").pack(side="left")
        self.target_os_var = tk.StringVar(value=TARGET_OS_LABELS["auto"])
        self.target_os_cb = ttk.Combobox(orow, textvariable=self.target_os_var, width=20,
                                         state="readonly", values=list(TARGET_OS_LABELS.values()))
        self.target_os_cb.pack(side="left", padx=(10, 0))
        self.target_os_cb.bind("<<ComboboxSelected>>", self._on_target_os)
        self.target_os_note = ttk.Label(blk, style="Card.TLabel", foreground=MUTED,
                                        wraplength=380, justify="left")
        self.target_os_note.pack(anchor="w", pady=(6, 0))
        self._update_target_os_note()
        ttk.Separator(t2).grid(row=3, column=0, sticky="ew", pady=9)

        # -- аккаунт
        self._cap(t2, "АККАУНТ", 4, 0)
        self.use_auth_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(t2, text="Скачивать под моим аккаунтом (приватные, 18+)",
                        variable=self.use_auth_var, style="Card.TCheckbutton").grid(
            row=5, column=0, sticky="w")
        arow = ttk.Frame(t2, style="Card.TFrame")
        arow.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        arow.columnconfigure(0, weight=1)
        self.auth_status_var = tk.StringVar()
        self.auth_status_lbl = ttk.Label(arow, textvariable=self.auth_status_var,
                                         style="Card.TLabel")
        self.auth_status_lbl.grid(row=0, column=0, sticky="w")
        self.auth_login_btn = ttk.Button(arow, text="Войти в аккаунт", command=self._auth_login)
        self.auth_login_btn.grid(row=0, column=1, padx=(8, 0))
        self.auth_logout_btn = ttk.Button(arow, text="Выйти", command=self._auth_logout)
        self.auth_logout_btn.grid(row=0, column=2, padx=(8, 0))
        ttk.Label(t2, style="Card.TLabel", foreground=MUTED, wraplength=380, justify="left",
                  text="Откроется окно браузера — войдите в Google как обычно. Окно закроется "
                       "само. Пароль программа не видит и не хранит.").grid(
            row=7, column=0, sticky="w", pady=(8, 0))
        ttk.Separator(t2).grid(row=8, column=0, sticky="ew", pady=9)

        # -- прокси
        self._cap(t2, "ПРОКСИ", 9, 0)
        self.use_proxy_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(t2, text="Использовать прокси", variable=self.use_proxy_var,
                        style="Card.TCheckbutton", command=self._toggle_proxy).grid(
            row=10, column=0, sticky="w", pady=(0, 8))

        row1 = ttk.Frame(t2, style="Card.TFrame")
        row1.grid(row=11, column=0, sticky="ew")
        row1.columnconfigure(1, weight=1)
        self._cap(row1, "ТИП", 0, 0)
        self._cap(row1, "IP / ХОСТ", 0, 1)
        self._cap(row1, "ПОРТ", 0, 2)
        self.ptype_var = tk.StringVar(value="http")
        self.ptype_cb = ttk.Combobox(row1, textvariable=self.ptype_var, width=8, state="readonly",
                                     values=["http", "https", "socks4", "socks5", "socks5h"])
        self.ptype_cb.grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.host_var = tk.StringVar()
        self.host_e = ttk.Entry(row1, textvariable=self.host_var)
        self.host_e.grid(row=1, column=1, sticky="ew", padx=8)
        self.port_var = tk.StringVar()
        self.port_e = ttk.Entry(row1, textvariable=self.port_var, width=8)
        self.port_e.grid(row=1, column=2, sticky="w", padx=(8, 0))

        row2 = ttk.Frame(t2, style="Card.TFrame")
        row2.grid(row=12, column=0, sticky="ew", pady=(10, 0))
        row2.columnconfigure(0, weight=1, uniform="cred")
        row2.columnconfigure(1, weight=1, uniform="cred")
        self._cap(row2, "ЛОГИН", 0, 0)
        self._cap(row2, "ПАРОЛЬ", 0, 1)
        self.user_var = tk.StringVar()
        self.user_e = ttk.Entry(row2, textvariable=self.user_var)
        self.user_e.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.pass_var = tk.StringVar()
        self.pass_e = ttk.Entry(row2, textvariable=self.pass_var, show="•")
        self.pass_e.grid(row=1, column=1, sticky="ew", padx=(8, 0))

        row3 = ttk.Frame(t2, style="Card.TFrame")
        row3.grid(row=13, column=0, sticky="w", pady=(8, 0))
        self.remember_pass_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text="Запомнить пароль", variable=self.remember_pass_var,
                        style="Card.TCheckbutton").pack(side="left", padx=(0, 22))
        self.show_pass_var = tk.BooleanVar(value=False)
        self.show_cb = ttk.Checkbutton(row3, text="Показать пароль", variable=self.show_pass_var,
                                       style="Card.TCheckbutton", command=self._toggle_show_pass)
        self.show_cb.pack(side="left")
        self.proxy_widgets = [self.ptype_cb, self.host_e, self.port_e, self.user_e,
                              self.pass_e, self.show_cb]
        ttk.Separator(t2).grid(row=14, column=0, sticky="ew", pady=9)

        self.autoupdate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(t2, text="Автообновление yt-dlp при запуске",
                        variable=self.autoupdate_var, style="Card.TCheckbutton").grid(
            row=15, column=0, sticky="w")
        self.clip_paste_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(t2, text=f"{PASTE_KEY} в окне — сразу скачивать ссылку из буфера",
                        variable=self.clip_paste_var, style="Card.TCheckbutton").grid(
            row=16, column=0, sticky="w", pady=(6, 0))

        # -- ручное обновление yt-dlp
        urow = ttk.Frame(t2, style="Card.TFrame")
        urow.grid(row=17, column=0, sticky="ew", pady=(14, 0))
        urow.columnconfigure(0, weight=1)
        self.ver_var = tk.StringVar(value=f"yt-dlp {YTDLP_VERSION}")
        ttk.Label(urow, textvariable=self.ver_var, style="Card.TLabel").grid(row=0, column=0, sticky="w")
        self.update_btn = ttk.Button(urow, text="Обновить yt-dlp",
                                     command=lambda: self._check_update(auto=False))
        self.update_btn.grid(row=0, column=1, padx=(8, 0))

        # ================= Правая колонка: очередь
        qf = ttk.Frame(right, style="Card.TFrame", padding=12)
        right.add(qf, text="Очередь")
        self.queue_tab = qf
        self.q_tree = self._make_tree(qf, [
            ("n", "#", 36, "center", False),
            ("title", "Название", 230, "w", True),
            ("fmt", "Формат", 92, "w", False),
            ("status", "Статус", 84, "w", False),
            ("prog", "Прогресс", 250, "w", False),
        ])
        self.q_tree.column("title", minwidth=140)
        self.q_tree.bind("<Double-1>", self._queue_dbl)
        self.q_tree.bind("<Delete>", lambda e: self._cancel_selected())
        bq = ttk.Frame(qf, style="Card.TFrame")
        bq.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bq, text="Отменить", command=self._cancel_selected).pack(side="left")
        ttk.Button(bq, text="Отменить все", command=self._cancel_all).pack(side="left", padx=8)
        ttk.Button(bq, text="Повторить", command=self._retry_selected).pack(side="left")
        ttk.Button(bq, text="Убрать готовые", command=self._clear_finished).pack(
            side="left", padx=8)
        ttk.Button(bq, text="Открыть папку", command=self._open_dir).pack(side="right")

        # ================= Правая колонка: история
        hf = ttk.Frame(right, style="Card.TFrame", padding=12)
        right.add(hf, text="История")
        self.history_tab = hf
        self.h_tree = self._make_tree(hf, [
            ("t", "Дата", 118, "w", False),
            ("title", "Название", 250, "w", True),
            ("site", "Сайт", 78, "w", False),
            ("fmt", "Формат", 100, "w", False),
            ("status", "Итог", 84, "w", False),
        ])
        self.h_tree.column("title", minwidth=140)
        self.h_tree.bind("<Double-1>", self._hist_dbl)
        self.h_tree.bind("<Delete>", lambda e: self._hist_delete())
        bh = ttk.Frame(hf, style="Card.TFrame")
        bh.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bh, text="Открыть", command=self._hist_open).pack(side="left")
        ttk.Button(bh, text="В папке", command=self._hist_reveal).pack(side="left", padx=8)
        ttk.Button(bh, text="Скачать снова", command=self._hist_redownload).pack(side="left")
        ttk.Button(bh, text="Удалить", command=self._hist_delete).pack(side="left", padx=8)
        ttk.Button(bh, text="Очистить историю", command=self._hist_clear).pack(side="right")

        # ================= Правая колонка: лог
        lf = ttk.Frame(right, style="Card.TFrame", padding=12)
        right.add(lf, text="Лог")
        outer = tk.Frame(lf, bg=BORDER)
        outer.pack(fill="both", expand=True)
        logf = tk.Frame(outer, bg=LOG_BG)
        logf.pack(fill="both", expand=True, padx=1, pady=1)
        self.log = tk.Text(logf, height=8, wrap="word", state="disabled", bg=LOG_BG, fg="#b6bdcb",
                           insertbackground=FG, relief="flat", bd=0, highlightthickness=0,
                           padx=14, pady=10, spacing3=3, font=(self.f_mono, 9),
                           selectbackground="#3a3f7a", selectforeground="#ffffff")
        sb = ttk.Scrollbar(logf, command=self.log.yview, style="Dark.Vertical.TScrollbar")
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 2), pady=2)
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_configure("info", foreground="#b6bdcb")
        self.log.tag_configure("dim", foreground=DIM)
        self.log.tag_configure("ok", foreground=GREEN)
        self.log.tag_configure("warn", foreground=AMBER)
        self.log.tag_configure("err", foreground=RED)

        self._toggle_proxy()
        self._auth_refresh_ui()
        self._update_parallel_note()
        self._fill_history()
        self._on_mode()

    # --------------------------------------------------------- clipboard
    def _setup_clipboard(self):
        self.menu = tk.Menu(self, tearoff=0, bg=INPUT, fg=FG, activebackground=ACCENT,
                            activeforeground="#ffffff", bd=0, relief="flat",
                            font=(self.f_ui, 10))
        self.menu.add_command(label="Вырезать", command=lambda: self._menu_do("<<Cut>>"))
        self.menu.add_command(label="Копировать", command=lambda: self._menu_do("<<Copy>>"))
        self.menu.add_command(label="Вставить", command=lambda: self._menu_do("<<Paste>>"))
        self.menu.add_separator()
        self.menu.add_command(label="Выделить всё", command=self._select_all)
        self._menu_widget = None

        # Windows/Linux: Ctrl+клавиша; macOS: Cmd+клавиша (Control+A там — «в начало строки»)
        MOD = "Command" if IS_MAC else "Control"
        # macOS: правая кнопка — Button-2, плюс Control+клик
        RIGHT_CLICK = ("<Button-2>", "<Control-Button-1>") if IS_MAC else ("<Button-3>",)

        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Entry, tk.Text)) and not isinstance(child, ttk.Combobox):
                    child.bind(f"<{MOD}-KeyPress>", self._on_ctrl_key)
                    for btn in RIGHT_CLICK:
                        child.bind(btn, self._show_menu)
                walk(child)
        walk(self)
        self.bind_all(f"<{MOD}-KeyPress>", self._on_global_ctrl)

    _KEYSYM_ACTION = {"v": "v", "cyrillic_em": "v", "c": "c", "cyrillic_es": "c",
                      "x": "x", "cyrillic_che": "x", "a": "a", "cyrillic_ef": "a"}

    @classmethod
    def _key_action(cls, event):
        """Какая это горячая клавиша (v/c/x/a) — независимо от раскладки (в т.ч. русской)."""
        act = cls._KEYSYM_ACTION.get(str(event.keysym).lower())
        if act is None and IS_WIN:  # запасной вариант: коды клавиш Windows
            act = {86: "v", 67: "c", 88: "x", 65: "a"}.get(event.keycode)
        return act

    def _on_ctrl_key(self, event):
        w = event.widget
        act = self._key_action(event)
        if act == "v":
            if isinstance(w, tk.Text):      # лог только для чтения — вставляем ссылку в очередь
                return None
            w.event_generate("<<Paste>>")
        elif act == "c":
            w.event_generate("<<Copy>>")
        elif act == "x":
            w.event_generate("<<Cut>>")
        elif act == "a":
            self._select_all(w)
        else:
            return None
        return "break"

    def _show_menu(self, event):
        self._menu_widget = event.widget
        event.widget.focus_set()
        self.menu.tk_popup(event.x_root, event.y_root)

    def _menu_do(self, virtual_event):
        if self._menu_widget is not None:
            self._menu_widget.event_generate(virtual_event)

    def _select_all(self, widget=None):
        w = widget or self._menu_widget
        if w is None:
            return
        if isinstance(w, tk.Text):
            w.tag_add("sel", "1.0", "end")
        else:
            w.select_range(0, "end")
            w.icursor("end")

    # ----------------------------------------------------------- helpers
    def _toggle_proxy(self):
        state = "normal" if self.use_proxy_var.get() else "disabled"
        for w in self.proxy_widgets:
            if isinstance(w, ttk.Combobox):
                w.configure(state="readonly" if state == "normal" else "disabled")
            else:
                w.configure(state=state)

    def _on_mode(self):
        audio = self.mode_var.get() == MODE_AUDIO
        if audio:
            self.container_cb.grid_remove()
            self.audio_cb.grid()
            self.fmt_label.configure(text="ФОРМАТ")
        else:
            self.audio_cb.grid_remove()
            self.container_cb.grid()
            self.fmt_label.configure(text="КОНТЕЙНЕР")
        self.quality_cb.configure(state="disabled" if audio else "readonly")
        self.subs_cb.configure(state="disabled" if audio else "normal")

    def _auth_refresh_ui(self):
        logged = os.path.isfile(AUTH_COOKIES)
        self.auth_status_var.set("Вход выполнен ✓" if logged else "Вход не выполнен")
        self.auth_status_lbl.configure(foreground=GREEN if logged else MUTED)
        if self.auth_busy:
            self.auth_login_btn.configure(text="Отменить вход")
        else:
            self.auth_login_btn.configure(text="Войти заново" if logged else "Войти в аккаунт")
        self.auth_logout_btn.configure(state="normal" if logged and not self.auth_busy else "disabled")

    def _chromium_proxy_arg(self):
        if not self.use_proxy_var.get():
            return None
        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        if not host or not port.isdigit():
            return None
        scheme = self.ptype_var.get().replace("socks5h", "socks5")
        host_part = f"[{host}]" if ":" in host and not host.startswith("[") else host
        return f"--proxy-server={scheme}://{host_part}:{port}"

    def _auth_login(self):
        if self.auth_busy:
            self.auth_cancel.set()
            return
        if self._running_count():
            messagebox.showinfo("Вход", "Дождитесь окончания загрузок или отмените их.")
            return
        exe = find_chromium()
        if not exe:
            messagebox.showwarning(
                "Браузер не найден",
                "Для входа нужен Google Chrome, Microsoft Edge, Brave или другой браузер на "
                "движке Chromium. Установите один из них и повторите.")
            return
        self.auth_busy = True
        self.auth_cancel = threading.Event()
        self._auth_refresh_ui()
        self._log(f"Открываю окно входа ({os.path.basename(exe)})...")
        threading.Thread(target=self._auth_worker, args=(exe, self._chromium_proxy_arg(),
                                                         self.auth_cancel), daemon=True).start()

    def _auth_worker(self, exe, proxy_arg, cancel_event):
        ok, msg = chromium_login(exe, proxy_arg, cancel_event)
        self.q.put(("auth", ok, msg))

    def _auth_logout(self):
        if not messagebox.askyesno("Выйти из аккаунта",
                                   "Удалить сохранённый вход из программы?\n"
                                   "Чтобы скачивать приватное, придётся войти заново."):
            return
        try:
            os.remove(AUTH_COOKIES)
        except OSError:
            pass
        shutil.rmtree(AUTH_PROFILE, ignore_errors=True)
        self.use_auth_var.set(False)
        self._auth_refresh_ui()
        self._log("Сохранённый вход удалён.")

    def _toggle_show_pass(self):
        self.pass_e.configure(show="" if self.show_pass_var.get() else "•")

    @staticmethod
    def _clip_native():
        """Текст из буфера обмена системным способом (без Tk)."""
        try:
            if IS_WIN:
                from ctypes import wintypes
                u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
                u32.OpenClipboard.argtypes = [wintypes.HWND]
                u32.OpenClipboard.restype = wintypes.BOOL
                u32.GetClipboardData.argtypes = [wintypes.UINT]
                u32.GetClipboardData.restype = wintypes.HANDLE
                k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
                k32.GlobalLock.restype = wintypes.LPVOID
                k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
                for _ in range(20):  # буфер может быть занят другой программой
                    if u32.OpenClipboard(None):
                        break
                    time.sleep(0.05)
                else:
                    return ""
                try:
                    h = u32.GetClipboardData(13)  # CF_UNICODETEXT
                    if not h:
                        return ""
                    ptr = k32.GlobalLock(h)
                    if not ptr:
                        return ""
                    try:
                        return ctypes.wstring_at(ptr)
                    finally:
                        k32.GlobalUnlock(h)
                finally:
                    u32.CloseClipboard()
            if IS_MAC:
                r = subprocess.run(["pbpaste"], capture_output=True, timeout=3)
                return r.stdout.decode("utf-8", "replace")
            for cmd in (["wl-paste", "-n"], ["xclip", "-selection", "clipboard", "-o"],
                        ["xsel", "-b", "-o"]):
                if shutil.which(cmd[0]):
                    r = subprocess.run(cmd, capture_output=True, timeout=3)
                    if r.returncode == 0:
                        return r.stdout.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _read_clipboard(self):
        """Текст из буфера обмена: на Windows сначала системный способ, затем Tk. Не бросает исключений."""
        if IS_WIN:
            text = self._clip_native()
            if text:
                return text
        try:
            text = self.clipboard_get()
            if text:
                return text
        except Exception:  # noqa: BLE001
            pass
        return "" if IS_WIN else self._clip_native()

    def _paste(self):
        """Кнопка «Вставить»: вставляет ссылку из буфера обмена в поле."""
        try:
            raw = self._read_clipboard()
            parts = raw.split()
            if parts:
                self.url_var.set(" ".join(parts))
                self.url_entry.focus_set()
                self.url_entry.icursor("end")
                self._log(f"Вставлено из буфера: {len(raw)} симв.")
                return
            # запасной путь — то же, что делает Ctrl+V в поле ввода
            self.url_entry.focus_set()
            self.url_entry.select_range(0, "end")
            self.url_entry.event_generate("<<Paste>>")
            self.after(80, lambda: self._log("ВНИМАНИЕ: буфер обмена пуст или в нём не текст.")
                       if not self.url_var.get().strip() else self._log("Вставлено из буфера (через Ctrl+V)."))
        except Exception as e:  # noqa: BLE001
            self._log(f"ОШИБКА вставки: {e!r}")

    def _choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get() or None)
        if d:
            self.out_var.set(d)

    def _open_dir(self):
        path = self.out_var.get().strip()
        if os.path.isdir(path):
            self._open_path(path)

    def _log(self, text):
        text = text.rstrip()
        core = re.sub(r"^\[#\d+\] ", "", text)
        if text.startswith("ОШИБКА"):
            tag = "err"
        elif text.startswith("ВНИМАНИЕ"):
            tag = "warn"
        elif (text.startswith("Готово") or text.startswith("ffmpeg найден")
              or text.startswith("Вход выполнен")
              or "обновлён" in text or "актуален" in text):
            tag = "ok"
        elif core.startswith("[download]"):
            tag = "dim"
        else:
            tag = "info"
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _build_proxy_url(self):
        if not self.use_proxy_var.get():
            return None, None
        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        if not host or not port:
            raise ValueError("Укажите IP/хост и порт прокси.")
        if not port.isdigit() or not (1 <= int(port) <= 65535):
            raise ValueError("Порт должен быть числом от 1 до 65535.")
        user = self.user_var.get()
        pwd = self.pass_var.get()
        scheme = self.ptype_var.get()
        host_part = f"[{host}]" if ":" in host and not host.startswith("[") else host

        auth = ""
        auth_safe = ""
        if user:
            auth = quote(user, safe="") + (":" + quote(pwd, safe="") if pwd else "") + "@"
            auth_safe = quote(user, safe="") + (":****" if pwd else "") + "@"
        url = f"{scheme}://{auth}{host_part}:{port}"
        safe = f"{scheme}://{auth_safe}{host_part}:{port}"
        return url, safe

    # ------------------------------------------------------------ config
    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError):
            return
        self.out_var.set(c.get("out", self.out_var.get()))
        self.target_os_var.set(TARGET_OS_LABELS.get(c.get("target_os", "auto"), TARGET_OS_LABELS["auto"]))
        self._update_target_os_note()
        self.container_var.set(c.get("container", "mkv"))
        self.playlist_var.set(c.get("playlist", False))
        self.subs_var.set(c.get("subs", False))
        self.mode_var.set(c.get("mode", MODE_VIDEO))
        self.quality_var.set(c.get("quality", QUALITIES[0][0]))
        self.audio_var.set(c.get("audio_fmt", "mp3"))
        self.autoupdate_var.set(c.get("auto_update", True))
        self.clip_paste_var.set(c.get("clip_paste", True))
        par = str(c.get("parallel", 2))
        self.parallel_var.set(par if par in [str(i) for i in range(1, 11)] else "2")
        self._update_parallel_note()
        self._on_mode()
        self.use_proxy_var.set(c.get("use_proxy", False))
        self.ptype_var.set(c.get("ptype", "http"))
        self.host_var.set(c.get("host", ""))
        self.port_var.set(c.get("port", ""))
        self.user_var.set(c.get("user", ""))
        self.remember_pass_var.set(c.get("remember_pass", True))
        if self.remember_pass_var.get():
            self.pass_var.set(decrypt_secret(c.get("password", "")))
        self.show_pass_var.set(False)
        self._toggle_show_pass()
        self._toggle_proxy()
        self.use_auth_var.set(c.get("use_auth", False) and os.path.isfile(AUTH_COOKIES))
        geom = c.get("geometry_v2")
        if geom:
            try:
                self.geometry(geom)
            except tk.TclError:
                pass

    def _save_config(self):
        c = {
            "out": self.out_var.get(),
            "container": self.container_var.get(),
            "target_os": self._target_os_key(),
            "playlist": self.playlist_var.get(),
            "subs": self.subs_var.get(),
            "mode": self.mode_var.get(),
            "quality": self.quality_var.get(),
            "audio_fmt": self.audio_var.get(),
            "auto_update": self.autoupdate_var.get(),
            "parallel": self._max_parallel(),
            "clip_paste": self.clip_paste_var.get(),
            "use_proxy": self.use_proxy_var.get(),
            "ptype": self.ptype_var.get(),
            "host": self.host_var.get().strip(),
            "port": self.port_var.get().strip(),
            "user": self.user_var.get(),
            "remember_pass": self.remember_pass_var.get(),
            "password": encrypt_secret(self.pass_var.get()) if self.remember_pass_var.get() else "",
            "use_auth": self.use_auth_var.get(),
            "geometry_v2": self.geometry(),
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _on_close(self):
        if self._running_count() or self._queued_count():
            if not messagebox.askyesno("Выход", "Есть активные и ожидающие загрузки.\n"
                                       "Закрыть программу и прервать их?"):
                return
        for job in self.jobs:
            job.cancel_event.set()
        self.auth_cancel.set()
        self._save_config()
        self.destroy()

    # ------------------------------------------------------------ очередь
    def _max_parallel(self):
        try:
            return max(1, min(10, int(self.parallel_var.get())))
        except ValueError:
            return 2

    def _running_count(self):
        return sum(1 for j in self.jobs if j.state == "running")

    def _queued_count(self):
        return sum(1 for j in self.jobs if j.state == "queued")

    def _on_parallel(self, _event=None):
        self._update_parallel_note()
        self._save_config()
        self._pump()

    # --- прокрутка вкладки «Настройки», когда окно слишком низкое
    def _sync_settings_scroll(self, _event=None):
        c = self.settings_canvas
        w, h = c.winfo_width(), c.winfo_height()
        need_h = self.settings_inner.winfo_reqheight()
        c.itemconfigure(self.settings_win, width=w)
        c.configure(scrollregion=(0, 0, w, need_h))
        need = need_h > h
        if need != self.settings_scroll_on:
            self.settings_scroll_on = need
            if need:
                self.settings_vsb.grid(row=0, column=1, sticky="ns")
            else:
                self.settings_vsb.grid_remove()
                c.yview_moveto(0)

    def _settings_wheel(self, event):
        if not self.settings_scroll_on:
            return None
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return None
        while w is not None and w is not self.settings_outer:
            w = w.master
        if w is None:
            return None
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self.settings_canvas.yview_scroll(step * 2, "units")
        return "break"

    def _target_os_key(self):
        label = self.target_os_var.get()
        return next((k for k, v in TARGET_OS_LABELS.items() if v == label), "auto")

    def _update_target_os_note(self):
        self.target_os_note.configure(text=TARGET_OS_NOTES[self._target_os_key()])

    def _on_target_os(self, _event=None):
        self._update_target_os_note()
        self._save_config()

    def _update_parallel_note(self):
        risky = self._max_parallel() > MAX_SAFE_PARALLEL
        self.parallel_note.configure(foreground=AMBER if risky else MUTED)

    def _current_settings(self):
        target = self._target_os_key()
        audio_only = self.mode_var.get() == MODE_AUDIO
        container = self.container_var.get()
        if target == "macos" and not audio_only:
            container = "mp4"  # QuickTime не открывает mkv/webm
        return {
            "target_os": target,
            "audio_only": audio_only,
            "container": container,
            "audio_codec": self.audio_var.get(),
            "quality": self.quality_var.get(),
            "playlist": self.playlist_var.get(),
            "subs": self.subs_var.get(),
            "out": self.out_var.get().strip(),
        }

    @staticmethod
    def _fmt_label(s):
        if s["audio_only"]:
            return f"Аудио · {s['audio_codec']}"
        q = s["quality"].split(" (")[0]
        if q == "Максимальное":
            q = "Макс."
        return f"{q} · {s['container']}"

    def _add_to_queue(self):
        text = self.url_var.get().strip()
        if not text:
            messagebox.showwarning("Нет ссылки", "Вставьте ссылку на видео.")
            return
        parts = text.split()
        if len(parts) > 1 and all("://" in p or "." in p for p in parts):
            urls = parts
        else:
            urls = [text]
        urls = ["https://" + u if "://" not in u and "." in u else u for u in urls]
        if self._queue_urls(urls):
            self.url_var.set("")

    def _queue_urls(self, urls):
        """Проверяет настройки, ставит ссылки в очередь и запускает. Возвращает число добавленных."""
        s = self._current_settings()
        if not s["out"]:
            messagebox.showwarning("Нет папки", "Выберите папку для сохранения.")
            return 0
        try:
            self._build_proxy_url()
        except ValueError as e:
            messagebox.showwarning("Прокси", str(e))
            return 0
        if s["audio_only"] and s["audio_codec"] != AUDIO_ORIGINAL and not self.ffmpeg_dir:
            messagebox.showwarning("ffmpeg", "Для конвертации в выбранный аудиоформат нужен ffmpeg. "
                                   + FFMPEG_HINT + " Либо выберите формат «оригинал».")
            return 0
        if self.use_auth_var.get() and not os.path.isfile(AUTH_COOKIES):
            messagebox.showwarning("Аккаунт", "Вы ещё не вошли в аккаунт. Нажмите «Войти в аккаунт» "
                                   "на вкладке «Настройки» или снимите галочку.")
            return 0
        try:
            os.makedirs(s["out"], exist_ok=True)
        except OSError as e:
            messagebox.showwarning("Папка", f"Не удалось создать папку:\n{e}")
            return 0

        added = self._enqueue(urls, s)
        self._save_config()
        return added

    # --- вставка ссылки из буфера обмена (Ctrl+V в любом месте окна)
    @staticmethod
    def _extract_urls(text):
        found = re.findall(r"https?://[^\s<>\"']+", text or "")
        urls = []
        for u in found:
            u = u.rstrip(".,;:!?)]}»")
            if u not in urls:
                urls.append(u)
        return urls[:100]

    def _on_global_ctrl(self, event):
        """Ctrl+V вне полей ввода: ссылка из буфера сразу попадает в очередь и стартует."""
        is_v = self._key_action(event) == "v"
        if not is_v or not self.clip_paste_var.get():
            return None
        text = self._read_clipboard()
        urls = self._extract_urls(text)
        if not urls:
            return None
        self._log(f"Из буфера обмена: ссылок — {len(urls)}")
        self._queue_urls(urls)
        return "break"

    def _enqueue(self, urls, settings):
        active = {j.url for j in self.jobs if j.state in ("queued", "running")}
        added = 0
        for u in urls:
            if u in active:
                self._log(f"Уже в очереди: {u}")
                continue
            job = Job(u, settings, self._fmt_label(settings))
            self.jobs.append(job)
            self.job_map[job.id] = job
            self.q_tree.insert("", "end", iid=str(job.id), values=self._row_values(job),
                               tags=(job.state,))
            active.add(u)
            added += 1
            self._log(f"В очередь #{job.id} ({site_name(u)}): {u}")
        if added:
            self.right_nb.select(self.queue_tab)
            self._pump()
        self._update_footer()
        return added

    def _pump(self):
        """Запускает ожидающие загрузки, пока не достигнут лимит одновременных."""
        if self.update_busy or self.auth_busy or self.js_busy:
            self._update_footer()
            return
        free = self._max_parallel() - self._running_count()
        for job in self.jobs:
            if free <= 0:
                break
            if job.state == "queued" and self._start_job(job):
                free -= 1
        self._update_footer()

    def _start_job(self, job):
        try:
            opts, details = self._build_opts(job)
        except Exception as e:  # noqa: BLE001
            self._finish_job(job, "error", str(e))
            return False
        job.state = "running"
        job.cancelling = False
        job.pct = 0.0
        job.info = "Запуск..."
        self._refresh_row(job)
        self._log(f"Старт #{job.id} ({site_name(job.url)}): {job.url}")
        self._log(f"   {details}")
        job.thread = threading.Thread(target=self._run_job, args=(job, opts), daemon=True)
        job.thread.start()
        return True

    def _build_opts(self, job):
        s = job.s
        proxy, proxy_safe = self._build_proxy_url()
        audio_only = s["audio_only"]
        container = s["container"]
        codec = s["audio_codec"]
        height = dict(QUALITIES).get(s["quality"])
        convert = audio_only and codec != AUDIO_ORIGINAL
        if convert and not self.ffmpeg_dir:
            raise ValueError("Для конвертации в выбранный аудиоформат нужен ffmpeg "
                             + FFMPEG_HINT)
        target = s.get("target_os", "auto")
        compat = target == "macos"
        fmt = "ba/b" if audio_only else build_video_format(container, height, compat)
        if audio_only and compat and codec == AUDIO_ORIGINAL:
            fmt = "ba[ext=m4a]/ba/b"  # opus/webm не играет в Музыке и QuickTime

        opts = {
            "format": fmt,
            "concurrent_fragment_downloads": max(1, 4 // self._max_parallel()),
            "outtmpl": os.path.join(s["out"], "%(title).150B [%(id)s].%(ext)s"),
            "noplaylist": not s["playlist"],
            "retries": 10,
            "fragment_retries": 10,
            "continuedl": True,
            "windowsfilenames": target == "windows" or (target == "auto" and IS_WIN),
            "logger": QLogger(self.q, f"[#{job.id}] "),
            "progress_hooks": [self._make_hook(job)],
            "postprocessor_hooks": [self._make_pp_hook(job)],
            "noprogress": True,
        }
        # JS-рантайм + решатель n-challenge: без них YouTube отдаёт только картинки
        js = find_js_runtime()
        if js:
            opts["js_runtimes"] = {js[0]: {"path": js[1]}}
        else:
            self.q.put(("log", "ВНИМАНИЕ: JS-рантайм (deno/node/bun) не найден — "
                               "YouTube может отдать только картинки."))
        # запасной вариант: если пакета yt-dlp-ejs нет, yt-dlp скачает решатель с GitHub
        opts["remote_components"] = ["ejs:github"]
        auth = False
        if self.use_auth_var.get():
            if not os.path.isfile(AUTH_COOKIES):
                raise ValueError("Нет сохранённого входа в аккаунт — нажмите «Войти в аккаунт».")
            opts["cookiefile"] = AUTH_COOKIES
            auth = True
        if self.ffmpeg_dir:
            opts["ffmpeg_location"] = self.ffmpeg_dir
        if proxy:
            opts["proxy"] = proxy
        if not audio_only:
            opts["merge_output_format"] = container
        if audio_only:
            pps = []
            if convert:
                pp = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
                if codec == "mp3":
                    pp["preferredquality"] = "0"
                pps.append(pp)
            if self.ffmpeg_dir:
                pps.append({"key": "FFmpegMetadata"})
            opts["postprocessors"] = pps
        elif s["subs"]:
            opts.update({
                "writesubtitles": True,
                "subtitleslangs": ["all", "-live_chat"],
                "postprocessors": [{"key": "FFmpegEmbedSubtitle"}],
            })
        details = (f"{job.fmt}; прокси: {proxy_safe or 'нет'}; "
                   f"аккаунт: {'да' if auth else 'нет'}; "
                   f"JS: {js[0] if js else 'нет'}; "
                   f"ОС: {TARGET_OS_LABELS.get(target, target)}")
        return opts, details

    def _run_job(self, job, opts):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([job.url])
            self.q.put(("job_done", job.id, "done", ""))
        except Exception as e:  # noqa: BLE001
            if job.cancel_event.is_set() or isinstance(e, Cancelled):
                self.q.put(("job_done", job.id, "cancelled", ""))
            else:
                self.q.put(("job_done", job.id, "error", strip_ansi(e) + self._auth_hint(e, opts)))

    def _make_hook(self, job):
        st = {"t": 0.0, "title": None}

        def hook(d):
            if job.cancel_event.is_set():
                raise Cancelled()
            info = d.get("info_dict") or {}
            pi, n = info.get("playlist_index"), info.get("n_entries")
            is_pl = bool(pi and n and n > 1)
            title = info.get("title")
            if is_pl and info.get("playlist_title"):
                title = f"{info['playlist_title']} · {n} видео"
            if title and title != st["title"]:
                st["title"] = title
                self.q.put(("title", job.id, title))
            status = d.get("status")
            if status == "downloading":
                now = time.monotonic()
                if now - st["t"] < 0.3:
                    return
                st["t"] = now
                done = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = done / total * 100 if total else 0.0
                parts = []
                if is_pl:
                    parts.append(f"[{pi}/{n}]")
                if not total:
                    parts.append(f"{done / 1024 / 1024:.1f} МБ")
                tail = []
                if d.get("speed"):
                    tail.append(f"{d['speed'] / 1024 / 1024:.2f} МБ/с")
                if d.get("eta") is not None:
                    tail.append(f"{int(d['eta'])} с")
                if tail:
                    parts.append(" · ".join(tail))
                self.q.put(("progress", job.id, pct, " ".join(parts)))
            elif status == "finished":
                self.q.put(("progress", job.id, 100.0, "Обработка (ffmpeg)..."))
        return hook

    def _make_pp_hook(self, job):
        def hook(d):
            if d.get("status") == "finished":
                fp = (d.get("info_dict") or {}).get("filepath")
                if fp:
                    job.filepath = fp
        return hook

    @staticmethod
    def _auth_hint(err, opts):
        text = strip_ansi(err).lower()
        needs_login = any(k in text for k in (
            "private video", "sign in", "log in", "login required", "confirm your age",
            "members-only", "join this channel", "confirm you"))
        if not needs_login:
            return ""
        if "cookiefile" in opts:
            return ("\n\nСессия могла устареть или у аккаунта нет доступа к этому видео. "
                    "Нажмите «Войти заново» (вкладка «Настройки») и повторите.")
        return ("\n\nВидео требует входа. Включите «Скачивать под моим аккаунтом» "
                "на вкладке «Настройки» и войдите.")

    def _finish_job(self, job, state, msg):
        job.state = state
        job.cancelling = False
        job.error = msg if state == "error" else ""
        if state == "done":
            job.pct = 100.0
            job.info = ""
        self._refresh_row(job)
        if state == "done":
            self._log(f"Готово #{job.id}: {job.title}")
        elif state == "cancelled":
            self._log(f"Отменено #{job.id}: {job.title}")
        else:
            self._log(f"ОШИБКА: #{job.id}: {msg}")
        self._history_add(job, state, msg)

    # --- строки таблицы очереди
    @staticmethod
    def _bar(pct):
        n = max(0, min(10, int(pct // 10)))
        return "█" * n + "░" * (10 - n)

    def _prog_text(self, job):
        if job.state == "running":
            t = f"{self._bar(job.pct)} {job.pct:.0f}%"
            return t + ("  " + job.info if job.info else "")
        if job.state == "done":
            return f"{self._bar(100)} 100%"
        if job.state == "error":
            return (job.error.splitlines() or [""])[0][:90]
        return "—"

    def _row_values(self, job):
        label = "Отмена…" if job.cancelling else STATE_LABEL[job.state]
        return (job.id, job.title, job.fmt, label, self._prog_text(job))

    def _refresh_row(self, job):
        iid = str(job.id)
        if self.q_tree.exists(iid):
            self.q_tree.item(iid, values=self._row_values(job),
                             tags=("cancelling" if job.cancelling else job.state,))

    def _update_footer(self):
        run, que = self._running_count(), self._queued_count()
        if self.js_busy and que:
            text = f"Настройка компонентов YouTube… загрузок в ожидании: {que}"
        elif self.update_busy and que:
            text = f"Обновление yt-dlp… загрузок в ожидании: {que}"
        elif self.auth_busy and que:
            text = f"Ожидание входа в аккаунт… загрузок в ожидании: {que}"
        elif run or que:
            text = f"Загрузка: {run} из {self._max_parallel()} · в очереди: {que}"
        else:
            text = self.idle_text
        self.status_var.set(text)
        total = run + que
        self.right_nb.tab(self.queue_tab, text=f"Очередь ({total})" if total else "Очередь")

    # --- действия над очередью
    def _selected_jobs(self):
        out = []
        for iid in self.q_tree.selection():
            job = self.job_map.get(int(iid))
            if job:
                out.append(job)
        return out

    def _remove_job(self, job):
        if self.q_tree.exists(str(job.id)):
            self.q_tree.delete(str(job.id))
        if job in self.jobs:
            self.jobs.remove(job)
        self.job_map.pop(job.id, None)

    def _cancel_job(self, job):
        if job.state == "queued":
            self._remove_job(job)
            self._log(f"Убрано из очереди #{job.id}")
        elif job.state == "running" and not job.cancelling:
            job.cancelling = True
            job.cancel_event.set()
            self._refresh_row(job)

    def _cancel_selected(self):
        for job in self._selected_jobs():
            self._cancel_job(job)
        self._pump()

    def _cancel_all(self):
        for job in list(self.jobs):
            self._cancel_job(job)
        self._pump()

    def _retry_selected(self):
        for job in self._selected_jobs():
            if job.state in ("error", "cancelled"):
                job.reset()
                self._refresh_row(job)
        self._pump()

    def _clear_finished(self):
        for job in list(self.jobs):
            if job.state in ("done", "error", "cancelled"):
                self._remove_job(job)
        self._update_footer()

    def _queue_dbl(self, event):
        iid = self.q_tree.identify_row(event.y)
        job = self.job_map.get(int(iid)) if iid else None
        if not job:
            return
        if job.state == "done":
            self._open_file_or_folder(job.filepath, job.s["out"])
        elif job.state == "error":
            messagebox.showerror("Ошибка загрузки", job.error[:800])

    # ------------------------------------------------------------ история
    def _load_history(self):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.history = [h for h in data if isinstance(h, dict) and "id" in h][:HISTORY_MAX]
        except (OSError, ValueError, TypeError):
            self.history = []

    def _save_history(self):
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    @staticmethod
    def _hist_values(rec):
        st = rec.get("status", "")
        return (rec.get("t", ""), rec.get("title", ""), rec.get("site", ""),
                rec.get("fmt", ""), STATE_LABEL.get(st, st))

    def _fill_history(self):
        for iid in self.h_tree.get_children():
            self.h_tree.delete(iid)
        for rec in self.history:
            self.h_tree.insert("", "end", iid=str(rec["id"]), values=self._hist_values(rec),
                               tags=(rec.get("status", ""),))

    def _history_add(self, job, state, msg):
        rec = {
            "id": time.time_ns(),
            "t": time.strftime("%Y-%m-%d %H:%M"),
            "title": job.title,
            "url": job.url,
            "site": site_name(job.url),
            "fmt": job.fmt,
            "out": job.s["out"],
            "path": job.filepath or "",
            "status": state,
            "msg": msg,
            "settings": job.s,
        }
        self.history.insert(0, rec)
        while len(self.history) > HISTORY_MAX:
            old = self.history.pop()
            if self.h_tree.exists(str(old["id"])):
                self.h_tree.delete(str(old["id"]))
        self.h_tree.insert("", 0, iid=str(rec["id"]), values=self._hist_values(rec),
                           tags=(state,))
        self._save_history()

    def _hist_selected(self):
        ids = {str(i) for i in self.h_tree.selection()}
        return [r for r in self.history if str(r["id"]) in ids]

    def _hist_open(self):
        recs = self._hist_selected()
        if recs:
            self._open_file_or_folder(recs[0].get("path"), recs[0].get("out"))

    def _hist_reveal(self):
        recs = self._hist_selected()
        if recs:
            self._reveal(recs[0].get("path"), recs[0].get("out"))

    def _hist_dbl(self, event):
        iid = self.h_tree.identify_row(event.y)
        rec = next((r for r in self.history if str(r["id"]) == iid), None)
        if not rec:
            return
        if rec.get("status") == "error":
            messagebox.showerror("Ошибка загрузки", (rec.get("msg") or "")[:800])
        else:
            self._open_file_or_folder(rec.get("path"), rec.get("out"))

    def _hist_redownload(self):
        recs = self._hist_selected()
        if not recs:
            return
        n = 0
        for rec in reversed(recs):
            s = dict(rec.get("settings") or self._current_settings())
            s.setdefault("out", rec.get("out") or self.out_var.get().strip())
            n += self._enqueue([rec["url"]], s)
        if n:
            self._save_config()

    def _hist_delete(self):
        recs = self._hist_selected()
        if not recs:
            return
        ids = {r["id"] for r in recs}
        self.history = [r for r in self.history if r["id"] not in ids]
        for i in ids:
            if self.h_tree.exists(str(i)):
                self.h_tree.delete(str(i))
        self._save_history()

    def _hist_clear(self):
        if not self.history:
            return
        if not messagebox.askyesno("История", "Очистить всю историю загрузок?\n"
                                   "Сами скачанные файлы останутся на диске."):
            return
        self.history = []
        self._fill_history()
        self._save_history()

    # ------------------------------------------------- открытие файлов/папок
    def _open_path(self, path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as e:
            self._log(f"Не удалось открыть: {e}")

    def _open_file_or_folder(self, path, folder):
        if path and os.path.isfile(path):
            self._open_path(path)
        elif folder and os.path.isdir(folder):
            self._open_path(folder)
        else:
            messagebox.showinfo("Открыть", "Файл не найден — возможно, он перемещён или удалён.")

    def _reveal(self, path, folder):
        try:
            if path and os.path.isfile(path):
                if sys.platform.startswith("win"):
                    subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", path])
                else:
                    self._open_path(os.path.dirname(path))
                return
        except OSError as e:
            self._log(f"Не удалось открыть: {e}")
            return
        if folder and os.path.isdir(folder):
            self._open_path(folder)
        else:
            messagebox.showinfo("Открыть", "Папка не найдена.")

    # ------------------------------------------------------ yt-dlp update
    def _check_update(self, auto):
        if self.update_busy:
            return
        if self._running_count():
            if not auto:
                messagebox.showinfo("Обновление", "Дождитесь окончания загрузок или отмените их.")
            return
        try:
            proxy, _ = self._build_proxy_url()
        except ValueError:
            proxy = None
        self.update_busy = True
        self.update_btn.configure(state="disabled")
        self._log("Проверка обновлений yt-dlp...")
        threading.Thread(target=self._update_worker, args=(proxy,), daemon=True).start()

    def _update_worker(self, proxy):
        try:
            latest = fetch_latest_version(proxy)
        except Exception as e:  # noqa: BLE001
            self.q.put(("update", f"Не удалось проверить обновления: {e}", False))
            return
        if _version_tuple(latest) <= _version_tuple(YTDLP_VERSION):
            self.q.put(("update", f"yt-dlp актуален ({YTDLP_VERSION}).", False))
            return
        self.q.put(("log", f"Новая версия yt-dlp: {latest} (сейчас {YTDLP_VERSION}). Скачиваю в папку lib..."))
        ok, out = install_or_update_ytdlp(proxy)
        if ok:
            self.q.put(("update", f"yt-dlp обновлён до {latest}.", True))
        else:
            self.q.put(("update", "Не удалось обновить yt-dlp:\n" + out[-600:], False))

    # ------------------------------------------- JS-рантайм / yt-dlp-ejs
    def _ensure_js(self):
        if self.js_busy or not js_needs_setup():
            return
        try:
            proxy, _ = self._build_proxy_url()
        except ValueError:
            proxy = None
        self.js_busy = True
        self._log("Настройка компонентов для YouTube (JS-рантайм и решатель n-challenge)...")
        self._update_footer()
        threading.Thread(target=self._js_worker, args=(proxy,), daemon=True).start()

    def _js_worker(self, proxy):
        try:
            ok, msg = install_ejs(proxy)
            self.q.put(("log", msg if ok else "ВНИМАНИЕ: не удалось установить yt-dlp-ejs: " + msg))
            if find_js_runtime() is None:
                self.q.put(("log", "Скачиваю Deno (JavaScript-рантайм) в папку bin..."))
                ok, msg = install_deno(proxy)
                self.q.put(("log", msg if ok else
                            "ВНИМАНИЕ: не удалось скачать Deno: " + msg +
                            "\nУстановите Node.js или положите " + ("deno.exe" if IS_WIN else "deno") + " в папку bin вручную."))
        finally:
            self.q.put(("jsdone",))

    def _offer_restart(self):
        global yt_dlp, YTDLP_VERSION
        new_mod = _import_ytdlp()
        if new_mod is not None:
            yt_dlp = new_mod
            YTDLP_VERSION = yt_dlp.version.__version__
            self.ver_var.set(f"yt-dlp {YTDLP_VERSION}")
            self._log(f"Модуль yt-dlp {YTDLP_VERSION} успешно перезагружен на лету!")
            self._ensure_js()  # новая версия yt-dlp может требовать другую версию yt-dlp-ejs

        if self._running_count() or self._queued_count():
            return
        if messagebox.askyesno("yt-dlp обновлён",
                               f"Установлена новая версия yt-dlp ({YTDLP_VERSION}).\n"
                               "Перезапустить программу сейчас для полного применения?"):
            self._save_config()
            try:
                if FROZEN:
                    subprocess.Popen([sys.executable] + sys.argv[1:])
                else:
                    subprocess.Popen([sys.executable] + sys.argv)
            except OSError as e:
                self._log(f"Не удалось перезапустить: {e}. Запустите программу вручную.")
                return
            self.destroy()

    def _poll_queue(self):
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._log(item[1])
                elif kind == "progress":
                    job = self.job_map.get(item[1])
                    if job and job.state == "running":
                        job.pct = item[2]
                        job.info = item[3]
                        self._refresh_row(job)
                elif kind == "title":
                    job = self.job_map.get(item[1])
                    if job:
                        job.title = item[2]
                        self._refresh_row(job)
                elif kind == "job_done":
                    job = self.job_map.get(item[1])
                    if job:
                        self._finish_job(job, item[2], item[3])
                        self._pump()
                        if not self._running_count() and not self._queued_count():
                            self.idle_text = "Все загрузки завершены"
                            self._update_footer()
                elif kind == "jsdone":
                    self.js_busy = False
                    self._pump()
                elif kind == "update":
                    self.update_busy = False
                    self.update_btn.configure(state="normal")
                    self._log(item[1])
                    self._pump()
                    if item[2]:
                        self._offer_restart()
                elif kind == "auth":
                    self.auth_busy = False
                    if item[1]:
                        self.use_auth_var.set(True)
                        self._log(item[2])
                    elif item[2] == "Вход отменён.":
                        self._log(item[2])
                    else:
                        self._log("ОШИБКА: " + item[2])
                    self._auth_refresh_ui()
                    self._pump()
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

if __name__ == "__main__":
    App().mainloop()
