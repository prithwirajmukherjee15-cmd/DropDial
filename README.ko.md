<p align="center">
  <img src="docs/banner.png" alt="DropDial: 파일을 끌고 Shift를 누른 다음 다이얼에 놓으세요" width="100%">
</p>

<p align="center">
  <b>끌어다 놓기만 하면 되는 무료 오픈 소스 파일 변환기.</b><br>
  아무 파일이나 끌고 <kbd>Shift</kbd>를 누른 다음, 커서 위치에 열리는 유리 다이얼의 칸에 놓으세요.
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><b>다운로드</b></a> ·
  <a href="#설치">설치</a> ·
  <a href="#처음-실행하기">처음 실행하기</a> ·
  <a href="#지원-형식">지원 형식</a> ·
  <a href="#명령줄">명령줄</a> ·
  <a href="#개발">개발</a>
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml"><img src="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><img src="https://img.shields.io/github/v/release/prithwirajmukherjee15-cmd/DropDial?color=d8ad62&label=release" alt="최신 릴리스"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases"><img src="https://img.shields.io/github/downloads/prithwirajmukherjee15-cmd/DropDial/total?color=a87a34" alt="다운로드 수"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-2b2f3a" alt="Windows 10 | 11">
  <img src="https://img.shields.io/badge/macOS-11%2B-2b2f3a" alt="macOS 11+">
  <img src="https://img.shields.io/badge/Linux-x64-2b2f3a" alt="Linux x64">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-e3be7a" alt="MIT 라이선스"></a>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.hi.md">हिन्दी</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a> · <a href="README.pt-BR.md">Português (Brasil)</a> · <a href="README.ja.md">日本語</a> · <b>한국어</b> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ru.md">Русский</a> · <a href="README.ar.md">العربية</a></p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg"><img src="docs/btn-mac-arm.svg" alt="macOS용 다운로드 (Apple Silicon)" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg"><img src="docs/btn-mac-intel.svg" alt="macOS용 다운로드 (Intel)" height="56"></a>
  <br>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe"><img src="docs/btn-win.svg" alt="Windows용 다운로드" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb"><img src="docs/btn-linux.svg" alt="Linux용 다운로드" height="56"></a>
</p>

> [!IMPORTANT]
> **DropDial을 처음 여시나요?** 앱에 아직 코드 서명이 없어서 Windows와 macOS가 처음 한 번 보안 경고를 띄웁니다. 앱은 안전하고, 경고를 넘기는 데는 10초면 충분합니다. **[처음 실행하기 보기 ↓](#처음-실행하기)**

<table>
  <tr>
    <td width="33%" valign="top"><b>커서 바로 옆에서</b><br>앱 창을 열 필요가 없습니다. 다이얼이 지금 있는 자리에 나타나고, 끌고 있는 파일에 맞는 형식만 보여 줍니다.</td>
    <td width="33%" valign="top"><b>140가지 이상의 파일 형식, 다른 프로그램 필요 없음</b><br>이미지, 카메라 RAW, PDF, Word, Excel, 전자책, 동영상, 오디오, 자막, 압축 파일, 글꼴, 3D 모델, 지도 파일까지 Office나 다른 프로그램 없이 바로 됩니다.</td>
    <td width="33%" valign="top"><b>내 컴퓨터 안에서만</b><br>아무것도 업로드하지 않습니다. DropDial은 오프라인에서 동작하고, 결과물은 원본 옆에 저장합니다. 원본을 덮어쓰지 않습니다.</td>
  </tr>
</table>

## 실제로 써 보면

<p align="center">
  <img src="docs/demo.gif" alt="사진을 끌고 Shift를 누른 다음 Compress에 놓는 모습" width="760">
</p>

## 설치

[Releases](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest)에서 다운로드하세요.

- **macOS 11 이상**: `.dmg`([Apple Silicon](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg) · [Intel](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg))를 열고 DropDial을 응용 프로그램 폴더로 끌어 놓으세요. 또는 아래 명령을 터미널에 붙여 넣으세요. 맞는 빌드를 골라 보안 경고 없이 설치하고, 다시 실행하면 업데이트도 해 줍니다:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/DropDial/main/install-mac.sh | bash
  ```
- **Windows 10/11**: [`DropDial-Setup.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe)를 실행하세요(현재 사용자에게만 설치되며 관리자 권한이 필요 없습니다. 오른쪽 클릭 메뉴, *보내기*, Windows 시작 시 자동 실행이 추가됩니다). 포터블 버전 [`DropDial.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial.exe)도 있습니다.
- **Linux x64** (Debian 12 이상, Ubuntu 23.04 이상, Mint 등): `sudo apt install ./DropDial-linux-amd64.deb` ([다운로드](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb)). Shift 제스처는 X11이 필요합니다. Wayland에서는 Home의 드롭 영역을 쓰거나 오른쪽 클릭 → **다른 프로그램으로 열기 → DropDial**을 사용하세요.
- **Linux ARM64** (Ubuntu 24.04 이상, Debian 13 이상, Raspberry Pi OS 13 64비트 등): `sudo apt install ./DropDial-linux-arm64.deb` ([다운로드](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-arm64.deb)).

DropDial은 메뉴 막대 / 시스템 트레이에 머물며, 새 버전이 나오면 알려 줍니다.

## 처음 실행하기

DropDial은 아직 코드 서명이 되어 있지 않습니다(서명 인증서는 매년 비용이 듭니다). 그래서 Windows와 macOS가 **처음 한 번만** 경고를 표시합니다. DropDial의 코드는 모두 이 저장소에 공개되어 있고, 다운로드 파일은 GitHub가 이 코드로 자동 빌드합니다.

### Windows: “Windows의 PC 보호”

`DropDial-Setup.exe`나 `DropDial.exe`를 처음 실행할 때 SmartScreen이 이 화면을 띄울 수 있습니다.

1. **추가 정보**를 클릭합니다.
2. **실행**을 클릭합니다.

끝입니다. Windows가 다시 묻지 않습니다.

### Mac: “Apple은 DropDial을 확인할 수 없습니다…”

위의 터미널 명령으로 설치했다면 이 단계는 건너뛰어도 됩니다. 경고가 뜨지 않습니다. **.dmg**로 설치하면 macOS가 *“Apple은 ‘DropDial’에 Mac을 손상시키거나 개인정보를 침해할 수 있는 악성 코드가 없음을 확인할 수 없습니다.”*라고 표시합니다. Apple의 유료 공증을 거치지 않은 앱이라면 어떤 앱이든 이렇게 나옵니다. 여는 방법:

1. 응용 프로그램 폴더에서 **DropDial**을 한 번 열고, 경고에서 **완료**를 클릭합니다.
2. **Apple 메뉴 → 시스템 설정 → 개인정보 보호 및 보안**을 엽니다. 아래로 스크롤해서 **Mac을 보호하기 위해 ‘DropDial’이(가) 차단되었습니다.** 항목을 찾아 **그래도 열기**를 클릭합니다.
3. 암호를 입력하고 **그래도 열기**를 한 번 더 클릭해 확인합니다.

완료입니다. macOS가 이 선택을 기억하므로 한 번만 하면 됩니다.

<details>
<summary>터미널이 더 편하신가요? 명령 하나로 똑같이 할 수 있습니다</summary>

```bash
xattr -dr com.apple.quarantine /Applications/DropDial.app
```

그다음 평소처럼 DropDial을 여세요.
</details>

> [!NOTE]
> macOS 15(Sequoia) 이상에서는 예전의 **오른쪽 클릭 → 열기** 방법으로 이 경고를 넘길 수 없습니다. 위 단계를 따라 주세요.

### Mac, 선택 사항: 화면 기록

DropDial이 **화면 기록** 권한을 요청할 수 있습니다. 허용하면 유리 다이얼 너머로 뒤쪽 창들이 비쳐 보입니다. 허용하지 않아도 모든 기능이 그대로 동작하고, 유리에는 대신 배경 화면이 보입니다. **어떤 것도 녹화되거나 저장되거나 어딘가로 전송되지 않습니다.** 이 설정은 언제든지 **시스템 설정 → 개인정보 보호 및 보안 → 화면 및 시스템 오디오 녹음**에서 바꿀 수 있습니다.

## 기능

- **커서 위치에 다이얼**: 파일을 끌고 <kbd>Shift</kbd>를 누른 다음 원하는 형식에 놓으세요. 파일에 맞는 형식만 나타납니다.
- **다이얼의 여러 면**: <kbd>Shift</kbd>를 한 번 더 누르거나, <kbd>Tab</kbd>을 누르거나, 마우스 휠을 돌리면 **More formats**, **Tools**, **Recipes**로 넘어갑니다.
- **브라우저에서 바로**: Chrome, Edge, Firefox, Safari에서 이미지, 파일 링크, 다운로드 항목을 끌어 오세요. DropDial이 다운로드 폴더에 저장한 다음 변환합니다.
- **Home**: 트레이 / 메뉴 막대 아이콘을 클릭하면 드롭 영역(Shift 필요 없음)과 미리 보기가 있는 최근 결과가 열립니다. 열기, 폴더에서 보기, 다시 변환, 실행 취소가 가능합니다.
- **파일 종류별 도구**: 이미지 압축·크기 조절·자르기·편집·주석·가리기·워터마크·메타데이터 제거, PDF 분할·병합·회전·쪽 번호·암호 설정·잠금 해제·압축, 동영상 압축·음소거·회전, 오디오 음량 정규화, 자막 정리, 글꼴 서브셋, 3D 모델 복구, GPS 트랙 주행 통계 등.
- **Recipes**: 여러 단계를 하나의 칸으로 묶을 수 있습니다("Web-ready", "Email size", "Private" 등). 직접 만들 수도 있습니다.
- **감시 폴더**: 폴더에 들어오는 파일을 모두 자동으로 변환합니다.
- **여러 파일을 한 번에**: 파일 더미나 폴더를 묶는 ZIP 칸도 있고, **History**에서 무엇이든 찾거나 되돌릴 수 있습니다.
- **다른 사용 방법**: 오른쪽 클릭 메뉴, *보내기*(Windows), Home의 드롭 영역, 그리고 [`dropdial` 명령](#명령줄).
- **나만의 스타일**: 리퀴드 글래스 다이얼에 원하는 강조 색상(Champagne, Rose, Ocean, Emerald, Violet, Silver)을 고를 수 있습니다.

## 스크린샷

<table>
  <tr>
    <td width="58%"><img src="docs/screen-home.png" alt="Home: 드롭 영역과 미리 보기가 있는 최근 결과"></td>
    <td width="42%"><img src="docs/screen-dial.png" alt="스프레드시트용 다이얼: XLSX, PDF, JSON, HTML, DOCX, MD"></td>
  </tr>
  <tr>
    <td align="center"><sub>Home: 드롭 영역과 최근 결과(3D 렌더링, GPS 지도, 글꼴 견본 등)</sub></td>
    <td align="center"><sub>스프레드시트용 다이얼. 뒤집으면 More formats와 Tools</sub></td>
  </tr>
</table>

## 지원 형식

| 원본 | 변환 결과 |
|---|---|
| **이미지**: JPG, PNG, WEBP, HEIC, AVIF, TIFF, GIF, BMP, ICO | 서로 변환, PDF, SVG(트레이스), ICNS, TGA, QOI |
| **전문가용 이미지**: 카메라 RAW(CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2…), PSD, TGA, QOI, JPEG 2000, DDS, ICNS, PPM… | JPG, PNG, TIFF(RAW는 16비트), WEBP, AVIF, HEIC, PDF |
| **벡터**: SVG | PDF(벡터 유지), PNG, JPG, WEBP, ICO |
| **PDF** | JPG, PNG, DOCX, TXT; 병합, 분할, 회전, 압축, 쪽 번호, 워터마크, 암호 설정, 잠금 해제, 이미지 추출 |
| **문서**: DOCX, TXT, Markdown, HTML, 저장한 웹 페이지(MHTML), reStructuredText | PDF, DOCX, HTML, Markdown, TXT |
| **이메일**: EML | PDF, DOCX, HTML, TXT; 첨부 파일 저장 |
| **스프레드시트**: XLSX, XLSM, XLS, ODS, CSV, TSV | XLSX, ODS, CSV, TSV, JSON, HTML, PDF, DOCX, Markdown; 연락처 CSV → VCF; 시트 합치기, 나누기 |
| **데이터**: JSON, JSON Lines, YAML, TOML, XML, plist, vCard | 서로 변환, CSV, XLSX, PDF |
| **전자책**: EPUB, MOBI, FB2, CBZ, XPS | PDF, DOCX, TXT |
| **동영상**: MP4, MOV, MKV, WEBM, AVI, WMV, FLV, M4V, MPEG, 3GP | MP4, WEBM, MOV, GIF, MP3; 압축, 음소거, 회전, 정지 화면 추출(iPhone HDR은 톤 매핑) |
| **오디오**: MP3, M4A, AAC, WAV, FLAC, OGG, OPUS, WMA, AIFF | MP3, M4A, WAV, FLAC, OGG; 음량 정규화, 무음 구간 자르기, 압축 |
| **자막**: SRT, WebVTT, ASS/SSA, SBV, MicroDVD, SAMI, LRC, TTML | UTF-8로 서로 변환, TXT; 자막 정리, 25 / 23.976fps 싱크 보정 |
| **압축 파일**: ZIP, 7Z, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, GZ, BZ2, XZ | 압축 풀기, ZIP, 7Z, TAR.GZ; 아무 파일이나 폴더 → ZIP 하나 |
| **글꼴**: TTF, OTF, WOFF, WOFF2, TTC | 서로 변환, PNG / PDF 견본; 라틴 문자 서브셋, 웹 폰트 키트 |
| **3D 모델**: STL, OBJ, PLY, GLB, glTF, OFF, 3MF | 서로 변환, PNG 미리 보기; 가운데 정렬 및 바닥에 맞추기, 복구, 폴리곤 줄이기 |
| **지도 데이터**: GPX, KML, KMZ, GeoJSON, Shapefile | 서로 변환, CSV, PNG 지도; 주행 통계, 경로 뒤집기, 단순화 |

설치하자마자 모든 기능을 쓸 수 있습니다. 다운로드에는 모든 엔진(동영상과 오디오용 FFmpeg 포함)이 들어 있습니다.
`dropdial formats`를 실행하면 내 환경에서 지원하는 전체 목록이 나옵니다.

## 명령줄

`dropdial` 명령은 앱과 같은 엔진과 레시피를 사용합니다(소스에서 실행할 때: `python -m dropdial`).

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

`--json`을 붙이면 기계가 읽기 쉬운 형식으로 출력합니다. 실패한 파일이 하나라도 있으면 종료 코드는 1입니다.

## 개발

Python 3.12, Windows·macOS·Linux에서:

```bash
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
pip install -r requirements.txt pytest
python -m dropdial
python -m pytest -q          # on Linux without a display: QT_QPA_PLATFORM=offscreen
```

[아키텍처](docs/ARCHITECTURE.md) · [파일 형식 추가하기](docs/ADDING-A-CONVERTER.md) · [기여하기](CONTRIBUTING.md) · [변경 내역](CHANGELOG.md) · [보안](SECURITY.md)

풀 리퀘스트는 언제나 환영합니다. DropDial 덕분에 클릭 몇 번을 아꼈다면, ⭐ 하나가 다른 사람들이 이 프로젝트를 찾는 데 도움이 됩니다.

## 코드 서명

DropDial은 **Prithwiraj Mukherjee**가 개발하고 배포합니다. Windows용과 macOS용 다운로드는 아직 코드 서명이나 공증을 받지 않았기 때문에 처음 실행할 때 시스템이 경고합니다([처음 실행하기](#처음-실행하기) 참고). 모든 다운로드 파일은 GitHub Actions가 이 저장소의 소스로 빌드하며, 손으로 빌드하는 것은 없습니다.

### 개인정보 보호

DropDial은 내 컴퓨터에서 파일을 변환하며 절대 업로드하지 않습니다. 사용 데이터를 수집하지 않고 원격 측정 데이터도 보내지 않습니다. 인터넷에 연결하는 경우는 다음뿐입니다:

- 새 릴리스가 있는지 GitHub(`api.github.com`)에 확인할 때. 시작 직후, 그리고 그 후 몇 시간마다 확인합니다. Settings의 "Check for updates automatically"에서 끌 수 있습니다.
- 웹 브라우저에서 다이얼로 끌어 온 파일을 다운로드할 때.
- 링크를 클릭해 웹 브라우저에서 열 때.

## 라이선스

MIT, © 2026 Prithwiraj Mukherjee. 함께 포함된 서드파티 구성 요소는 각자의 라이선스를 따르며, 목록은 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)에 있습니다.

<p align="center">
  <a href="https://star-history.com/#prithwirajmukherjee15-cmd/DropDial&Date"><img src="https://api.star-history.com/svg?repos=prithwirajmukherjee15-cmd/DropDial&type=Date" alt="스타 추이" width="600"></a>
</p>

<p align="center"><sub>만든 사람: <b>Prithwiraj Mukherjee</b></sub></p>
