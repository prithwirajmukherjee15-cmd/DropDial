import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Recipes, history and watch rules go to a temp folder, never the real profile."""
    home = tmp_path / "dropdial-home"
    monkeypatch.setenv("DROPDIAL_HOME", str(home))
    return home
