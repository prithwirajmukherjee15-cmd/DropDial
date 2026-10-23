<p align="center">
  <img src="docs/banner.png" alt="DropDial: перетащите файл, нажмите Shift и отпустите его на диске" width="100%">
</p>

<p align="center">
  <b>Бесплатный конвертер файлов с открытым исходным кодом, которым пользуются перетаскиванием.</b><br>
  Перетащите любой файл, нажмите <kbd>Shift</kbd> и отпустите его на секторе стеклянного диска, который открывается прямо у курсора.
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><b>Скачать</b></a> ·
  <a href="#установка">Установка</a> ·
  <a href="#первый-запуск">Первый запуск</a> ·
  <a href="#форматы">Форматы</a> ·
  <a href="#командная-строка">Командная строка</a> ·
  <a href="#разработка">Разработка</a>
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml"><img src="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><img src="https://img.shields.io/github/v/release/prithwirajmukherjee15-cmd/DropDial?color=d8ad62&label=release" alt="Последняя версия"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases"><img src="https://img.shields.io/github/downloads/prithwirajmukherjee15-cmd/DropDial/total?color=a87a34" alt="Загрузки"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-2b2f3a" alt="Windows 10 | 11">
  <img src="https://img.shields.io/badge/macOS-11%2B-2b2f3a" alt="macOS 11+">
  <img src="https://img.shields.io/badge/Linux-x64-2b2f3a" alt="Linux x64">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-e3be7a" alt="Лицензия MIT"></a>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.hi.md">हिन्दी</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a> · <a href="README.pt-BR.md">Português (Brasil)</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <a href="README.zh-CN.md">简体中文</a> · <b>Русский</b> · <a href="README.ar.md">العربية</a></p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg"><img src="docs/btn-mac-arm.svg" alt="Скачать для macOS (Apple Silicon)" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg"><img src="docs/btn-mac-intel.svg" alt="Скачать для macOS (Intel)" height="56"></a>
  <br>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe"><img src="docs/btn-win.svg" alt="Скачать для Windows" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb"><img src="docs/btn-linux.svg" alt="Скачать для Linux" height="56"></a>
</p>

> [!IMPORTANT]
> **Открываете DropDial впервые?** Windows и macOS один раз покажут предупреждение безопасности, потому что у приложения пока нет цифровой подписи. Оно безопасно, а чтобы пройти предупреждение, нужно секунд 10. **[См. «Первый запуск» ↓](#первый-запуск)**

<table>
  <tr>
    <td width="33%" valign="top"><b>Прямо у курсора</b><br>Не нужно открывать окно приложения. Диск появляется там, где вы уже находитесь, и показывает только те форматы, которые подходят для перетаскиваемых файлов.</td>
    <td width="33%" valign="top"><b>Более 140 типов файлов, без других программ</b><br>Изображения, RAW с камер, PDF, Word, Excel, электронные книги, видео, аудио, субтитры, архивы, шрифты, 3D-модели и картографические файлы работают без Office и любых других установленных программ.</td>
    <td width="33%" valign="top"><b>Всё остаётся на вашем компьютере</b><br>Ничего не загружается в сеть. DropDial работает офлайн и сохраняет результат рядом с оригиналом, никогда не поверх него.</td>
  </tr>
</table>

## Как это выглядит

<p align="center">
  <img src="docs/demo.gif" alt="Перетаскиваем фото, нажимаем Shift и отпускаем на Compress" width="760">
</p>

## Установка

Скачайте со страницы [Releases](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest).

- **macOS 11+**: откройте `.dmg` ([Apple Silicon](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg) · [Intel](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg)) и перетащите DropDial в «Программы». Или вставьте эту строку в Терминал: она выберет нужную сборку, установит её без предупреждений безопасности и обновит при повторном запуске:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/DropDial/main/install-mac.sh | bash
  ```
- **Windows 10/11**: запустите [`DropDial-Setup.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe) (устанавливается для вашего пользователя, без прав администратора; добавляет пункт в контекстное меню, в меню *Отправить* и автозапуск с Windows) или используйте портативный [`DropDial.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial.exe).
- **Linux x64** (Debian 12+, Ubuntu 23.04+, Mint…): `sudo apt install ./DropDial-linux-amd64.deb` ([скачать](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb)). Жесту с Shift нужен X11; в Wayland используйте зону перетаскивания в Home или правый клик → **Открыть с помощью → DropDial**.
- **Linux ARM64** (Ubuntu 24.04+, Debian 13+, Raspberry Pi OS 13 64-бит…): `sudo apt install ./DropDial-linux-arm64.deb` ([скачать](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-arm64.deb)).

DropDial живёт в строке меню / системном трее и сообщает, когда выходит новая версия.

## Первый запуск

У DropDial пока нет цифровой подписи (сертификаты для подписи стоят денег каждый год), поэтому Windows и macOS показывают предупреждение **только в первый раз**. Весь код DropDial открыт в этом репозитории, а файлы для загрузки GitHub собирает из него автоматически.

### Windows: «Windows защитила ваш компьютер»

SmartScreen может показать это окно при первом запуске `DropDial-Setup.exe` или `DropDial.exe`.

1. Нажмите **Подробнее**.
2. Нажмите **Выполнить в любом случае**.

Вот и всё. Больше Windows спрашивать не будет.

### Mac: «Apple не удалось проверить DropDial…»

Если вы установили приложение командой для Терминала выше, этот шаг можно пропустить: предупреждения не будет. При установке из **.dmg** macOS сообщает: *«Apple не удалось проверить, что „DropDial“ не содержит вредоносного ПО, которое может нанести вред Mac или поставить под угрозу Вашу конфиденциальность».* Так macOS пишет о любом приложении, которое не прошло платное нотариальное заверение Apple. Чтобы открыть его:

1. Один раз откройте **DropDial** из «Программ» и нажмите **Готово** в предупреждении.
2. Откройте **меню Apple → Системные настройки → Конфиденциальность и безопасность**. Прокрутите вниз до строки **Приложение «DropDial» заблокировано для защиты Mac** и нажмите **Всё равно открыть**.
3. Введите пароль и ещё раз нажмите **Всё равно открыть** для подтверждения.

Готово. macOS запомнит выбор, так что делать это нужно только один раз.

<details>
<summary>Предпочитаете Терминал? Одна команда делает то же самое</summary>

```bash
xattr -dr com.apple.quarantine /Applications/DropDial.app
```

После этого откройте DropDial как обычно.
</details>

> [!NOTE]
> В macOS 15 (Sequoia) и новее старый способ **правый клик → Открыть** больше не помогает обойти это предупреждение. Используйте шаги выше.

### Mac, по желанию: запись экрана

DropDial может запросить разрешение на **Запись экрана**. Если разрешить, стеклянный диск будет показывать окна позади себя. Если нет, всё продолжит работать, а в стекле будут видны обои рабочего стола. **Ничего никогда не записывается, не сохраняется и никуда не отправляется.** Изменить это можно в любой момент в **Системные настройки → Конфиденциальность и безопасность → Запись экрана и системного звука**.

## Возможности

- **Диск у курсора**: перетащите файлы, нажмите <kbd>Shift</kbd> и отпустите их на формате. Показываются только форматы, подходящие для этих файлов.
- **Не одна сторона**: нажмите <kbd>Shift</kbd> ещё раз, нажмите <kbd>Tab</kbd> или покрутите колесо мыши, чтобы перевернуть диск на **More formats**, **Tools** и **Recipes**.
- **Прямо из браузера**: перетащите картинку, ссылку на файл или загрузку из Chrome, Edge, Firefox или Safari. DropDial сохранит её в «Загрузки», а затем сконвертирует.
- **Home**: щёлкните значок в трее / строке меню, чтобы открыть зону перетаскивания (без Shift) и последние результаты с превью. Открывайте, показывайте в папке, конвертируйте заново или отменяйте.
- **Инструменты для каждого типа файлов**: сжатие, изменение размера, обрезка, редактирование, пометки, скрытие данных, водяные знаки и удаление метаданных для изображений; разделение, объединение, поворот, нумерация страниц, защита паролем, снятие защиты и сжатие PDF; сжатие, отключение звука и поворот видео; нормализация громкости аудио; очистка субтитров; урезание шрифтов до нужных символов; починка 3D-моделей; статистика поездок по GPS-трекам; и многое другое.
- **Recipes**: объединяйте несколько шагов в один сектор («Web-ready», «Email size», «Private»…) или создавайте свои.
- **Отслеживаемые папки** конвертируют каждый файл, который в них попадает.
- **Много файлов сразу**, сектор ZIP для кучи файлов или папки и **History**, чтобы найти или отменить что угодно.
- **Другие способы**: контекстное меню, *Отправить* (Windows), зона перетаскивания в Home и [команда `dropdial`](#командная-строка).
- **Ваш стиль**: диск из жидкого стекла с акцентным цветом на выбор (Champagne, Rose, Ocean, Emerald, Violet, Silver).

## Скриншоты

<table>
  <tr>
    <td width="58%"><img src="docs/screen-home.png" alt="Home: зона перетаскивания и последние результаты с превью"></td>
    <td width="42%"><img src="docs/screen-dial.png" alt="Диск для электронной таблицы: XLSX, PDF, JSON, HTML, DOCX, MD"></td>
  </tr>
  <tr>
    <td align="center"><sub>Home: зона перетаскивания и последние результаты (3D-рендер, GPS-карта, образец шрифта…)</sub></td>
    <td align="center"><sub>Диск для электронной таблицы; переверните его, чтобы увидеть More formats и Tools</sub></td>
  </tr>
</table>

## Форматы

| Из | В |
|---|---|
| **Изображения**: JPG, PNG, WEBP, HEIC, AVIF, TIFF, GIF, BMP, ICO | друг в друга, PDF, SVG (трассировка), ICNS, TGA, QOI |
| **Профессиональные изображения**: RAW с камер (CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2…), PSD, TGA, QOI, JPEG 2000, DDS, ICNS, PPM… | JPG, PNG, TIFF (16 бит для RAW), WEBP, AVIF, HEIC, PDF |
| **Векторная графика**: SVG | PDF (остаётся векторным), PNG, JPG, WEBP, ICO |
| **PDF** | JPG, PNG, DOCX, TXT; объединение, разделение, поворот, сжатие, нумерация, водяной знак, защита, снятие защиты, извлечение изображений |
| **Документы**: DOCX, TXT, Markdown, HTML, сохранённые веб-страницы (MHTML), reStructuredText | PDF, DOCX, HTML, Markdown, TXT |
| **Почта**: EML | PDF, DOCX, HTML, TXT; сохранение вложений |
| **Таблицы**: XLSX, XLSM, XLS, ODS, CSV, TSV | XLSX, ODS, CSV, TSV, JSON, HTML, PDF, DOCX, Markdown; CSV с контактами → VCF; объединение, разделение листов |
| **Данные**: JSON, JSON Lines, YAML, TOML, XML, plist, vCard | друг в друга, CSV, XLSX, PDF |
| **Электронные книги**: EPUB, MOBI, FB2, CBZ, XPS | PDF, DOCX, TXT |
| **Видео**: MP4, MOV, MKV, WEBM, AVI, WMV, FLV, M4V, MPEG, 3GP | MP4, WEBM, MOV, GIF, MP3; сжатие, отключение звука, поворот, стоп-кадр (HDR с iPhone приводится тональной компрессией) |
| **Аудио**: MP3, M4A, AAC, WAV, FLAC, OGG, OPUS, WMA, AIFF | MP3, M4A, WAV, FLAC, OGG; нормализация громкости, обрезка тишины, сжатие |
| **Субтитры**: SRT, WebVTT, ASS/SSA, SBV, MicroDVD, SAMI, LRC, TTML | друг в друга в UTF-8, TXT; очистка субтитров, исправление тайминга 25 / 23,976 кадра/с |
| **Архивы**: ZIP, 7Z, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, GZ, BZ2, XZ | распаковка, ZIP, 7Z, TAR.GZ; любые файлы или папка → один ZIP |
| **Шрифты**: TTF, OTF, WOFF, WOFF2, TTC | друг в друга, образец в PNG / PDF; латинское подмножество, набор веб-шрифтов |
| **3D-модели**: STL, OBJ, PLY, GLB, glTF, OFF, 3MF | друг в друга, превью PNG; центрирование и установка на пол, починка, упрощение сетки |
| **Картографические данные**: GPX, KML, KMZ, GeoJSON, Shapefile | друг в друга, CSV, карта PNG; статистика поездки, разворот маршрута, упрощение |

Всё работает сразу после установки: в загрузках уже есть все движки (FFmpeg для видео и аудио).
`dropdial formats` выводит полный список для вашей копии.

## Командная строка

Команда `dropdial` использует те же движки и рецепты, что и приложение (из исходников: `python -m dropdial`).

```bash
dropdial convert *.heic --to jpg
dropdial convert report.md --to pdf
dropdial convert ride.gpx --to kml
dropdial compress photo.jpg --target 500KB
dropdial pdf merge a.pdf b.pdf          # also: split, rotate, number, protect, unlock, extract, compress
dropdial media gif clip.mov --fps 15    # also: audio, mute, frame, rotate, normalize, trim-silence
dropdial recipe run web-ready ~/Pictures/*.png
dropdial watch ~/Screenshots --recipe web-ready
dropdial formats
```

Добавьте `--json`, чтобы получить машиночитаемый вывод; код выхода равен 1, если хотя бы один файл не удалось обработать.

## Разработка

Python 3.12, на Windows, macOS или Linux:

```bash
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
pip install -r requirements.txt pytest
python -m dropdial
python -m pytest -q          # on Linux without a display: QT_QPA_PLATFORM=offscreen
```

[Архитектура](docs/ARCHITECTURE.md) · [Как добавить формат файла](docs/ADDING-A-CONVERTER.md) · [Участие в разработке](CONTRIBUTING.md) · [Список изменений](CHANGELOG.md) · [Безопасность](SECURITY.md)

Pull request’ы приветствуются. Если DropDial экономит вам пару кликов, ⭐ поможет другим людям его найти.

## Цифровая подпись

DropDial разрабатывает и публикует **Prithwiraj Mukherjee**. Загрузки для Windows и macOS пока не подписаны и не заверены у Apple, поэтому система предупреждает при первом запуске (см. [Первый запуск](#первый-запуск)). Каждый файл для загрузки собирается GitHub Actions из исходного кода этого репозитория; ничего не собирается вручную.

### Конфиденциальность

DropDial конвертирует файлы на вашем собственном компьютере и никогда их не загружает. Он не собирает данные об использовании и не отправляет телеметрию. В интернет он выходит только:

- чтобы спросить у GitHub (`api.github.com`), нет ли новой версии: вскоре после запуска, а затем раз в несколько часов. Это можно отключить в Settings («Check for updates automatically»).
- чтобы скачать файл, который вы перетащили из браузера на диск.
- когда вы нажимаете на ссылку, которая открывается в браузере.

## Лицензия

MIT, © 2026 Prithwiraj Mukherjee. Входящие в комплект сторонние компоненты распространяются под своими лицензиями, перечисленными в [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

<p align="center">
  <a href="https://star-history.com/#prithwirajmukherjee15-cmd/DropDial&Date"><img src="https://api.star-history.com/svg?repos=prithwirajmukherjee15-cmd/DropDial&type=Date" alt="История звёзд" width="600"></a>
</p>

<p align="center"><sub>Автор: <b>Prithwiraj Mukherjee</b></sub></p>
