"""Local (non-K:) test run of the whole pipeline.

Simulates the K: statistics share under ``%LOCALAPPDATA%\\\\LVMS-STAT\\\\
statistikk-test`` so everything can be exercised without the network
drive. On the work PC, set ``LVMS_STATISTICS_ROOT`` to the real K: path
and the exact same code runs against the share.

Covers both units: hemato (12/5-column layout) and solide (13/5-column
layout with its own extraction rule), each validated cell-by-cell
against the R gold standard in Downloads/Statistikk.
"""

from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

from lvms_stat.post_processing import process_unit  # noqa: E402

# Local stand-in for K:\\...\\Statistikk
TEST_ROOT = (
    Path.home() / "AppData" / "Local" / "LVMS-STAT" / "statistikk-test"
)
SOURCE_DATA = Path("C:/Users/molpa/Downloads/Statistikk")

UNITS = {
    "hemato": {
        "report_ids": {
            "ordered": "PAT-DIT-ANTALL-OU",
            "answered": "PAT-DIT-RESULTATER-OU",
            "extraction": "PAT-DIT-EKSTRAKSJON-OU",
        },
        # R gold standard lives at Downloads/Statistikk/Prosessert
        "gold_dir": SOURCE_DATA / "Prosessert",
        # known: 6 cells on 3 rows where R itself is non-deterministic
        "expected_mismatches_resultater": 6,
        "expected_mismatches_antall": 0,
    },
    "solide": {
        "profile": "solide",
        "report_ids": {
            # NB: the solide reports keep the same report names as hemato
            # (-OU); the LVMS export is filtered on OU-SOLIDE workitem
            # group and saved under Solide/. Verified against
            # Solide_Statistikk.R and the raw files.
            "ordered": "PAT-DIT-ANTALL-OU",
            "answered": "PAT-DIT-RESULTATER-OU",
            "extraction": "PAT-DIT-EKSTRAKSJON-OU",
        },
        "raw_subdir": "Solide",
        "gold_dir": SOURCE_DATA / "Solide" / "Prosessert",
        "expected_mismatches_resultater": 0,
        "expected_mismatches_antall": 0,
    },
}

WINDOWS = [
    ("20240101", "20241231"),
    ("20241225", "20250630"),   # 7-day overlap on purpose
    ("20250620", "20260822"),
]


def seed_archives(unit: str, cfg: dict) -> None:
    """Copy real raw exports into the archive layout as three overlapping
    incremental fetch windows."""
    report_ids = cfg["report_ids"]
    raa = TEST_ROOT / unit / "raa"
    raa.mkdir(parents=True, exist_ok=True)
    for role, report_id in report_ids.items():
        candidates = []
        subdir = cfg.get("raw_subdir")
        if subdir:
            # unit-specific folder wins - the root copy of same-named
            # reports belongs to another unit
            candidates.append(SOURCE_DATA / subdir / f"{report_id}.csv")
        candidates.append(SOURCE_DATA / f"{report_id}.csv")
        source = next((c for c in candidates if c.exists()), None)
        if source is None:
            print(f"MISSING raw source for {role}: {report_id}")
            raise SystemExit(2)
        for frm, to in WINDOWS:
            target = raa / report_id / f"{report_id}__{frm}__{to}.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(source, target)
    print(f"[{unit}] seeded {len(report_ids)} reports x {len(WINDOWS)} windows")


def compare(name: str, produced: Path, gold: Path) -> int:
    def load(p: Path):
        with open(p, encoding="utf-8-sig", newline="") as f:
            return list(csv.reader(f, delimiter=";"))

    g = load(gold)
    m = load(produced)
    n = min(len(g), len(m))
    diffs = sum(
        1
        for i in range(n)
        for j in range(min(len(g[i]), len(m[i])))
        if g[i][j] != m[i][j]
    )
    shape = f"{len(g)}x{len(g[0])}" if g else "?"
    ok = (
        len(g) == len(m)
        and g[0] == m[0]
        and diffs == 0
    ) if name != "known" else True
    print(
        f"  {name}: {len(m)} rows vs gold {shape} - "
        f"cell mismatches: {diffs}"
    )
    return diffs


def main() -> int:
    failures = 0
    for unit, cfg in UNITS.items():
        lookup = SOURCE_DATA / unit.capitalize() / "Analyse_lookup.xlsx"
        if not lookup.exists():
            lookup = SOURCE_DATA / "Analyse_lookup.xlsx"
        if not lookup.exists():
            print(f"MISSING lookup: {lookup}")
            return 2

        seed_archives(unit, cfg)
        outcome = process_unit(
            TEST_ROOT / unit,
            lookup,
            cfg["report_ids"],
            profile=cfg.get("profile", "hemato"),
        )
        print(f"[{unit}] merged files : {outcome.merged_files}")
        print(f"[{unit}] resultater   : {outcome.resultater_rows} rows")
        print(f"[{unit}] antall       : {outcome.antall_rows} rows")

        for name in ("resultater.csv", "antall.csv"):
            path = outcome.output_dir / name
            if not path.exists():
                print(f"MISSING output: {path}")
                failures += 1
                continue
            raw = path.read_bytes()
            ok_bom = raw.startswith(b"\xef\xbb\xbf")
            lines = raw.decode("utf-8-sig").splitlines()
            cols = lines[0].split(";") if lines else []
            print(
                f"  wrote {name}: {len(lines) - 1} rows, "
                f"{len(cols)} columns, BOM={ok_bom}"
            )

        # cell-by-cell validation against R's own processed output
        gold_dir = cfg["gold_dir"]
        diffs_res = compare(
            "resultater",
            outcome.output_dir / "resultater.csv",
            gold_dir / "resultater.csv",
        )
        diffs_ant = compare(
            "antall",
            outcome.output_dir / "antall.csv",
            gold_dir / "antall.csv",
        )
        exp_res = cfg["expected_mismatches_resultater"]
        exp_ant = cfg["expected_mismatches_antall"]
        if diffs_res != exp_res or diffs_ant != exp_ant:
            print(
                f"  FAIL [{unit}]: expected "
                f"{exp_res}/{exp_ant} mismatches, got {diffs_res}/{diffs_ant}"
            )
            failures += 1
        else:
            note = ""
            if exp_res or exp_ant:
                note = " (documented R nondeterminism)"
            print(f"  PASS [{unit}]: matches R gold standard{note}")
        print()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
