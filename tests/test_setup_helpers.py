"""Task 6: the Oppsett page must show whether each configured folder
actually exists (the user could not tell which paths were real), and
must offer one-click restore of the built-in analysis-code lists."""

from __future__ import annotations

from pathlib import Path

from lvms_stat.qt_app import default_codes_text, path_status


def test_path_status_reports_existing_directory(tmp_path: Path) -> None:
    assert path_status(str(tmp_path)) == "✓ mappen finnes"


def test_path_status_flags_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "finnes-ikke"
    text = path_status(str(missing))
    assert text.startswith("⚠")
    assert "opprettes automatisk" in text


def test_path_status_empty_is_neutral() -> None:
    assert path_status("") == ""


def test_default_codes_text_lists_every_code_one_per_line() -> None:
    text = default_codes_text("solide")
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 70
    assert "BRCA1-OU" in lines
    # One code per line - never comma-joined onto one line.
    assert "," not in text


def test_default_codes_text_unknown_unit_is_empty() -> None:
    assert default_codes_text("finnes-ikke") == ""
