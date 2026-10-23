# Third-party notices

DropDial is MIT-licensed (see [LICENSE](LICENSE)). The downloads also bundle the open-source
components below; each keeps its own licence. Their full licence texts ship inside the installed
app, in the folders PyInstaller copies from each package.

| Component | Used for | Licence |
|---|---|---|
| [Python](https://www.python.org/) | Runtime | PSF License |
| [Qt](https://www.qt.io/) / [PySide6](https://pyside.org) | Windows, the dial, SVG and PDF drawing | LGPL-3.0 |
| [Pillow](https://github.com/python-pillow/Pillow) | Reading and writing images | MIT-CMU |
| [pillow-heif](https://github.com/bigcat88/pillow_heif) (libheif, libde265, x265) | HEIC / AVIF | BSD-3-Clause; bundled codecs LGPL / GPL |
| [PyMuPDF](https://github.com/pymupdf/pymupdf) (MuPDF) | PDF, e-books, PDF rendering | AGPL-3.0 |
| [NumPy](https://numpy.org/) | Image maths, glass rendering | BSD-3-Clause |
| [python-docx](https://github.com/python-openxml/python-docx) | Word documents | MIT |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) (FFmpeg) | Video and audio | BSD-2-Clause; FFmpeg binary GPL-3.0 |
| [vtracer](https://github.com/visioncortex/vtracer) | Image → SVG tracing | MIT |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | Excel workbooks | MIT |
| [PyYAML](https://pyyaml.org/) | YAML | MIT |
| [defusedxml](https://github.com/tiran/defusedxml) | Safe XML parsing | PSF License |
| [tomli-w](https://github.com/hukkin/tomli-w) | Writing TOML | MIT |
| [py7zr](https://github.com/miurahr/py7zr) | 7-Zip archives | LGPL-2.1-or-later |
| [rawpy](https://github.com/letmaik/rawpy) (LibRaw) | Camera RAW photos | MIT; LibRaw LGPL-2.1 / CDDL-1.0 |
| [fontTools](https://github.com/fonttools/fonttools), [Brotli](https://github.com/google/brotli) | Fonts, WOFF2 | MIT |
| [trimesh](https://github.com/mikedh/trimesh) | 3D models | MIT |
| [Python-Markdown](https://Python-Markdown.github.io/) | Markdown | BSD-3-Clause |

Because PyMuPDF and the bundled FFmpeg are copyleft, the complete source of DropDial is published in
this repository, and the source of each component is available from the links above.
