<p align="center">
  <img src="docs/banner.png" alt="DropDial: arraste um arquivo, aperte Shift e solte no seletor" width="100%">
</p>

<p align="center">
  <b>Um conversor de arquivos gratuito e de código aberto que você usa arrastando.</b><br>
  Arraste qualquer arquivo, aperte <kbd>Shift</kbd> e solte em uma fatia do seletor de vidro que se abre no seu cursor.
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><b>Baixar</b></a> ·
  <a href="#instalação">Instalação</a> ·
  <a href="#primeira-execução">Primeira execução</a> ·
  <a href="#formatos">Formatos</a> ·
  <a href="#linha-de-comando">Linha de comando</a> ·
  <a href="#desenvolvimento">Desenvolvimento</a>
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml"><img src="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><img src="https://img.shields.io/github/v/release/prithwirajmukherjee15-cmd/DropDial?color=d8ad62&label=release" alt="Versão mais recente"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases"><img src="https://img.shields.io/github/downloads/prithwirajmukherjee15-cmd/DropDial/total?color=a87a34" alt="Downloads"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-2b2f3a" alt="Windows 10 | 11">
  <img src="https://img.shields.io/badge/macOS-11%2B-2b2f3a" alt="macOS 11+">
  <img src="https://img.shields.io/badge/Linux-x64-2b2f3a" alt="Linux x64">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-e3be7a" alt="Licença MIT"></a>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.hi.md">हिन्दी</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a> · <b>Português (Brasil)</b> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ru.md">Русский</a> · <a href="README.ar.md">العربية</a></p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg"><img src="docs/btn-mac-arm.svg" alt="Baixar para macOS (Apple Silicon)" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg"><img src="docs/btn-mac-intel.svg" alt="Baixar para macOS (Intel)" height="56"></a>
  <br>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe"><img src="docs/btn-win.svg" alt="Baixar para Windows" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb"><img src="docs/btn-linux.svg" alt="Baixar para Linux" height="56"></a>
</p>

> [!IMPORTANT]
> **Vai abrir o DropDial pela primeira vez?** O Windows e o macOS mostram um aviso de segurança uma única vez, porque o app ainda não tem assinatura de código. Ele é seguro, e passar pelo aviso leva 10 segundos. **[Veja Primeira execução ↓](#primeira-execução)**

<table>
  <tr>
    <td width="33%" valign="top"><b>Bem no seu cursor</b><br>Nenhuma janela para abrir. O seletor aparece onde você já está, só com os formatos que fazem sentido para os arquivos que você arrasta.</td>
    <td width="33%" valign="top"><b>Mais de 140 tipos de arquivo, sem outros programas</b><br>Imagens, RAW de câmera, PDF, Word, Excel, e-books, vídeo, áudio, legendas, arquivos compactados, fontes, modelos 3D e arquivos de mapa funcionam sem Office nem qualquer outra coisa instalada.</td>
    <td width="33%" valign="top"><b>Fica no seu computador</b><br>Nada é enviado para a internet. O DropDial funciona offline e salva o resultado ao lado do original, nunca por cima dele.</td>
  </tr>
</table>

## Veja funcionando

<p align="center">
  <img src="docs/demo.gif" alt="Arrastando uma foto, apertando Shift e soltando em Compress" width="760">
</p>

## Instalação

Baixe em [Releases](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest).

- **macOS 11+**: abra o `.dmg` ([Apple Silicon](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg) · [Intel](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg)) e arraste o DropDial para Aplicativos. Ou cole isto no Terminal: ele escolhe a versão certa, instala sem nenhum aviso de segurança e atualiza quando você rodar de novo:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/DropDial/main/install-mac.sh | bash
  ```
- **Windows 10/11**: execute o [`DropDial-Setup.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe) (instala para o seu usuário, sem precisar de administrador; adiciona o menu do botão direito, *Enviar para* e a inicialização com o Windows), ou use o portátil [`DropDial.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial.exe).
- **Linux x64** (Debian 12+, Ubuntu 23.04+, Mint…): `sudo apt install ./DropDial-linux-amd64.deb` ([baixar](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb)). O gesto do Shift precisa de X11; no Wayland, use a área de soltar do Home ou clique com o botão direito → **Abrir com → DropDial**.
- **Linux ARM64** (Ubuntu 24.04+, Debian 13+, Raspberry Pi OS 13 de 64 bits…): `sudo apt install ./DropDial-linux-arm64.deb` ([baixar](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-arm64.deb)).

O DropDial fica na barra de menus / bandeja do sistema e avisa quando sai uma versão nova.

## Primeira execução

O DropDial ainda não tem assinatura de código (certificados de assinatura custam dinheiro todo ano), então o Windows e o macOS mostram um aviso **só na primeira vez**. Todo o código do DropDial é público neste repositório, e os downloads são gerados a partir dele automaticamente pelo GitHub.

### Windows: “O Windows protegeu o computador”

O SmartScreen pode mostrar isso na primeira vez que você executar o `DropDial-Setup.exe` ou o `DropDial.exe`.

1. Clique em **Mais informações**.
2. Clique em **Executar assim mesmo**.

Pronto. O Windows não vai perguntar de novo.

### Mac: “A Apple não conseguiu verificar o DropDial…”

Se você instalou com a linha do Terminal acima, pode pular esta parte: não aparece nenhum aviso. Com o **.dmg**, o macOS diz *“A Apple não conseguiu verificar se ‘DropDial’ está livre de malware que possa danificar o Mac ou comprometer a sua privacidade.”* Ele diz isso de qualquer app que não passou pela notarização paga da Apple. Para abrir:

1. Abra o **DropDial** em Aplicativos uma vez e feche o aviso.
2. Abra **menu Apple → Ajustes do Sistema → Privacidade e Segurança**. Role até **“DropDial” foi bloqueado para proteger o seu Mac** e clique em **Abrir Mesmo Assim**.
3. Digite sua senha e clique em **Abrir Mesmo Assim** de novo para confirmar.

Feito. O macOS lembra da escolha, então você só faz isso uma vez.

<details>
<summary>Prefere o Terminal? Um comando faz a mesma coisa</summary>

```bash
xattr -dr com.apple.quarantine /Applications/DropDial.app
```

Depois abra o DropDial normalmente.
</details>

> [!NOTE]
> No macOS 15 (Sequoia) e posteriores, o velho atalho **clique com o botão direito → Abrir** não passa mais por esse aviso. Use os passos acima.

### Mac, opcional: Gravação de Tela

O DropDial pode pedir permissão de **Gravação de Tela**. Se você permitir, o seletor de vidro mostra as janelas que estão atrás dele. Se não permitir, tudo continua funcionando e o vidro mostra o seu papel de parede. **Nada é gravado, salvo ou enviado para lugar nenhum, nunca.** Você pode mudar isso quando quiser em **Ajustes do Sistema → Privacidade e Segurança → Gravação de Tela e Áudio do Sistema**.

## Recursos

- **Um seletor no cursor**: arraste arquivos, aperte <kbd>Shift</kbd> e solte em um formato. Só aparecem os formatos que combinam com os arquivos.
- **Mais de um lado**: toque <kbd>Shift</kbd> de novo, aperte <kbd>Tab</kbd> ou gire a roda do mouse para virar para **More formats**, **Tools** e **Recipes**.
- **Direto do navegador**: arraste uma imagem, um link para um arquivo ou um download do Chrome, Edge, Firefox ou Safari. O DropDial salva em Downloads e depois converte.
- **Home**: clique no ícone da bandeja / barra de menus para abrir uma área de soltar (sem precisar de Shift) e seus resultados recentes com prévia. Abra, mostre na pasta, converta de novo ou desfaça.
- **Ferramentas para cada tipo de arquivo**: comprimir, redimensionar, recortar, editar, anotar, ocultar trechos, colocar marca d’água e remover metadados de imagens; dividir, juntar, girar, numerar, proteger, desbloquear e comprimir PDFs; comprimir, tirar o som e girar vídeos; normalizar áudio; limpar legendas; reduzir fontes a um subconjunto; reparar modelos 3D; estatísticas de trajetos GPS; e mais.
- **Recipes**: encadeie etapas em uma única fatia ("Web-ready", "Email size", "Private"…) ou crie as suas.
- **Pastas monitoradas** convertem cada arquivo que cai nelas.
- **Vários arquivos de uma vez**, uma fatia ZIP para uma pilha de arquivos ou uma pasta, e **History** para encontrar ou desfazer qualquer coisa.
- **Outros jeitos de usar**: o menu do botão direito, *Enviar para* (Windows), a área de soltar do Home e o [comando `dropdial`](#linha-de-comando).
- **Do seu jeito**: seletor de vidro líquido com a cor de destaque que você preferir (Champagne, Rose, Ocean, Emerald, Violet, Silver).

## Capturas de tela

<table>
  <tr>
    <td width="58%"><img src="docs/screen-home.png" alt="Home: área de soltar e resultados recentes com prévia"></td>
    <td width="42%"><img src="docs/screen-dial.png" alt="O seletor para uma planilha: XLSX, PDF, JSON, HTML, DOCX, MD"></td>
  </tr>
  <tr>
    <td align="center"><sub>Home: área de soltar e resultados recentes (uma renderização 3D, um mapa GPS, uma amostra de fonte…)</sub></td>
    <td align="center"><sub>O seletor para uma planilha; vire para ver More formats e Tools</sub></td>
  </tr>
</table>

## Formatos

| De | Para |
|---|---|
| **Imagens**: JPG, PNG, WEBP, HEIC, AVIF, TIFF, GIF, BMP, ICO | entre si, PDF, SVG (vetorizado), ICNS, TGA, QOI |
| **Imagens profissionais**: RAW de câmera (CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2…), PSD, TGA, QOI, JPEG 2000, DDS, ICNS, PPM… | JPG, PNG, TIFF (16 bits para RAW), WEBP, AVIF, HEIC, PDF |
| **Vetor**: SVG | PDF (continua vetorial), PNG, JPG, WEBP, ICO |
| **PDF** | JPG, PNG, DOCX, TXT; juntar, dividir, girar, comprimir, numerar, marca d’água, proteger, desbloquear, extrair imagens |
| **Documentos**: DOCX, TXT, Markdown, HTML, páginas da web salvas (MHTML), reStructuredText | PDF, DOCX, HTML, Markdown, TXT |
| **E-mail**: EML | PDF, DOCX, HTML, TXT; salvar anexos |
| **Planilhas**: XLSX, XLSM, XLS, ODS, CSV, TSV | XLSX, ODS, CSV, TSV, JSON, HTML, PDF, DOCX, Markdown; CSV de contatos → VCF; combinar, dividir abas |
| **Dados**: JSON, JSON Lines, YAML, TOML, XML, plist, vCard | entre si, CSV, XLSX, PDF |
| **E-books**: EPUB, MOBI, FB2, CBZ, XPS | PDF, DOCX, TXT |
| **Vídeo**: MP4, MOV, MKV, WEBM, AVI, WMV, FLV, M4V, MPEG, 3GP | MP4, WEBM, MOV, GIF, MP3; comprimir, tirar o som, girar, quadro estático (o HDR do iPhone passa por tone mapping) |
| **Áudio**: MP3, M4A, AAC, WAV, FLAC, OGG, OPUS, WMA, AIFF | MP3, M4A, WAV, FLAC, OGG; normalizar volume, cortar silêncio, comprimir |
| **Legendas**: SRT, WebVTT, ASS/SSA, SBV, MicroDVD, SAMI, LRC, TTML | entre si em UTF-8, TXT; limpar legendas, corrigir sincronia 25 / 23,976 fps |
| **Arquivos compactados**: ZIP, 7Z, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, GZ, BZ2, XZ | extrair, ZIP, 7Z, TAR.GZ; quaisquer arquivos ou pasta → um ZIP |
| **Fontes**: TTF, OTF, WOFF, WOFF2, TTC | entre si, amostra em PNG / PDF; subconjunto latino, kit de fontes para web |
| **Modelos 3D**: STL, OBJ, PLY, GLB, glTF, OFF, 3MF | entre si, prévia em PNG; centralizar e apoiar no chão, reparar, simplificar malha |
| **Dados de mapa**: GPX, KML, KMZ, GeoJSON, Shapefile | entre si, CSV, mapa em PNG; estatísticas do trajeto, inverter, simplificar |

Tudo funciona logo de cara: os downloads incluem todos os motores (FFmpeg para vídeo e áudio).
`dropdial formats` mostra a lista completa da sua cópia.

## Linha de comando

O comando `dropdial` usa os mesmos motores e receitas do app (a partir do código-fonte: `python -m dropdial`).

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

Adicione `--json` para ter uma saída legível por máquina; o código de saída é 1 se algum arquivo falhar.

## Desenvolvimento

Python 3.12, no Windows, macOS ou Linux:

```bash
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
pip install -r requirements.txt pytest
python -m dropdial
python -m pytest -q          # on Linux without a display: QT_QPA_PLATFORM=offscreen
```

[Arquitetura](docs/ARCHITECTURE.md) · [Adicionar um formato de arquivo](docs/ADDING-A-CONVERTER.md) · [Como contribuir](CONTRIBUTING.md) · [Histórico de mudanças](CHANGELOG.md) · [Segurança](SECURITY.md)

Pull requests são bem-vindos. Se o DropDial te poupa alguns cliques, uma ⭐ ajuda outras pessoas a encontrá-lo.

## Assinatura de código

O DropDial é desenvolvido e publicado por **Prithwiraj Mukherjee**. Os downloads para Windows e macOS ainda não têm assinatura de código nem notarização, e é por isso que o sistema avisa na primeira vez (veja [Primeira execução](#primeira-execução)). Cada download é gerado pelo GitHub Actions a partir do código-fonte deste repositório; nada é compilado à mão.

### Privacidade

O DropDial converte arquivos no seu próprio computador e nunca os envia para a internet. Ele não coleta dados de uso nem envia telemetria. Ele só se conecta à internet:

- para perguntar ao GitHub (`api.github.com`) se existe uma versão mais nova, logo depois de iniciar e depois a cada poucas horas. Desative isso em Settings ("Check for updates automatically").
- para baixar um arquivo que você arrasta do navegador para o seletor.
- quando você clica em um link, que abre no seu navegador.

## Licença

MIT, © 2026 Prithwiraj Mukherjee. Os componentes de terceiros incluídos mantêm suas próprias licenças, listadas em [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

<p align="center">
  <a href="https://star-history.com/#prithwirajmukherjee15-cmd/DropDial&Date"><img src="https://api.star-history.com/svg?repos=prithwirajmukherjee15-cmd/DropDial&type=Date" alt="Histórico de estrelas" width="600"></a>
</p>

<p align="center"><sub>Feito por <b>Prithwiraj Mukherjee</b></sub></p>
