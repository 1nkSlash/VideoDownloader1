# Сборка Video Downloader

PyInstaller не умеет кросс-компиляцию: собирать нужно на той ОС, для которой делается билд.

| ОС | Команда | Результат |
|---|---|---|
| Windows | `build_windows.bat` | `release\VideoDownloader\` |
| macOS | `./build_mac.sh` | `release/VideoDownloader/` + zip |
| Linux | `./build_linux.sh` | `release/VideoDownloader/` + tar.gz |

Требуется Python 3.10+ с Tk (Linux: `python3-tk`; macOS — Python с python.org или `brew install python-tk`).
PyInstaller не умеет кросс-компиляцию: собирать нужно на той ОС, для которой делается билд.
Все три сразу: залить папку в GitHub → Actions → Build → Run workflow.

**Всё вшито в сборку — пользователю ничего ставить и скачивать не нужно, работает без интернета (кроме самих загрузок):**
Python, ffmpeg, ffprobe, deno (JS-рантайм для YouTube), yt-dlp и yt-dlp-ejs.

    VideoDownloader/
      VideoDownloader(.exe)      <- запускать его
      _internal/                 <- внутри: bin/ffmpeg, bin/ffprobe, bin/deno, yt-dlp (Windows/Linux)
    VideoDownloader.app          <- на macOS всё внутри .app

Распространять нужно папку целиком (zip / tar.gz из `release/`): распаковал и запустил.
Это папка, а не один exe: единый файл с ffmpeg и deno (~250 МБ) распаковывался бы в temp при каждом запуске.

`fetch_ffmpeg.py` перед сборкой скачивает ffmpeg/ffprobe/deno в `bin/` (Windows — BtbN, Linux — johnvansickle,
macOS — martin-riedl.de / evermeet.cx, deno — GitHub Releases). Свои бинарники можно положить в `bin/` заранее.
yt-dlp и yt-dlp-ejs берутся из `requirements-build.txt` (актуальные версии на момент сборки).
Иконка: `icon.ico` / `icon.icns` / `icon.png` рядом со spec.

**Обновление yt-dlp** (кнопка в программе) скачивает свежий yt-dlp в профиль пользователя
(Windows: `%LOCALAPPDATA%\\VideoDownloader\\lib`, macOS: `~/Library/Application Support/VideoDownloader/lib`,
Linux: `~/.config/VideoDownloader/lib`) и он перекрывает вшитый. Если вшитый новее скачанного
(вышла новая версия программы), используется вшитый. Рядом с программой ничего не создаётся.
