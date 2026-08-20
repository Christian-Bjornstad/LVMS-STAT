from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class DownloadError(RuntimeError):
    """CSV detection or local opening failed without exposing a path."""


class DownloadStatus(StrEnum):
    WAITING = "waiting"
    DETECTED = "detected"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"


@dataclass(frozen=True)
class FileStamp:
    size: int
    modified_ns: int


def _stamp(path: Path) -> FileStamp:
    stat = path.stat()
    return FileStamp(stat.st_size, stat.st_mtime_ns)


class CsvArrivalDetector:
    def __init__(self, directory: Path) -> None:
        if not directory.is_absolute():
            raise DownloadError("download directory must be absolute")
        self._directory = directory.resolve()
        self._baseline: dict[Path, FileStamp] = {}
        self._pending: tuple[Path, FileStamp] | None = None
        self._detected: Path | None = None
        self._started = False

    def _scan(self) -> dict[Path, FileStamp]:
        try:
            return {
                item.resolve(): _stamp(item)
                for item in self._directory.iterdir()
                if item.is_file() and item.suffix.lower() == ".csv"
            }
        except OSError as exc:
            raise DownloadError("download directory is unavailable") from exc

    def start(self) -> None:
        self._baseline = self._scan()
        self._pending = None
        self._detected = None
        self._started = True

    def poll(self) -> DownloadStatus:
        if not self._started:
            raise DownloadError("download detector has not started")
        if self._detected is not None:
            return (
                DownloadStatus.DETECTED
                if self._detected.is_file()
                else DownloadStatus.MISSING
            )
        current = self._scan()
        new_files = {path: stamp for path, stamp in current.items() if path not in self._baseline}
        if len(new_files) > 1:
            self._pending = None
            return DownloadStatus.AMBIGUOUS
        if not new_files:
            self._pending = None
            return DownloadStatus.WAITING
        item = next(iter(new_files.items()))
        if self._pending == item:
            self._detected = item[0]
            return DownloadStatus.DETECTED
        self._pending = item
        return DownloadStatus.WAITING

    def detected_path(self) -> Path | None:
        return self._detected


def open_local(
    path: Path,
    *,
    opener: Callable[[str], object] | None = None,
) -> None:
    if not path.is_absolute() or path.suffix.lower() != ".csv" or not path.is_file():
        raise DownloadError("detected CSV is unavailable")
    active_opener = opener or getattr(os, "startfile", None)
    if active_opener is None:
        raise DownloadError("local CSV opening is unavailable")
    try:
        active_opener(str(path))
    except OSError as exc:
        raise DownloadError("local CSV opening failed") from exc
