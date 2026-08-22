"""Local (non-K:) test run of the whole pipeline.

Simulates the K: statistics share under ``%LOCALAPPDATA%\\LVMS-STAT\\
statistikk-test`` so everything can be exercised without the network
drive. On the work PC, set ``LVMS_STATISTICS_ROOT`` to the real K: path
and the exact same code runs against the share.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

from lvms_stat.merge_raw import merge_report_csvs, write_merged_csv  # noqa: E402
from lvms_stat.post_processing import process_unit  # noqa: E402

# Local stand-in for K:\...\Statistikk
TEST_ROOT = (
    Path.home() / "AppData" / "Local" / "LVMS-STAT" / "statistikk-test"
)
SOURCE_DATA = Path("C:/Users/molpa/Downloads/Statistikk")

UNIT = "hemato"
REPORT_IDS = {
    "ordered": "PAT-DIT-ANTALL-OU",
    "answered": "PAT-DIT-RESULTATER-OU",
    "extraction": "PAT-DIT-EKSTRAKSJON-OU",
}


def seed_archives() -> None:
    """Copy the real raw exports into the archive layout as if they were
    fetched by two overlapping incremental runs."""
    raa = TEST_ROOT / UNIT / "raa"
    raa.mkdir(parents=True, exist_ok=True)
    windows = [
        ("20240101", "20241231"),
        ("20241225", "20250630"),   # 7-day overlap on purpose
        ("20250620", "20260822"),
    ]
    for role, report_id in REPORT_IDS.items():
        source = SOURCE_DATA / f"{report_id}.csv"
        for i, (frm, to) in enumerate(windows):
            target = raa / report_id / f"{report_id}__{frm}__{to}.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(source, target)
        print(f"seeded {role}: 3 windows -> {raa / report_id}")


def main() -> int:
    lookup = SOURCE_DATA / "Analyse_lookup.xlsx"
    if not lookup.exists():
        print(f"MISSING lookup: {lookup}")
        return 2

    seed_archives()

    outcome = process_unit(TEST_ROOT / UNIT, lookup, REPORT_IDS)
    print()
    print("=== RESULT ===")
    print(f"merged files      : {outcome.merged_files}")
    print(f"resultater rows   : {outcome.resultater_rows}")
    print(f"antall rows       : {outcome.antall_rows}")
    print(f"output dir        : {outcome.output_dir}")

    for name in ("resultater.csv", "antall.csv"):
        path = outcome.output_dir / name
        if not path.exists():
            print(f"MISSING output: {path}")
            return 1
        raw = path.read_bytes()
        ok_bom = raw.startswith(b"\xef\xbb\xbf")
        lines = raw.decode("utf-8-sig").splitlines()
        cols = lines[0].split(";") if lines else []
        print(f"{name}: {len(lines) - 1} rows, {len(cols)} columns, "
              f"BOM={ok_bom}")

    # sanity: compare against R's own processed output
    import csv

    def load(p):
        with open(p, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f, delimiter=";"))

    ref_dir = SOURCE_DATA / "Prosessert"
    for name in ("resultater", "antall"):
        ref = load(ref_dir / f"{name}.csv")
        new = load(outcome.output_dir / f"{name}.csv")
        n = min(len(ref), len(new))
        mismatches = sum(
            1
            for i in range(n)
            for col in ref[0]
            if ref[i].get(col, "") != new[i].get(col, "")
        )
        print(f"{name}: vs R-output -> {len(new)} rows "
              f"(R had {len(ref)}), cell mismatches: {mismatches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
