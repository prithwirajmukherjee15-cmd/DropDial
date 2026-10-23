"""Interface languages: catalogues are complete and well-formed, and every window opens in
every language."""
from __future__ import annotations

import ast
import json
import string
from pathlib import Path

import pytest

from dropdial import i18n

ROOT = Path(__file__).resolve().parents[1] / "dropdial"
LANGS = [code for code, _ in i18n.available() if code != "en"]


# ---------------------------------------------------------------- what the code shows
def _literals(node) -> list[str]:
    """String constants in an argument (both sides of `a if c else b`)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _literals(node.body) + _literals(node.orelse)
    return []


def _callee(node: ast.Call) -> str:
    f = node.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


def code_strings() -> set[str]:
    """Every English source string: tr/trn/N_ literals and UserError sentences (shown through
    i18n.error_text). The command line stays English, so cli.py is left out."""
    out: set[str] = set()
    for f in ROOT.rglob("*.py"):
        if f.name == "cli.py":
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = _callee(node)
            if name in ("tr", "N_", "UserError", "NotSmaller"):
                out.update(_literals(node.args[0]))
            elif name == "trn":
                for a in node.args[:2]:
                    out.update(_literals(a))
    return {s for s in out if s.strip()}


def family_strings() -> set[str]:
    """Names, hints and progress text of the plug-in families (dropdial/formats), which the
    dial translates as it shows them."""
    from dropdial import formats
    out: set[str] = set()
    for fam in formats.all_families():
        out.update(v for v in fam.hints.values() if v)
        for t in fam.tools:
            out.update(s for s in (t.name, t.hint, t.working) if s)
    return out


def source_strings() -> set[str]:
    return code_strings() | family_strings()


def catalogue(code: str) -> dict[str, str]:
    return json.loads((i18n.LOCALES / f"{code}.json").read_text(encoding="utf-8"))


def fields(s: str) -> set[str] | None:
    """Named {fields} of a template; None for a plain sentence that merely contains braces."""
    try:
        names = {name for _, name, _, _ in string.Formatter().parse(s) if name is not None}
    except ValueError:
        return None
    return names if all(n.isidentifier() for n in names) else None


@pytest.fixture
def english():
    yield
    i18n.set_language("en")


# ---------------------------------------------------------------- catalogues
@pytest.mark.parametrize("code", LANGS)
def test_catalogue_is_valid_and_current(code):
    cat = catalogue(code)
    assert cat and all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in cat.items())
    src = source_strings()
    stale = sorted(set(cat) - src)
    assert not stale, f"{code}: keys no longer used in the code: {stale[:10]}"
    missing = sorted(src - set(cat))
    assert len(src & set(cat)) >= 0.95 * len(src), f"{code}: {len(missing)} untranslated, e.g. {missing[:10]}"


@pytest.mark.parametrize("code", LANGS)
def test_placeholders_match(code):
    bad = [k for k, v in catalogue(code).items() if fields(k) != fields(v)]
    assert not bad, f"{code}: placeholders differ in {bad[:5]}"
    for k, v in catalogue(code).items():      # and every translation formats cleanly
        if fields(k):
            v.format(**{f: "x" for f in fields(k)})


@pytest.mark.parametrize("code", LANGS)
def test_names_stay_untranslated(code):
    cat = catalogue(code)
    for k, v in cat.items():
        for keep in ("DropDial", "PDF", "PNG", "WebP", "MP3", "MP4", "GPS", "ffmpeg"):
            if keep in k:
                assert keep in v, f"{code}: “{keep}” lost in {k!r} → {v!r}"


def test_every_language_has_a_catalogue_and_a_native_name():
    assert i18n.available()[0] == ("en", "English")
    for code, native in i18n.available():
        assert native and (code == "en" or (i18n.LOCALES / f"{code}.json").is_file())


# ---------------------------------------------------------------- lookups
def test_fallback_and_formatting(english):
    assert i18n.set_language("de") == "de"
    assert i18n.tr("Settings") == catalogue("de")["Settings"]
    assert i18n.tr("Not a string anyone wrote") == "Not a string anyone wrote"
    assert i18n.tr("Converting to {fmt}…", fmt="PNG").endswith("…") and "PNG" in i18n.tr("Converting to {fmt}…", fmt="PNG")
    assert i18n.trn("{n} file", "{n} files", 3) == catalogue("de")["{n} files"].format(n=3)
    assert i18n.set_language("xx") == "en" and i18n.tr("Settings") == "Settings"
    assert i18n.tr("{n} files", n=2) == "2 files"


def test_broken_translation_falls_back(english, monkeypatch):
    i18n.set_language("fr")
    monkeypatch.setitem(i18n._catalogue, "{n} files", "{count} fichiers")
    assert i18n.tr("{n} files", n=2) == "2 files"


def test_user_errors_translate_with_their_values(english):
    from dropdial.util import UserError
    e = UserError("{name} was moved or deleted.", name="a.png")
    assert str(e) == "a.png was moved or deleted."
    i18n.set_language("es")
    assert "a.png" in i18n.error_text(e) and i18n.error_text(e) != str(e)
    plain = UserError("No images found in this PDF.")
    assert i18n.error_text(plain) == catalogue("es")["No images found in this PDF."]
    assert UserError("{not a field}").args[0] == "{not a field}"     # no fields: kept as written


def test_default_is_english():
    # tests run with LANG=C: nothing set means English, so English assertions elsewhere hold
    assert i18n.current() == "en"
    assert i18n.system_language("C") == "en"


@pytest.mark.parametrize("name, code", [
    ("pt_BR", "pt-BR"), ("pt_PT", "pt-BR"), ("zh_CN", "zh-CN"), ("zh_TW", "zh-CN"), ("de_AT", "de"),
    ("fr_CA", "fr"), ("hi_IN", "hi"), ("ar_EG", "ar"), ("ja_JP", "ja"), ("ko_KR", "ko"), ("ru_RU", "ru"),
    ("es_MX", "es"), ("en_US", "en"), ("it_IT", "en"), ("C", "en"), ("", "en"), ("de_DE.UTF-8", "de"),
])
def test_system_language(name, code):
    assert i18n.system_language(name) == code


def test_system_setting_uses_the_locale(english, monkeypatch):
    monkeypatch.setattr(i18n, "system_language", lambda name=None: "ja")
    assert i18n.set_language("system") == "ja" and i18n.current() == "ja"


# ---------------------------------------------------------------- every window, every language
class _Settings:
    """Settings without touching the real profile."""

    def __init__(self, **values):
        from dropdial.settings import DEFAULTS
        self.values = {**DEFAULTS, **values}

    def get(self, key):
        return self.values[key]

    def set(self, key, value):
        self.values[key] = value


def _open_everything(tmp_path: Path):
    from PIL import Image
    from PySide6.QtWidgets import QApplication
    from dropdial import panels
    from dropdial.app import DropDialApp
    from dropdial.radial import RadialMenu
    from dropdial.settings import SettingsWindow, WelcomeWindow

    img = tmp_path / "photo.png"
    Image.new("RGB", (64, 48), (200, 120, 40)).save(img)
    windows = [SettingsWindow(_Settings()), WelcomeWindow(_Settings(), "Shift"), panels.HistoryWindow(),
               panels.RecipesWindow(), panels.WatchWindow()]

    class _App:   # what HomeWindow needs from the app
        update = None
        open_dialog = open_history = open_recipes = open_watch = open_settings = show_welcome = \
            show_click_menu = open_web_drop = staticmethod(lambda *a: None)
    from dropdial.home import HomeWindow
    windows.append(HomeWindow(_App()))
    menu = RadialMenu(lambda p: DropDialApp.build_rings(None, p), lambda p: DropDialApp.describe(None, p))
    for w in windows:
        w.show()
    menu._load([str(img)])
    menu.show()
    QApplication.processEvents()
    for ring in range(len(menu.ring_names)):         # draw every ring, hovering a petal
        menu.hover = 0
        menu.grab()
        menu.next_ring()
    shots = [w.grab() for w in windows]
    labels = [it.label for items in menu.rings.values() for it in items]
    for w in windows:
        w.close()
    menu.close_menu()
    return shots, labels, menu


@pytest.mark.parametrize("code", ["en"] + LANGS)
def test_windows_open_in_every_language(code, tmp_path, english):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    i18n.set_language(code)
    i18n.apply_direction()
    try:
        shots, labels, menu = _open_everything(tmp_path)
        assert all(not s.isNull() for s in shots)
        assert set(menu.ring_names) >= {"Convert", "Tools"}          # keys stay English
        if code != "en":
            assert i18n.tr("Compress") in labels and "Compress" not in labels
        assert QGuiApplication.layoutDirection() == (Qt.RightToLeft if code == "ar" else Qt.LeftToRight)
    finally:
        i18n.set_language("en")
        i18n.apply_direction()


def test_settings_language_choice(english):
    from dropdial.settings import SettingsWindow
    s = _Settings()
    w = SettingsWindow(s)
    codes = [w.language.itemData(i) for i in range(w.language.count())]
    assert codes == ["system"] + [c for c, _ in i18n.available()]
    assert "日本語" in [w.language.itemText(i) for i in range(w.language.count())]
    w.language.setCurrentIndex(codes.index("ja"))
    assert s.values["language"] == "ja" and i18n.current() == "ja"
    assert w.lang_note.text() == catalogue("ja")["Restart DropDial to apply everywhere"]
    w.close()


def test_built_in_recipes_translate_for_display_only(english):
    from dropdial import recipes
    i18n.set_language("fr")
    web = recipes.find("Web-ready")
    assert web.name == "Web-ready"                                   # stored and found by its real name
    assert recipes.display_name(web) == catalogue("fr")["Web-ready"]
    assert recipes.builtin_name(recipes.display_name(web)) == "Web-ready"
    assert recipes.display_name("My own thing") == "My own thing"
