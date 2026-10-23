import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Recipes, history and watch rules go to a temp folder, never the real profile."""
    home = tmp_path / "dropdial-home"
    monkeypatch.setenv("DROPDIAL_HOME", str(home))
    return home


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """One QApplication for the whole run. Created first, so code that would otherwise start a
    plain QGuiApplication on demand (SVG rendering) can't leave widgets without an application."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("DROPDIAL_NO_UPDATE_CHECK", "1")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
