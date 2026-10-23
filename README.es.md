<p align="center">
  <img src="docs/banner.png" alt="DropDial: arrastra un archivo, pulsa Shift y suéltalo en el dial" width="100%">
</p>

<p align="center">
  <b>Un conversor de archivos gratuito y de código abierto que se usa arrastrando.</b><br>
  Arrastra cualquier archivo, pulsa <kbd>Shift</kbd> y suéltalo en una porción del dial de cristal que se abre junto al cursor.
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><b>Descargar</b></a> ·
  <a href="#instalación">Instalación</a> ·
  <a href="#primer-inicio">Primer inicio</a> ·
  <a href="#formatos">Formatos</a> ·
  <a href="#línea-de-comandos">Línea de comandos</a> ·
  <a href="#desarrollo">Desarrollo</a>
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml"><img src="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><img src="https://img.shields.io/github/v/release/prithwirajmukherjee15-cmd/DropDial?color=d8ad62&label=release" alt="Última versión"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases"><img src="https://img.shields.io/github/downloads/prithwirajmukherjee15-cmd/DropDial/total?color=a87a34" alt="Descargas"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-2b2f3a" alt="Windows 10 | 11">
  <img src="https://img.shields.io/badge/macOS-11%2B-2b2f3a" alt="macOS 11+">
  <img src="https://img.shields.io/badge/Linux-x64-2b2f3a" alt="Linux x64">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-e3be7a" alt="Licencia MIT"></a>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.hi.md">हिन्दी</a> · <b>Español</b> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a> · <a href="README.pt-BR.md">Português (Brasil)</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ru.md">Русский</a> · <a href="README.ar.md">العربية</a></p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg"><img src="docs/btn-mac-arm.svg" alt="Descargar para macOS (Apple Silicon)" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg"><img src="docs/btn-mac-intel.svg" alt="Descargar para macOS (Intel)" height="56"></a>
  <br>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe"><img src="docs/btn-win.svg" alt="Descargar para Windows" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb"><img src="docs/btn-linux.svg" alt="Descargar para Linux" height="56"></a>
</p>

> [!IMPORTANT]
> **¿Vas a abrir DropDial por primera vez?** Windows y macOS muestran un aviso de seguridad una sola vez porque la app todavía no tiene firma de código. Es segura y saltarse el aviso lleva 10 segundos. **[Ver Primer inicio ↓](#primer-inicio)**

<table>
  <tr>
    <td width="33%" valign="top"><b>Justo en tu cursor</b><br>No hay ninguna ventana que abrir. El dial aparece donde ya estás, solo con los formatos que tienen sentido para los archivos que arrastras.</td>
    <td width="33%" valign="top"><b>Más de 140 tipos de archivo, sin otros programas</b><br>Imágenes, RAW de cámara, PDF, Word, Excel, libros electrónicos, vídeo, audio, subtítulos, archivos comprimidos, fuentes, modelos 3D y mapas funcionan sin Office ni nada más instalado.</td>
    <td width="33%" valign="top"><b>Todo se queda en tu ordenador</b><br>No se sube nada. DropDial funciona sin conexión y guarda el resultado junto al original, nunca encima.</td>
  </tr>
</table>

## Míralo en acción

<p align="center">
  <img src="docs/demo.gif" alt="Arrastrar una foto, pulsar Shift y soltarla en Compress" width="760">
</p>

## Instalación

Descárgalo desde [Releases](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest).

- **macOS 11+**: abre el `.dmg` ([Apple Silicon](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg) · [Intel](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg)) y arrastra DropDial a Aplicaciones. O pega esto en Terminal: elige la versión correcta, la instala sin ningún aviso de seguridad y la actualiza cada vez que lo vuelves a ejecutar:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/DropDial/main/install-mac.sh | bash
  ```
- **Windows 10/11**: ejecuta [`DropDial-Setup.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe) (se instala para tu usuario, sin permisos de administrador; añade el menú contextual, *Enviar a* y el inicio con Windows), o usa la versión portable [`DropDial.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial.exe).
- **Linux x64** (Debian 12+, Ubuntu 23.04+, Mint…): `sudo apt install ./DropDial-linux-amd64.deb` ([descargar](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb)). El gesto de Shift necesita X11; en Wayland, usa la zona para soltar de Home o clic derecho → **Abrir con → DropDial**.
- **Linux ARM64** (Ubuntu 24.04+, Debian 13+, Raspberry Pi OS 13 de 64 bits…): `sudo apt install ./DropDial-linux-arm64.deb` ([descargar](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-arm64.deb)).

DropDial vive en la barra de menús / bandeja del sistema y te avisa cuando sale una versión nueva.

## Primer inicio

DropDial todavía no tiene firma de código (los certificados de firma cuestan dinero cada año), así que Windows y macOS muestran un aviso **solo la primera vez**. Todo el código de DropDial es público en este repositorio, y GitHub genera las descargas a partir de él automáticamente.

### Windows: “Windows protegió su PC”

SmartScreen puede mostrar esto la primera vez que ejecutes `DropDial-Setup.exe` o `DropDial.exe`.

1. Haz clic en **Más información**.
2. Haz clic en **Ejecutar de todas formas**.

Listo. Windows no volverá a preguntar.

### Mac: “Apple no ha podido verificar DropDial…”

Si instalaste con la línea de Terminal de arriba, puedes saltarte esto: no aparece ningún aviso. Con el **.dmg**, macOS dice *“Apple no ha podido verificar que ‘DropDial’ esté libre de malware que pueda dañar tu Mac o comprometer tu privacidad.”* Lo dice de cualquier app que no haya pasado por la notarización de pago de Apple. Para abrirla:

1. Abre **DropDial** desde Aplicaciones una vez y cierra el aviso.
2. Abre **menú Apple → Ajustes del Sistema → Privacidad y seguridad**. Desplázate hasta **Se ha bloqueado “DropDial” para proteger tu Mac** y haz clic en **Abrir igualmente**.
3. Escribe tu contraseña y vuelve a hacer clic en **Abrir igualmente** para confirmar.

Hecho. macOS recuerda la elección, así que solo tienes que hacerlo una vez.

<details>
<summary>¿Prefieres Terminal? Un solo comando hace lo mismo</summary>

```bash
xattr -dr com.apple.quarantine /Applications/DropDial.app
```

Después abre DropDial como siempre.
</details>

> [!NOTE]
> En macOS 15 (Sequoia) y posteriores, el viejo atajo de **clic derecho → Abrir** ya no sirve para saltarse este aviso. Sigue los pasos de arriba.

### Mac, opcional: Grabación de pantalla

DropDial puede pedirte permiso de **Grabación de pantalla**. Si lo concedes, el dial de cristal muestra las ventanas que tiene detrás. Si no, todo sigue funcionando y el cristal muestra tu fondo de pantalla. **Nunca se graba, se guarda ni se envía nada.** Puedes cambiarlo cuando quieras en **Ajustes del Sistema → Privacidad y seguridad → Grabación de pantalla y audio del sistema**.

## Funciones

- **Un dial en el cursor**: arrastra archivos, pulsa <kbd>Shift</kbd> y suéltalos en un formato. Solo aparecen los formatos que encajan con esos archivos.
- **Más de una cara**: pulsa <kbd>Shift</kbd> otra vez, pulsa <kbd>Tab</kbd> o gira la rueda del ratón para pasar a **More formats**, **Tools** y **Recipes**.
- **Directamente desde el navegador**: arrastra una imagen, un enlace a un archivo o una descarga desde Chrome, Edge, Firefox o Safari. DropDial lo guarda en Descargas y luego lo convierte.
- **Home**: haz clic en el icono de la bandeja / barra de menús para abrir una zona donde soltar archivos (sin Shift) y tus resultados recientes con vista previa. Ábrelos, muéstralos en la carpeta, conviértelos otra vez o deshaz.
- **Herramientas para cada tipo de archivo**: comprimir, redimensionar, recortar, editar, anotar, censurar, añadir marca de agua y quitar metadatos de imágenes; dividir, unir, girar, numerar, proteger, desbloquear y comprimir PDF; comprimir, silenciar y girar vídeo; normalizar audio; limpiar subtítulos; reducir fuentes; reparar modelos 3D; estadísticas de recorridos GPS; y más.
- **Recipes**: encadena pasos en una sola porción ("Web-ready", "Email size", "Private"…) o crea las tuyas.
- **Carpetas vigiladas** que convierten cada archivo que cae en ellas.
- **Muchos archivos a la vez**, una porción ZIP para un montón de archivos o una carpeta, y **History** para encontrar o deshacer cualquier cosa.
- **Otras formas de entrar**: el menú contextual, *Enviar a* (Windows), la zona para soltar de Home y el [comando `dropdial`](#línea-de-comandos).
- **A tu estilo**: dial de cristal líquido con el color de acento que elijas (Champagne, Rose, Ocean, Emerald, Violet, Silver).

## Capturas de pantalla

<table>
  <tr>
    <td width="58%"><img src="docs/screen-home.png" alt="Home: zona para soltar y resultados recientes con vista previa"></td>
    <td width="42%"><img src="docs/screen-dial.png" alt="El dial para una hoja de cálculo: XLSX, PDF, JSON, HTML, DOCX, MD"></td>
  </tr>
  <tr>
    <td align="center"><sub>Home: zona para soltar y resultados recientes (un render 3D, un mapa GPS, una muestra de fuente…)</sub></td>
    <td align="center"><sub>El dial para una hoja de cálculo; dale la vuelta para ver More formats y Tools</sub></td>
  </tr>
</table>

## Formatos

| De | A |
|---|---|
| **Imágenes**: JPG, PNG, WEBP, HEIC, AVIF, TIFF, GIF, BMP, ICO | entre sí, PDF, SVG (vectorizado), ICNS, TGA, QOI |
| **Imágenes profesionales**: RAW de cámara (CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2…), PSD, TGA, QOI, JPEG 2000, DDS, ICNS, PPM… | JPG, PNG, TIFF (16 bits para RAW), WEBP, AVIF, HEIC, PDF |
| **Vectoriales**: SVG | PDF (sigue siendo vectorial), PNG, JPG, WEBP, ICO |
| **PDF** | JPG, PNG, DOCX, TXT; unir, dividir, girar, comprimir, numerar, marca de agua, proteger, desbloquear, extraer imágenes |
| **Documentos**: DOCX, TXT, Markdown, HTML, páginas web guardadas (MHTML), reStructuredText | PDF, DOCX, HTML, Markdown, TXT |
| **Correo**: EML | PDF, DOCX, HTML, TXT; guardar adjuntos |
| **Hojas de cálculo**: XLSX, XLSM, XLS, ODS, CSV, TSV | XLSX, ODS, CSV, TSV, JSON, HTML, PDF, DOCX, Markdown; CSV de contactos → VCF; combinar, dividir hojas |
| **Datos**: JSON, JSON Lines, YAML, TOML, XML, plist, vCard | entre sí, CSV, XLSX, PDF |
| **Libros electrónicos**: EPUB, MOBI, FB2, CBZ, XPS | PDF, DOCX, TXT |
| **Vídeo**: MP4, MOV, MKV, WEBM, AVI, WMV, FLV, M4V, MPEG, 3GP | MP4, WEBM, MOV, GIF, MP3; comprimir, silenciar, girar, fotograma fijo (el HDR del iPhone se adapta con tone mapping) |
| **Audio**: MP3, M4A, AAC, WAV, FLAC, OGG, OPUS, WMA, AIFF | MP3, M4A, WAV, FLAC, OGG; normalizar volumen, recortar silencios, comprimir |
| **Subtítulos**: SRT, WebVTT, ASS/SSA, SBV, MicroDVD, SAMI, LRC, TTML | entre sí en UTF-8, TXT; limpiar subtítulos, corregir tiempos 25 / 23,976 fps |
| **Archivos comprimidos**: ZIP, 7Z, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, GZ, BZ2, XZ | extraer, ZIP, 7Z, TAR.GZ; cualquier archivo o carpeta → un ZIP |
| **Fuentes**: TTF, OTF, WOFF, WOFF2, TTC | entre sí, muestra en PNG / PDF; subconjunto latino, kit de fuentes web |
| **Modelos 3D**: STL, OBJ, PLY, GLB, glTF, OFF, 3MF | entre sí, vista previa PNG; centrar y apoyar en el suelo, reparar, simplificar |
| **Datos de mapas**: GPX, KML, KMZ, GeoJSON, Shapefile | entre sí, CSV, mapa PNG; estadísticas del recorrido, invertir, simplificar |

Todo funciona nada más instalarlo: las descargas incluyen todos los motores (FFmpeg para vídeo y audio).
`dropdial formats` muestra la lista completa de tu copia.

## Línea de comandos

El comando `dropdial` usa los mismos motores y recetas que la app (desde el código fuente: `python -m dropdial`).

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

Añade `--json` para obtener una salida legible por máquinas; el código de salida es 1 si algún archivo falla.

## Desarrollo

Python 3.12, en Windows, macOS o Linux:

```bash
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
pip install -r requirements.txt pytest
python -m dropdial
python -m pytest -q          # on Linux without a display: QT_QPA_PLATFORM=offscreen
```

[Arquitectura](docs/ARCHITECTURE.md) · [Añadir un formato de archivo](docs/ADDING-A-CONVERTER.md) · [Contribuir](CONTRIBUTING.md) · [Registro de cambios](CHANGELOG.md) · [Seguridad](SECURITY.md)

Los pull requests son bienvenidos. Si DropDial te ahorra unos cuantos clics, una ⭐ ayuda a que otras personas lo encuentren.

## Firma de código

DropDial lo desarrolla y publica **Prithwiraj Mukherjee**. Las descargas para Windows y macOS todavía no tienen firma de código ni notarización, y por eso el sistema avisa la primera vez (consulta [Primer inicio](#primer-inicio)). Cada descarga la genera GitHub Actions a partir del código de este repositorio; nada se compila a mano.

### Privacidad

DropDial convierte los archivos en tu propio ordenador y nunca los sube. No recopila datos de uso ni envía telemetría. Solo se conecta a internet:

- para preguntar a GitHub (`api.github.com`) si hay una versión más reciente, poco después de iniciarse y luego cada pocas horas. Puedes desactivarlo en Settings ("Check for updates automatically").
- para descargar un archivo que arrastres desde tu navegador al dial.
- cuando haces clic en un enlace, que se abre en tu navegador.

## Licencia

MIT, © 2026 Prithwiraj Mukherjee. Los componentes de terceros incluidos mantienen sus propias licencias, que se enumeran en [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

<p align="center">
  <a href="https://star-history.com/#prithwirajmukherjee15-cmd/DropDial&Date"><img src="https://api.star-history.com/svg?repos=prithwirajmukherjee15-cmd/DropDial&type=Date" alt="Historial de estrellas" width="600"></a>
</p>

<p align="center"><sub>Hecho por <b>Prithwiraj Mukherjee</b></sub></p>
