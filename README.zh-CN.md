<p align="center">
  <img src="docs/banner.png" alt="DropDial：拖动文件，按下 Shift，放到转盘上" width="100%">
</p>

<p align="center">
  <b>一款免费、开源、拖一拖就能用的文件转换工具。</b><br>
  拖动任意文件，按下 <kbd>Shift</kbd>，把它放到在光标处弹出的玻璃转盘的某一格上即可。
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><b>下载</b></a> ·
  <a href="#安装">安装</a> ·
  <a href="#首次启动">首次启动</a> ·
  <a href="#支持的格式">支持的格式</a> ·
  <a href="#命令行">命令行</a> ·
  <a href="#开发">开发</a>
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml"><img src="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><img src="https://img.shields.io/github/v/release/prithwirajmukherjee15-cmd/DropDial?color=d8ad62&label=release" alt="最新版本"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases"><img src="https://img.shields.io/github/downloads/prithwirajmukherjee15-cmd/DropDial/total?color=a87a34" alt="下载量"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-2b2f3a" alt="Windows 10 | 11">
  <img src="https://img.shields.io/badge/macOS-11%2B-2b2f3a" alt="macOS 11+">
  <img src="https://img.shields.io/badge/Linux-x64-2b2f3a" alt="Linux x64">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-e3be7a" alt="MIT 许可证"></a>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.hi.md">हिन्दी</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a> · <a href="README.pt-BR.md">Português (Brasil)</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <b>简体中文</b> · <a href="README.ru.md">Русский</a> · <a href="README.ar.md">العربية</a></p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg"><img src="docs/btn-mac-arm.svg" alt="下载 macOS 版（Apple 芯片）" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg"><img src="docs/btn-mac-intel.svg" alt="下载 macOS 版（Intel）" height="56"></a>
  <br>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe"><img src="docs/btn-win.svg" alt="下载 Windows 版" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb"><img src="docs/btn-linux.svg" alt="下载 Linux 版" height="56"></a>
</p>

> [!IMPORTANT]
> **第一次打开 DropDial？** 由于应用暂时还没有代码签名，Windows 和 macOS 会显示一次安全警告。应用是安全的，10 秒钟就能过掉这个警告。**[查看首次启动 ↓](#首次启动)**

<table>
  <tr>
    <td width="33%" valign="top"><b>就在光标旁边</b><br>不用打开任何应用窗口。转盘就出现在你当前的位置，只显示适合所拖文件的格式。</td>
    <td width="33%" valign="top"><b>140 多种文件类型，无需其他软件</b><br>图片、相机 RAW、PDF、Word、Excel、电子书、视频、音频、字幕、压缩包、字体、3D 模型和地图文件，都不需要安装 Office 或其他任何软件。</td>
    <td width="33%" valign="top"><b>一切留在你的电脑上</b><br>不会上传任何东西。DropDial 离线工作，把结果保存在原文件旁边，绝不覆盖原文件。</td>
  </tr>
</table>

## 实际效果

<p align="center">
  <img src="docs/demo.gif" alt="拖动一张照片，按下 Shift，放到 Compress 上" width="760">
</p>

## 安装

从 [Releases](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest) 下载。

- **macOS 11+**：打开 `.dmg`（[Apple 芯片](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg) · [Intel](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg)），把 DropDial 拖到“应用程序”文件夹。也可以把下面这行粘贴到“终端”：它会自动选择合适的版本，安装时不会弹出安全提示，再次运行即可更新：
  ```bash
  curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/DropDial/main/install-mac.sh | bash
  ```
- **Windows 10/11**：运行 [`DropDial-Setup.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe)（为当前用户安装，无需管理员权限；会添加右键菜单、*发送到* 以及开机自启），或者使用便携版 [`DropDial.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial.exe)。
- **Linux x64**（Debian 12+、Ubuntu 23.04+、Mint 等）：`sudo apt install ./DropDial-linux-amd64.deb`（[下载](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb)）。Shift 手势需要 X11；在 Wayland 下，请使用 Home 的拖放区，或右键 → **打开方式 → DropDial**。
- **Linux ARM64**（Ubuntu 24.04+、Debian 13+、Raspberry Pi OS 13 64 位等）：`sudo apt install ./DropDial-linux-arm64.deb`（[下载](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-arm64.deb)）。

DropDial 常驻在菜单栏 / 系统托盘里，有新版本时会提醒你。

## 首次启动

DropDial 目前还没有代码签名（签名证书每年都要花钱），所以 Windows 和 macOS **只在第一次** 会显示警告。DropDial 的全部代码都公开在这个仓库里，下载文件由 GitHub 根据这些代码自动构建。

### Windows：“Windows 已保护你的电脑”

第一次运行 `DropDial-Setup.exe` 或 `DropDial.exe` 时，SmartScreen 可能会显示这个提示。

1. 点击 **更多信息**。
2. 点击 **仍要运行**。

就这样。Windows 不会再问了。

### Mac：“Apple 无法验证 DropDial……”

如果你是用上面的终端命令安装的，可以跳过这一步：不会出现警告。如果用 **.dmg** 安装，macOS 会提示 *“Apple 无法验证‘DropDial’是否包含可能危害 Mac 安全或泄漏隐私的恶意软件。”* 凡是没有经过 Apple 付费公证的应用，都会显示这条提示。打开方法：

1. 从“应用程序”中打开一次 **DropDial**，在警告中点击 **完成**。
2. 打开 **苹果菜单 → 系统设置 → 隐私与安全性**。向下滚动到 **已阻止“DropDial”以保护 Mac**，点击 **仍要打开**。
3. 输入密码，再点一次 **仍要打开** 确认。

完成。macOS 会记住这个选择，所以只需要做一次。

<details>
<summary>更喜欢用终端？一条命令就能搞定</summary>

```bash
xattr -dr com.apple.quarantine /Applications/DropDial.app
```

然后像平常一样打开 DropDial 即可。
</details>

> [!NOTE]
> 在 macOS 15（Sequoia）及更高版本中，以前的 **右键 → 打开** 方法已经无法绕过这个警告。请按照上面的步骤操作。

### Mac（可选）：录屏

DropDial 可能会请求 **录屏** 权限。允许后，玻璃转盘会透出它后面的窗口。如果不允许，所有功能照常可用，玻璃里显示的会是你的桌面墙纸。**任何内容都不会被录制、保存或发送到任何地方。** 你可以随时在 **系统设置 → 隐私与安全性 → 录屏与系统录音** 中更改。

## 功能

- **光标处的转盘**：拖动文件，按下 <kbd>Shift</kbd>，放到某个格式上。只会显示适合这些文件的格式。
- **不止一面**：再按一下 <kbd>Shift</kbd>、按 <kbd>Tab</kbd> 或滚动鼠标滚轮，即可翻到 **More formats**、**Tools** 和 **Recipes**。
- **直接从浏览器拖**：从 Chrome、Edge、Firefox 或 Safari 中拖出图片、文件链接或下载项。DropDial 会先把它保存到“下载”文件夹，再进行转换。
- **Home**：点击托盘 / 菜单栏图标，打开一个拖放区（不用按 Shift）以及带预览的最近结果。可以打开、在文件夹中显示、再次转换或撤销。
- **按文件类型提供的工具**：图片压缩、缩放、裁剪、编辑、标注、遮盖敏感信息、加水印、清除元数据；PDF 拆分、合并、旋转、加页码、加密、解锁、压缩；视频压缩、静音、旋转；音频响度标准化；字幕清理；字体子集化；3D 模型修复；GPS 轨迹的行程统计；等等。
- **Recipes**：把多个步骤串成一个格子（“Web-ready”、“Email size”、“Private”……），也可以自己创建。
- **监视文件夹**：自动转换放进来的每一个文件。
- **一次处理多个文件**，用 ZIP 格子把一堆文件或一个文件夹打包，用 **History** 查找或撤销任何操作。
- **其他使用方式**：右键菜单、*发送到*（Windows）、Home 的拖放区，以及 [`dropdial` 命令](#命令行)。
- **你的风格**：液态玻璃转盘，强调色随你选（Champagne、Rose、Ocean、Emerald、Violet、Silver）。

## 截图

<table>
  <tr>
    <td width="58%"><img src="docs/screen-home.png" alt="Home：拖放区和带预览的最近结果"></td>
    <td width="42%"><img src="docs/screen-dial.png" alt="电子表格的转盘：XLSX、PDF、JSON、HTML、DOCX、MD"></td>
  </tr>
  <tr>
    <td align="center"><sub>Home：拖放区和最近结果（3D 渲染图、GPS 地图、字体样张……）</sub></td>
    <td align="center"><sub>电子表格的转盘；翻面可以看到 More formats 和 Tools</sub></td>
  </tr>
</table>

## 支持的格式

| 源格式 | 目标格式 |
|---|---|
| **图片**：JPG、PNG、WEBP、HEIC、AVIF、TIFF、GIF、BMP、ICO | 互相转换、PDF、SVG（描摹）、ICNS、TGA、QOI |
| **专业图片**：相机 RAW（CR2、CR3、NEF、ARW、DNG、RAF、ORF、RW2……）、PSD、TGA、QOI、JPEG 2000、DDS、ICNS、PPM…… | JPG、PNG、TIFF（RAW 为 16 位）、WEBP、AVIF、HEIC、PDF |
| **矢量图**：SVG | PDF（保持矢量）、PNG、JPG、WEBP、ICO |
| **PDF** | JPG、PNG、DOCX、TXT；合并、拆分、旋转、压缩、加页码、加水印、加密、解锁、提取图片 |
| **文档**：DOCX、TXT、Markdown、HTML、保存的网页（MHTML）、reStructuredText | PDF、DOCX、HTML、Markdown、TXT |
| **电子邮件**：EML | PDF、DOCX、HTML、TXT；保存附件 |
| **电子表格**：XLSX、XLSM、XLS、ODS、CSV、TSV | XLSX、ODS、CSV、TSV、JSON、HTML、PDF、DOCX、Markdown；联系人 CSV → VCF；合并、拆分工作表 |
| **数据**：JSON、JSON Lines、YAML、TOML、XML、plist、vCard | 互相转换、CSV、XLSX、PDF |
| **电子书**：EPUB、MOBI、FB2、CBZ、XPS | PDF、DOCX、TXT |
| **视频**：MP4、MOV、MKV、WEBM、AVI、WMV、FLV、M4V、MPEG、3GP | MP4、WEBM、MOV、GIF、MP3；压缩、静音、旋转、截取静帧（iPhone HDR 会做色调映射） |
| **音频**：MP3、M4A、AAC、WAV、FLAC、OGG、OPUS、WMA、AIFF | MP3、M4A、WAV、FLAC、OGG；响度标准化、裁掉静音、压缩 |
| **字幕**：SRT、WebVTT、ASS/SSA、SBV、MicroDVD、SAMI、LRC、TTML | 以 UTF-8 互相转换、TXT；清理字幕、修正 25 / 23.976 fps 时间轴 |
| **压缩包**：ZIP、7Z、TAR、TAR.GZ、TAR.BZ2、TAR.XZ、GZ、BZ2、XZ | 解压、ZIP、7Z、TAR.GZ；任意文件或文件夹 → 一个 ZIP |
| **字体**：TTF、OTF、WOFF、WOFF2、TTC | 互相转换、PNG / PDF 样张；拉丁字符子集、网页字体包 |
| **3D 模型**：STL、OBJ、PLY、GLB、glTF、OFF、3MF | 互相转换、PNG 预览；居中并落地、修复、减面 |
| **地图数据**：GPX、KML、KMZ、GeoJSON、Shapefile | 互相转换、CSV、PNG 地图；行程统计、反转、简化 |

一切开箱即用：下载包里已包含所有引擎（视频和音频使用 FFmpeg）。
运行 `dropdial formats` 可以列出你这份安装支持的完整格式列表。

## 命令行

`dropdial` 命令使用与应用相同的引擎和配方（从源码运行：`python -m dropdial`）。

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

加上 `--json` 可以得到便于程序读取的输出；只要有任何文件失败，退出码就是 1。

## 开发

Python 3.12，支持 Windows、macOS 或 Linux：

```bash
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
pip install -r requirements.txt pytest
python -m dropdial
python -m pytest -q          # on Linux without a display: QT_QPA_PLATFORM=offscreen
```

[架构](docs/ARCHITECTURE.md) · [添加文件格式](docs/ADDING-A-CONVERTER.md) · [参与贡献](CONTRIBUTING.md) · [更新日志](CHANGELOG.md) · [安全](SECURITY.md)

欢迎提交 Pull Request。如果 DropDial 帮你省了几次点击，点个 ⭐ 能让更多人发现它。

## 代码签名

DropDial 由 **Prithwiraj Mukherjee** 开发和发布。Windows 和 macOS 版的下载文件目前还没有代码签名或公证，所以系统会在第一次运行时发出警告（参见 [首次启动](#首次启动)）。每个下载文件都由 GitHub Actions 根据本仓库的源码构建，没有任何手工构建的内容。

### 隐私

DropDial 在你自己的电脑上转换文件，从不上传。它不收集使用数据，也不发送遥测信息。它只在以下情况连接互联网：

- 向 GitHub（`api.github.com`）查询是否有新版本：启动后不久查询一次，之后每隔几小时查询一次。可以在 Settings 中关闭（“Check for updates automatically”）。
- 下载你从浏览器拖到转盘上的文件。
- 你点击链接时，在浏览器中打开它。

## 许可证

MIT，© 2026 Prithwiraj Mukherjee。随附的第三方组件保留各自的许可证，详见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。

<p align="center">
  <a href="https://star-history.com/#prithwirajmukherjee15-cmd/DropDial&Date"><img src="https://api.star-history.com/svg?repos=prithwirajmukherjee15-cmd/DropDial&type=Date" alt="Star 历史" width="600"></a>
</p>

<p align="center"><sub>作者：<b>Prithwiraj Mukherjee</b></sub></p>
