<p align="center">
  <img src="docs/banner.png" alt="DropDial : faites glisser un fichier, appuyez sur Maj, déposez-le sur le cadran" width="100%">
</p>

<p align="center">
  <b>Un convertisseur de fichiers gratuit et open source, qui s’utilise par glisser-déposer.</b><br>
  Faites glisser n’importe quel fichier, appuyez sur <kbd>Shift</kbd> et déposez-le sur une part du cadran en verre qui s’ouvre sous votre curseur.
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><b>Télécharger</b></a> ·
  <a href="#installation">Installation</a> ·
  <a href="#premier-lancement">Premier lancement</a> ·
  <a href="#formats">Formats</a> ·
  <a href="#ligne-de-commande">Ligne de commande</a> ·
  <a href="#développement">Développement</a>
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml"><img src="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><img src="https://img.shields.io/github/v/release/prithwirajmukherjee15-cmd/DropDial?color=d8ad62&label=release" alt="Dernière version"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases"><img src="https://img.shields.io/github/downloads/prithwirajmukherjee15-cmd/DropDial/total?color=a87a34" alt="Téléchargements"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-2b2f3a" alt="Windows 10 | 11">
  <img src="https://img.shields.io/badge/macOS-11%2B-2b2f3a" alt="macOS 11+">
  <img src="https://img.shields.io/badge/Linux-x64-2b2f3a" alt="Linux x64">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-e3be7a" alt="Licence MIT"></a>
</p>

<p align="center"><a href="README.md">English</a> · <a href="README.hi.md">हिन्दी</a> · <a href="README.es.md">Español</a> · <b>Français</b> · <a href="README.de.md">Deutsch</a> · <a href="README.pt-BR.md">Português (Brasil)</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ru.md">Русский</a> · <a href="README.ar.md">العربية</a></p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg"><img src="docs/btn-mac-arm.svg" alt="Télécharger pour macOS (Apple Silicon)" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg"><img src="docs/btn-mac-intel.svg" alt="Télécharger pour macOS (Intel)" height="56"></a>
  <br>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe"><img src="docs/btn-win.svg" alt="Télécharger pour Windows" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb"><img src="docs/btn-linux.svg" alt="Télécharger pour Linux" height="56"></a>
</p>

> [!IMPORTANT]
> **Vous ouvrez DropDial pour la première fois ?** Windows et macOS affichent un avertissement de sécurité, une seule fois, parce que l’app n’est pas encore signée. Elle est sûre, et il suffit de 10 secondes pour passer l’avertissement. **[Voir Premier lancement ↓](#premier-lancement)**

<table>
  <tr>
    <td width="33%" valign="top"><b>Directement sous votre curseur</b><br>Aucune fenêtre à ouvrir. Le cadran apparaît là où vous êtes déjà, avec seulement les formats qui ont du sens pour les fichiers que vous faites glisser.</td>
    <td width="33%" valign="top"><b>Plus de 140 types de fichiers, sans autre logiciel</b><br>Images, RAW d’appareil photo, PDF, Word, Excel, livres numériques, vidéo, audio, sous-titres, archives, polices, modèles 3D et fichiers cartographiques fonctionnent sans Office ni rien d’autre à installer.</td>
    <td width="33%" valign="top"><b>Tout reste sur votre ordinateur</b><br>Rien n’est envoyé en ligne. DropDial fonctionne hors ligne et enregistre le résultat à côté de l’original, jamais par-dessus.</td>
  </tr>
</table>

## Voir DropDial en action

<p align="center">
  <img src="docs/demo.gif" alt="Faire glisser une photo, appuyer sur Maj et la déposer sur Compress" width="760">
</p>

## Installation

Téléchargez-le depuis les [Releases](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest).

- **macOS 11+** : ouvrez le `.dmg` ([Apple Silicon](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg) · [Intel](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg)) et faites glisser DropDial dans Applications. Ou collez ceci dans le Terminal : la commande choisit la bonne version, l’installe sans alerte de sécurité et la met à jour quand vous la relancez :
  ```bash
  curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/DropDial/main/install-mac.sh | bash
  ```
- **Windows 10/11** : lancez [`DropDial-Setup.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe) (installation pour votre utilisateur, sans droits administrateur ; ajoute le menu contextuel, *Envoyer vers* et le démarrage avec Windows), ou utilisez la version portable [`DropDial.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial.exe).
- **Linux x64** (Debian 12+, Ubuntu 23.04+, Mint…) : `sudo apt install ./DropDial-linux-amd64.deb` ([télécharger](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb)). Le geste Maj nécessite X11 ; sous Wayland, utilisez la zone de dépôt de Home ou clic droit → **Ouvrir avec → DropDial**.
- **Linux ARM64** (Ubuntu 24.04+, Debian 13+, Raspberry Pi OS 13 64 bits…) : `sudo apt install ./DropDial-linux-arm64.deb` ([télécharger](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-arm64.deb)).

DropDial se loge dans la barre des menus / la zone de notification et vous prévient quand une nouvelle version sort.

## Premier lancement

DropDial n’est pas encore signé (les certificats de signature coûtent de l’argent chaque année) : Windows et macOS affichent donc un avertissement **la première fois seulement**. Tout le code de DropDial est public dans ce dépôt, et GitHub construit automatiquement les téléchargements à partir de celui-ci.

### Windows : « Windows a protégé votre ordinateur »

SmartScreen peut afficher ce message la première fois que vous lancez `DropDial-Setup.exe` ou `DropDial.exe`.

1. Cliquez sur **Informations complémentaires**.
2. Cliquez sur **Exécuter quand même**.

C’est tout. Windows ne vous le redemandera plus.

### Mac : « Apple n’a pas pu vérifier DropDial… »

Si vous avez installé DropDial avec la ligne de Terminal ci-dessus, vous pouvez sauter cette étape : il n’y a pas d’avertissement. Avec le **.dmg**, macOS affiche *« Apple n’a pas pu confirmer que “DropDial” ne contenait pas de logiciel malveillant pouvant endommager votre Mac ou compromettre votre confidentialité. »* Il le dit pour toute app qui n’est pas passée par la notarisation payante d’Apple. Pour l’ouvrir :

1. Ouvrez **DropDial** une fois depuis Applications, puis cliquez sur **Terminé** dans l’avertissement.
2. Ouvrez **menu Pomme → Réglages Système → Confidentialité et sécurité**. Faites défiler jusqu’à **« DropDial » a été bloqué pour protéger votre Mac** et cliquez sur **Ouvrir quand même**.
3. Saisissez votre mot de passe et cliquez à nouveau sur **Ouvrir quand même** pour confirmer.

Terminé. macOS retient votre choix, vous n’aurez à le faire qu’une fois.

<details>
<summary>Vous préférez le Terminal ? Une seule commande fait la même chose</summary>

```bash
xattr -dr com.apple.quarantine /Applications/DropDial.app
```

Ensuite, ouvrez DropDial normalement.
</details>

> [!NOTE]
> Depuis macOS 15 (Sequoia), l’ancien raccourci **clic droit → Ouvrir** ne permet plus de passer cet avertissement. Suivez plutôt les étapes ci-dessus.

### Mac, facultatif : enregistrement de l’écran

DropDial peut demander l’autorisation d’**Enregistrement de l’écran**. Si vous l’accordez, le cadran en verre laisse voir les fenêtres qui se trouvent derrière lui. Sinon, tout fonctionne quand même et le verre affiche votre fond d’écran. **Rien n’est jamais enregistré, conservé ni envoyé où que ce soit.** Vous pouvez modifier ce choix à tout moment dans **Réglages Système → Confidentialité et sécurité → Enregistrement de l’écran et de l’audio du système**.

## Fonctionnalités

- **Un cadran sous le curseur** : faites glisser des fichiers, appuyez sur <kbd>Shift</kbd> et déposez-les sur un format. Seuls les formats adaptés à ces fichiers apparaissent.
- **Plusieurs faces** : appuyez de nouveau sur <kbd>Shift</kbd>, appuyez sur <kbd>Tab</kbd> ou tournez la molette de la souris pour passer à **More formats**, **Tools** et **Recipes**.
- **Directement depuis le navigateur** : faites glisser une image, un lien vers un fichier ou un téléchargement depuis Chrome, Edge, Firefox ou Safari. DropDial l’enregistre dans Téléchargements, puis le convertit.
- **Home** : cliquez sur l’icône de la zone de notification / de la barre des menus pour ouvrir une zone de dépôt (pas besoin de Maj) et vos résultats récents avec aperçu. Ouvrez-les, affichez-les dans le dossier, convertissez-les à nouveau ou annulez.
- **Des outils pour chaque type de fichier** : compresser, redimensionner, recadrer, retoucher, annoter, caviarder, ajouter un filigrane et supprimer les métadonnées des images ; diviser, fusionner, faire pivoter, numéroter, protéger, déverrouiller et compresser des PDF ; compresser, couper le son et faire pivoter des vidéos ; normaliser l’audio ; nettoyer des sous-titres ; réduire des polices à un sous-ensemble ; réparer des modèles 3D ; statistiques de parcours GPS ; et plus encore.
- **Recipes** : enchaînez plusieurs étapes dans une seule part (« Web-ready », « Email size », « Private »…) ou créez les vôtres.
- **Dossiers surveillés** qui convertissent chaque fichier qui y arrive.
- **Plusieurs fichiers à la fois**, une part ZIP pour une pile de fichiers ou un dossier, et **History** pour retrouver ou annuler n’importe quoi.
- **D’autres façons de l’utiliser** : le menu contextuel, *Envoyer vers* (Windows), la zone de dépôt de Home et la [commande `dropdial`](#ligne-de-commande).
- **À votre goût** : un cadran en verre liquide avec la couleur d’accent de votre choix (Champagne, Rose, Ocean, Emerald, Violet, Silver).

## Captures d’écran

<table>
  <tr>
    <td width="58%"><img src="docs/screen-home.png" alt="Home : zone de dépôt et résultats récents avec aperçu"></td>
    <td width="42%"><img src="docs/screen-dial.png" alt="Le cadran pour un tableur : XLSX, PDF, JSON, HTML, DOCX, MD"></td>
  </tr>
  <tr>
    <td align="center"><sub>Home : zone de dépôt et résultats récents (un rendu 3D, une carte GPS, un spécimen de police…)</sub></td>
    <td align="center"><sub>Le cadran pour un tableur ; retournez-le pour More formats et Tools</sub></td>
  </tr>
</table>

## Formats

| Depuis | Vers |
|---|---|
| **Images** : JPG, PNG, WEBP, HEIC, AVIF, TIFF, GIF, BMP, ICO | entre eux, PDF, SVG (vectorisé), ICNS, TGA, QOI |
| **Images pro** : RAW d’appareil photo (CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2…), PSD, TGA, QOI, JPEG 2000, DDS, ICNS, PPM… | JPG, PNG, TIFF (16 bits pour le RAW), WEBP, AVIF, HEIC, PDF |
| **Vectoriel** : SVG | PDF (reste vectoriel), PNG, JPG, WEBP, ICO |
| **PDF** | JPG, PNG, DOCX, TXT ; fusionner, diviser, faire pivoter, compresser, numéroter, filigrane, protéger, déverrouiller, extraire les images |
| **Documents** : DOCX, TXT, Markdown, HTML, pages web enregistrées (MHTML), reStructuredText | PDF, DOCX, HTML, Markdown, TXT |
| **E-mail** : EML | PDF, DOCX, HTML, TXT ; enregistrer les pièces jointes |
| **Tableurs** : XLSX, XLSM, XLS, ODS, CSV, TSV | XLSX, ODS, CSV, TSV, JSON, HTML, PDF, DOCX, Markdown ; CSV de contacts → VCF ; combiner, séparer les feuilles |
| **Données** : JSON, JSON Lines, YAML, TOML, XML, plist, vCard | entre eux, CSV, XLSX, PDF |
| **Livres numériques** : EPUB, MOBI, FB2, CBZ, XPS | PDF, DOCX, TXT |
| **Vidéo** : MP4, MOV, MKV, WEBM, AVI, WMV, FLV, M4V, MPEG, 3GP | MP4, WEBM, MOV, GIF, MP3 ; compresser, couper le son, faire pivoter, image fixe (le HDR de l’iPhone est converti par tone mapping) |
| **Audio** : MP3, M4A, AAC, WAV, FLAC, OGG, OPUS, WMA, AIFF | MP3, M4A, WAV, FLAC, OGG ; normaliser le volume, supprimer les silences, compresser |
| **Sous-titres** : SRT, WebVTT, ASS/SSA, SBV, MicroDVD, SAMI, LRC, TTML | entre eux en UTF-8, TXT ; nettoyer les sous-titres, corriger le minutage 25 / 23,976 i/s |
| **Archives** : ZIP, 7Z, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, GZ, BZ2, XZ | extraire, ZIP, 7Z, TAR.GZ ; n’importe quels fichiers ou dossier → un seul ZIP |
| **Polices** : TTF, OTF, WOFF, WOFF2, TTC | entre elles, spécimen PNG / PDF ; sous-ensemble latin, kit de polices web |
| **Modèles 3D** : STL, OBJ, PLY, GLB, glTF, OFF, 3MF | entre eux, aperçu PNG ; centrer et poser au sol, réparer, simplifier |
| **Données cartographiques** : GPX, KML, KMZ, GeoJSON, Shapefile | entre elles, CSV, carte PNG ; statistiques de parcours, inverser, simplifier |

Tout fonctionne dès l’installation : les téléchargements incluent tous les moteurs (FFmpeg pour la vidéo et l’audio).
`dropdial formats` affiche la liste complète pour votre copie.

## Ligne de commande

La commande `dropdial` utilise les mêmes moteurs et recettes que l’app (depuis les sources : `python -m dropdial`).

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

Ajoutez `--json` pour une sortie lisible par une machine ; le code de sortie vaut 1 si un fichier a échoué.

## Développement

Python 3.12, sous Windows, macOS ou Linux :

```bash
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
pip install -r requirements.txt pytest
python -m dropdial
python -m pytest -q          # on Linux without a display: QT_QPA_PLATFORM=offscreen
```

[Architecture](docs/ARCHITECTURE.md) · [Ajouter un format de fichier](docs/ADDING-A-CONVERTER.md) · [Contribuer](CONTRIBUTING.md) · [Journal des modifications](CHANGELOG.md) · [Sécurité](SECURITY.md)

Les pull requests sont les bienvenues. Si DropDial vous fait gagner quelques clics, une ⭐ aide d’autres personnes à le découvrir.

## Signature du code

DropDial est développé et publié par **Prithwiraj Mukherjee**. Les téléchargements Windows et macOS ne sont pas encore signés ni notarisés, c’est pourquoi le système affiche un avertissement la première fois (voir [Premier lancement](#premier-lancement)). Chaque téléchargement est construit par GitHub Actions à partir du code source de ce dépôt ; rien n’est compilé à la main.

### Confidentialité

DropDial convertit les fichiers sur votre propre ordinateur et ne les envoie jamais en ligne. Il ne collecte aucune donnée d’utilisation et n’envoie aucune télémétrie. Il se connecte à internet uniquement :

- pour demander à GitHub (`api.github.com`) s’il existe une version plus récente, peu après le démarrage puis toutes les quelques heures. Vous pouvez désactiver cela dans Settings (« Check for updates automatically »).
- pour télécharger un fichier que vous faites glisser depuis votre navigateur jusqu’au cadran.
- quand vous cliquez sur un lien, qui s’ouvre dans votre navigateur.

## Licence

MIT, © 2026 Prithwiraj Mukherjee. Les composants tiers inclus conservent leurs propres licences, répertoriées dans [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

<p align="center">
  <a href="https://star-history.com/#prithwirajmukherjee15-cmd/DropDial&Date"><img src="https://api.star-history.com/svg?repos=prithwirajmukherjee15-cmd/DropDial&type=Date" alt="Historique des étoiles" width="600"></a>
</p>

<p align="center"><sub>Créé par <b>Prithwiraj Mukherjee</b></sub></p>
