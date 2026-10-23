<p align="center">
  <img src="docs/banner.png" alt="DropDial：ファイルをドラッグして Shift を押し、ダイヤルにドロップ" width="100%">
</p>

<p align="center">
  <b>ドラッグするだけで使える、無料のオープンソースのファイル変換ツール。</b><br>
  好きなファイルをドラッグして <kbd>Shift</kbd> を押し、カーソルの位置に開くガラスのダイヤルの項目にドロップするだけです。
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><b>ダウンロード</b></a> ·
  <a href="#インストール">インストール</a> ·
  <a href="#初回起動">初回起動</a> ·
  <a href="#対応フォーマット">対応フォーマット</a> ·
  <a href="#コマンドライン">コマンドライン</a> ·
  <a href="#開発">開発</a>
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml"><img src="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><img src="https://img.shields.io/github/v/release/prithwirajmukherjee15-cmd/DropDial?color=d8ad62&label=release" alt="最新リリース"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases"><img src="https://img.shields.io/github/downloads/prithwirajmukherjee15-cmd/DropDial/total?color=a87a34" alt="ダウンロード数"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-2b2f3a" alt="Windows 10 | 11">
  <img src="https://img.shields.io/badge/macOS-11%2B-2b2f3a" alt="macOS 11+">
  <img src="https://img.shields.io/badge/Linux-x64-2b2f3a" alt="Linux x64">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-e3be7a" alt="MIT ライセンス"></a>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.hi.md">हिन्दी</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a> · <a href="README.pt-BR.md">Português (Brasil)</a> · <b>日本語</b> · <a href="README.ko.md">한국어</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ru.md">Русский</a> · <a href="README.ar.md">العربية</a></p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg"><img src="docs/btn-mac-arm.svg" alt="macOS 版をダウンロード（Apple シリコン）" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg"><img src="docs/btn-mac-intel.svg" alt="macOS 版をダウンロード（Intel）" height="56"></a>
  <br>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe"><img src="docs/btn-win.svg" alt="Windows 版をダウンロード" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb"><img src="docs/btn-linux.svg" alt="Linux 版をダウンロード" height="56"></a>
</p>

> [!IMPORTANT]
> **はじめて DropDial を開きますか？** アプリにまだコード署名がないため、Windows と macOS では最初の一度だけセキュリティ警告が表示されます。アプリは安全で、警告は 10 秒ほどで通過できます。**[初回起動を見る ↓](#初回起動)**

<table>
  <tr>
    <td width="33%" valign="top"><b>カーソルのすぐそばに</b><br>アプリのウィンドウを開く必要はありません。ダイヤルは今いる場所に現れ、ドラッグしたファイルに合うフォーマットだけを表示します。</td>
    <td width="33%" valign="top"><b>140 種類以上のファイル、ほかのソフトは不要</b><br>画像、カメラの RAW、PDF、Word、Excel、電子書籍、動画、音声、字幕、アーカイブ、フォント、3D モデル、地図ファイルを、Office などをインストールせずに扱えます。</td>
    <td width="33%" valign="top"><b>すべてあなたのコンピュータの中で</b><br>何もアップロードされません。DropDial はオフラインで動作し、変換結果は元のファイルの隣に保存します。上書きはしません。</td>
  </tr>
</table>

## 動作イメージ

<p align="center">
  <img src="docs/demo.gif" alt="写真をドラッグして Shift を押し、Compress にドロップする様子" width="760">
</p>

## インストール

[Releases](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest) からダウンロードしてください。

- **macOS 11 以降**：`.dmg`（[Apple シリコン](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg) · [Intel](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg)）を開き、DropDial を「アプリケーション」にドラッグします。または、次の 1 行をターミナルに貼り付けてください。適切なビルドを選んでセキュリティ警告なしでインストールし、もう一度実行すればアップデートもできます：
  ```bash
  curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/DropDial/main/install-mac.sh | bash
  ```
- **Windows 10/11**：[`DropDial-Setup.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe) を実行します（ユーザー単位でインストールされ、管理者権限は不要。右クリックメニュー、*送る*、Windows 起動時の自動起動を追加します）。ポータブル版の [`DropDial.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial.exe) も使えます。
- **Linux x64**（Debian 12 以降、Ubuntu 23.04 以降、Mint など）：`sudo apt install ./DropDial-linux-amd64.deb`（[ダウンロード](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb)）。Shift ジェスチャーには X11 が必要です。Wayland では Home のドロップゾーンか、右クリック → **アプリケーションで開く → DropDial** を使ってください。
- **Linux ARM64**（Ubuntu 24.04 以降、Debian 13 以降、Raspberry Pi OS 13 64 ビット版など）：`sudo apt install ./DropDial-linux-arm64.deb`（[ダウンロード](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-arm64.deb)）。

DropDial はメニューバー / システムトレイに常駐し、新しいバージョンが出るとお知らせします。

## 初回起動

DropDial はまだコード署名されていません（署名用の証明書には毎年費用がかかるためです）。そのため Windows と macOS では **最初の一度だけ** 警告が表示されます。DropDial のコードはすべてこのリポジトリで公開されており、ダウンロードファイルは GitHub がそこから自動でビルドしています。

### Windows：「Windows によって PC が保護されました」

`DropDial-Setup.exe` または `DropDial.exe` を初めて実行したときに、SmartScreen がこの画面を表示することがあります。

1. **詳細情報** をクリックします。
2. **実行** をクリックします。

これで完了です。Windows が再び確認してくることはありません。

### Mac：「Apple は DropDial を検証できませんでした…」

上のターミナルのコマンドでインストールした場合、この手順は不要です。警告は出ません。**.dmg** の場合、macOS は *「“DropDial”は、Mac に損害を与えたり、プライバシーを侵害したりする可能性のあるマルウェアが含まれていないことを Apple が検証できませんでした。」* と表示します。これは Apple の有料の公証（ノータリゼーション）を受けていないアプリすべてに表示されるものです。開くには：

1. 「アプリケーション」から **DropDial** を一度開き、警告で **完了** をクリックします。
2. **アップルメニュー → システム設定 → プライバシーとセキュリティ** を開きます。下にスクロールして **Mac を保護するために“DropDial”がブロックされました。** を見つけ、**このまま開く** をクリックします。
3. パスワードを入力し、もう一度 **このまま開く** をクリックして確定します。

完了です。macOS はこの選択を記憶するので、作業は一度だけで済みます。

<details>
<summary>ターミナル派ですか？ 1 つのコマンドで同じことができます</summary>

```bash
xattr -dr com.apple.quarantine /Applications/DropDial.app
```

その後は普段どおり DropDial を開いてください。
</details>

> [!NOTE]
> macOS 15（Sequoia）以降では、以前の **右クリック → 開く** という方法ではこの警告を回避できなくなりました。上の手順を使ってください。

### Mac（任意）：画面収録

DropDial が **画面収録** の許可を求めることがあります。許可すると、ガラスのダイヤル越しに背後のウインドウが透けて見えます。許可しなくてもすべての機能は使え、ガラスには代わりに壁紙が映ります。**画面が録画・保存されたり、どこかへ送信されたりすることは一切ありません。** この設定は **システム設定 → プライバシーとセキュリティ → 画面とシステムオーディオ収録** でいつでも変更できます。

## 機能

- **カーソルの位置にダイヤル**：ファイルをドラッグして <kbd>Shift</kbd> を押し、フォーマットにドロップ。そのファイルに合うフォーマットだけが表示されます。
- **ダイヤルは裏返せる**：もう一度 <kbd>Shift</kbd> をタップするか、<kbd>Tab</kbd> を押すか、マウスホイールを回すと、**More formats**、**Tools**、**Recipes** に切り替わります。
- **ブラウザから直接**：Chrome、Edge、Firefox、Safari から画像、ファイルへのリンク、ダウンロードをドラッグ。DropDial が「ダウンロード」に保存してから変換します。
- **Home**：トレイ / メニューバーのアイコンをクリックすると、ドロップゾーン（Shift 不要）と、プレビュー付きの最近の結果が表示されます。開く、フォルダで表示、もう一度変換、元に戻す、がここからできます。
- **ファイルの種類ごとのツール**：画像の圧縮・リサイズ・切り抜き・編集・注釈・墨消し・透かし・メタデータ削除、PDF の分割・結合・回転・ページ番号・保護・ロック解除・圧縮、動画の圧縮・ミュート・回転、音声のノーマライズ、字幕のクリーンアップ、フォントのサブセット化、3D モデルの修復、GPS トラックの走行統計など。
- **Recipes**：複数の処理を 1 つの項目にまとめられます（「Web-ready」「Email size」「Private」など）。自分で作ることもできます。
- **監視フォルダ**：フォルダに入ったファイルをすべて自動で変換します。
- **複数ファイルを一度に**：たくさんのファイルやフォルダをまとめる ZIP 項目もあり、**History** で何でも見つけたり元に戻したりできます。
- **ほかの使い方**：右クリックメニュー、*送る*（Windows）、Home のドロップゾーン、そして [`dropdial` コマンド](#コマンドライン)。
- **好みの見た目に**：リキッドグラスのダイヤルに、好きなアクセントカラー（Champagne、Rose、Ocean、Emerald、Violet、Silver）を選べます。

## スクリーンショット

<table>
  <tr>
    <td width="58%"><img src="docs/screen-home.png" alt="Home：ドロップゾーンとプレビュー付きの最近の結果"></td>
    <td width="42%"><img src="docs/screen-dial.png" alt="スプレッドシート用のダイヤル：XLSX、PDF、JSON、HTML、DOCX、MD"></td>
  </tr>
  <tr>
    <td align="center"><sub>Home：ドロップゾーンと最近の結果（3D レンダリング、GPS マップ、フォント見本など）</sub></td>
    <td align="center"><sub>スプレッドシート用のダイヤル。裏返すと More formats と Tools</sub></td>
  </tr>
</table>

## 対応フォーマット

| 変換元 | 変換先 |
|---|---|
| **画像**：JPG、PNG、WEBP、HEIC、AVIF、TIFF、GIF、BMP、ICO | 相互変換、PDF、SVG（トレース）、ICNS、TGA、QOI |
| **プロ向け画像**：カメラ RAW（CR2、CR3、NEF、ARW、DNG、RAF、ORF、RW2…）、PSD、TGA、QOI、JPEG 2000、DDS、ICNS、PPM… | JPG、PNG、TIFF（RAW は 16 ビット）、WEBP、AVIF、HEIC、PDF |
| **ベクター**：SVG | PDF（ベクターのまま）、PNG、JPG、WEBP、ICO |
| **PDF** | JPG、PNG、DOCX、TXT。結合、分割、回転、圧縮、ページ番号、透かし、保護、ロック解除、画像の抽出 |
| **文書**：DOCX、TXT、Markdown、HTML、保存した Web ページ（MHTML）、reStructuredText | PDF、DOCX、HTML、Markdown、TXT |
| **メール**：EML | PDF、DOCX、HTML、TXT。添付ファイルの保存 |
| **スプレッドシート**：XLSX、XLSM、XLS、ODS、CSV、TSV | XLSX、ODS、CSV、TSV、JSON、HTML、PDF、DOCX、Markdown。連絡先 CSV → VCF。シートの結合・分割 |
| **データ**：JSON、JSON Lines、YAML、TOML、XML、plist、vCard | 相互変換、CSV、XLSX、PDF |
| **電子書籍**：EPUB、MOBI、FB2、CBZ、XPS | PDF、DOCX、TXT |
| **動画**：MP4、MOV、MKV、WEBM、AVI、WMV、FLV、M4V、MPEG、3GP | MP4、WEBM、MOV、GIF、MP3。圧縮、ミュート、回転、静止画の書き出し（iPhone の HDR はトーンマッピング） |
| **音声**：MP3、M4A、AAC、WAV、FLAC、OGG、OPUS、WMA、AIFF | MP3、M4A、WAV、FLAC、OGG。ラウドネスのノーマライズ、無音のカット、圧縮 |
| **字幕**：SRT、WebVTT、ASS/SSA、SBV、MicroDVD、SAMI、LRC、TTML | UTF-8 での相互変換、TXT。字幕のクリーンアップ、25 / 23.976 fps のタイミング修正 |
| **アーカイブ**：ZIP、7Z、TAR、TAR.GZ、TAR.BZ2、TAR.XZ、GZ、BZ2、XZ | 展開、ZIP、7Z、TAR.GZ。任意のファイルやフォルダ → 1 つの ZIP |
| **フォント**：TTF、OTF、WOFF、WOFF2、TTC | 相互変換、PNG / PDF の見本。ラテン文字サブセット、Web フォントキット |
| **3D モデル**：STL、OBJ、PLY、GLB、glTF、OFF、3MF | 相互変換、PNG プレビュー。中心合わせと接地、修復、ポリゴン削減 |
| **地図データ**：GPX、KML、KMZ、GeoJSON、Shapefile | 相互変換、CSV、PNG の地図。走行統計、反転、簡略化 |

インストールしてすぐにすべて使えます。ダウンロードにはすべてのエンジン（動画と音声用の FFmpeg を含む）が入っています。
`dropdial formats` を実行すると、お使いの環境での完全な一覧が表示されます。

## コマンドライン

`dropdial` コマンドは、アプリと同じエンジンとレシピを使います（ソースから使う場合：`python -m dropdial`）。

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

`--json` を付けると機械で読みやすい形式で出力します。失敗したファイルが 1 つでもあれば終了コードは 1 になります。

## 開発

Python 3.12。Windows、macOS、Linux で動作します：

```bash
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
pip install -r requirements.txt pytest
python -m dropdial
python -m pytest -q          # on Linux without a display: QT_QPA_PLATFORM=offscreen
```

[アーキテクチャ](docs/ARCHITECTURE.md) · [ファイル形式の追加](docs/ADDING-A-CONVERTER.md) · [コントリビュート](CONTRIBUTING.md) · [変更履歴](CHANGELOG.md) · [セキュリティ](SECURITY.md)

プルリクエスト歓迎です。DropDial でクリックの手間が少しでも減ったら、⭐ を付けてもらえると、ほかの人が見つけやすくなります。

## コード署名

DropDial は **Prithwiraj Mukherjee** が開発・公開しています。Windows 版と macOS 版のダウンロードはまだコード署名・公証されていないため、初回だけシステムが警告を表示します（[初回起動](#初回起動) を参照）。すべてのダウンロードは、このリポジトリのソースから GitHub Actions でビルドされており、手作業でビルドしたものはありません。

### プライバシー

DropDial はファイルをあなた自身のコンピュータ上で変換し、アップロードすることはありません。利用データの収集やテレメトリの送信も一切しません。インターネットに接続するのは次の場合だけです：

- 新しいリリースがあるかを GitHub（`api.github.com`）に確認するとき。起動直後と、その後は数時間ごとに確認します。Settings の「Check for updates automatically」でオフにできます。
- Web ブラウザからダイヤルへドラッグしたファイルをダウンロードするとき。
- リンクをクリックして、Web ブラウザで開くとき。

## ライセンス

MIT、© 2026 Prithwiraj Mukherjee。同梱しているサードパーティ製コンポーネントにはそれぞれのライセンスが適用されます。一覧は [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) にあります。

<p align="center">
  <a href="https://star-history.com/#prithwirajmukherjee15-cmd/DropDial&Date"><img src="https://api.star-history.com/svg?repos=prithwirajmukherjee15-cmd/DropDial&type=Date" alt="スター数の推移" width="600"></a>
</p>

<p align="center"><sub>制作：<b>Prithwiraj Mukherjee</b></sub></p>
