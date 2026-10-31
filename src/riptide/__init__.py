"""Riptide: direct, encrypted PC-to-PC file transfer in the terminal."""

from pathlib import Path
import tomllib


def _load_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject_path.exists():
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            return str(data.get("project", {}).get("version", "0.0.0"))
        except Exception:
            pass
    try:
        from importlib.metadata import version
        return version("riptide")
    except Exception:
        return "0.0.0"


__version__ = _load_version()
__all__ = ["__version__"]
