"""Start the LVMS-STAT PyQt6 app inside Python FELLES."""
from __future__ import annotations

import importlib
import site
import sys
from collections.abc import Callable
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


def _add_path_first(path: Path) -> None:
    text = str(path)
    while text in sys.path:
        sys.path.remove(text)
    sys.path.insert(0, text)


def start(
    *,
    project_dir: Path = PROJECT_DIR,
    user_site: Path | None = None,
    app_main: Callable[[list[str]], int | None] | None = None,
) -> int:
    project = project_dir.resolve()
    config = project / "config.json"
    jobs = project / "jobs.json"
    if not (project / "src" / "lvms_stat").is_dir():
        raise RuntimeError("Finner ikke LVMS-STAT-koden.")
    if not config.is_file() or not jobs.is_file():
        raise RuntimeError("config.json og jobs.json må ligge i LVMS-STAT-mappen.")

    package_site = (user_site or Path(site.getusersitepackages())).resolve()
    _add_path_first(package_site)
    _add_path_first(project / "src")
    _add_path_first(project)
    importlib.invalidate_caches()

    if app_main is None:
        from lvms_stat.__main__ import main as app_main

    result = int(app_main(["app", "--config", str(config)]) or 0)
    if result != 0:
        raise RuntimeError(f"LVMS-STAT stoppet med kode {result}.")
    return 0


if __name__ == "__main__":
    start()
