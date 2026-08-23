"""Install LVMS-STAT for the current Python FELLES user."""
from __future__ import annotations

import ensurepip
import importlib
import site
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
REQUIRED_IMPORTS = ("PyQt6", "websocket", "lvms_stat")


def _add_path_first(path: Path) -> None:
    text = str(path)
    while text in sys.path:
        sys.path.remove(text)
    sys.path.insert(0, text)


def install(
    *,
    project_dir: Path = PROJECT_DIR,
    user_site: Path | None = None,
    pip_main: Callable[[list[str]], int | None] | None = None,
    importer: Callable[[str], Any] = importlib.import_module,
) -> int:
    project = project_dir.resolve()
    if not (project / "pyproject.toml").is_file():
        raise RuntimeError("Finner ikke pyproject.toml i LVMS-STAT-mappen.")
    if not (project / "src" / "lvms_stat").is_dir():
        raise RuntimeError("Finner ikke LVMS-STAT-koden.")

    package_site = (user_site or Path(site.getusersitepackages())).resolve()
    package_site.mkdir(parents=True, exist_ok=True)
    _add_path_first(package_site)

    if pip_main is None:
        try:
            import pip  # noqa: F401
        except ImportError:
            ensurepip.bootstrap(user=True, upgrade=True)
        from pip._internal.cli.main import main as pip_main

    result = int(
        pip_main(
            [
                "install",
                "--user",
                "--upgrade",
                "--disable-pip-version-check",
                "--no-compile",
                str(project),
            ]
        )
        or 0
    )
    if result != 0:
        raise RuntimeError(f"Installasjonen stoppet med kode {result}.")

    _add_path_first(project / "src")
    importlib.invalidate_caches()
    for module_name in REQUIRED_IMPORTS:
        importer(module_name)
    print("LVMS-STAT er installert. Lukk Python FELLES og åpne det på nytt.")
    return 0


if __name__ == "__main__":
    install()
