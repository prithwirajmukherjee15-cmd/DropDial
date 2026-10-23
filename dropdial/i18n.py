"""Interface languages.

Code is written in English and wraps what it shows in `tr("English text")`; the text is
looked up in the active language's catalogue (dropdial/locales/<code>.json, a flat
{"English": "translation"} map) and falls back to English when it isn't there. Values go
in as named fields, so translators can move them: tr("{n} files", n=3).

Strings kept in tables and translated later are marked with N_("…"): it returns the text
unchanged and only tells the catalogue checker (tests/test_i18n.py) that the text is shown.

The command line never sets a language, so its output stays English for scripts. No Qt
needed here, except to read the system locale.
"""
from __future__ import annotations

import json
from pathlib import Path

LOCALES = Path(__file__).with_name("locales")

# code -> the language's own name (shown in Settings)
LANGUAGES: dict[str, str] = {
    "en": "English",
    "hi": "हिन्दी",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "pt-BR": "Português (Brasil)",
    "ja": "日本語",
    "ko": "한국어",
    "zh-CN": "简体中文",
    "ru": "Русский",
    "ar": "العربية",
}
RTL = {"ar"}

_lang = "en"
_catalogue: dict[str, str] = {}


def N_(text: str) -> str:
    """Mark a string for translation without translating it yet (tables, constants)."""
    return text


def tr(text: str, **fmt) -> str:
    """`text` in the active language (English if there's no translation), with `fmt` filled in."""
    out = _catalogue.get(text, text)
    if fmt:
        try:
            return out.format(**fmt)
        except (KeyError, IndexError, ValueError):   # a broken translation never breaks the UI
            return text.format(**fmt)
    return out


def trn(one: str, many: str, n: int, **fmt) -> str:
    """Singular or plural English source, chosen by `n` (available as {n}), then translated."""
    return tr(one if n == 1 else many, n=n, **fmt)


def error_text(e: BaseException) -> str:
    """A UserError's message in the active language (see util.UserError for named fields)."""
    template = getattr(e, "template", None)
    if template is not None:
        return tr(template, **getattr(e, "fmt", {}))
    return tr(str(e))


def load(code: str) -> dict[str, str]:
    """The catalogue for `code` ({} for English, or a missing / unreadable file)."""
    if code == "en":
        return {}
    try:
        data = json.loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str) and v}


def set_language(code: str | None) -> str:
    """Switch language: a code from LANGUAGES, or "system" / None for the computer's language.
    Returns the code actually in use."""
    global _lang, _catalogue
    if not code or code == "system":
        code = system_language()
    if code not in LANGUAGES:
        code = "en"
    _lang, _catalogue = code, load(code)
    return code


def current() -> str:
    return _lang


def is_rtl(code: str | None = None) -> bool:
    return (code or _lang) in RTL


def available() -> list[tuple[str, str]]:
    """[(code, native name)] for every language, English first."""
    return list(LANGUAGES.items())


def system_language(name: str | None = None) -> str:
    """The supported language closest to the system locale ("pt_BR" -> "pt-BR", "de_AT" -> "de",
    "zh_TW" -> "zh-CN"), or "en". `name` overrides QLocale.system().name() (for tests)."""
    if name is None:
        try:
            from PySide6.QtCore import QLocale
            name = QLocale.system().name()
        except Exception:  # noqa: BLE001 - no Qt: English
            return "en"
    name = (name or "").split(".")[0].replace("-", "_")
    lang, _, region = name.partition("_")
    full = f"{lang.lower()}-{region.upper()}" if region else lang.lower()
    if full in LANGUAGES:
        return full
    lang = lang.lower()
    if lang == "pt":
        return "pt-BR"
    if lang == "zh":
        return "zh-CN"
    return lang if lang in LANGUAGES else "en"


def credit() -> str:
    """'Made by Prithwiraj Mukherjee', with "Made by" translated."""
    from . import __author__
    return tr("Made by {name}", name=__author__)


def apply_direction() -> None:
    """Right-to-left layouts for Arabic. Needs a QGuiApplication."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.setLayoutDirection(Qt.RightToLeft if is_rtl() else Qt.LeftToRight)
