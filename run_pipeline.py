"""
run_pipeline.py — Единая точка запуска всего пайплайна.

Шаги:
  1. Парсинг Sberbank-AST
  2. Парсинг B2B-Center
  3. Парсинг ЕИС (контрольный источник)
  4. Merge + дедупликация -> output/merged_sprints.csv
  5. Экспорт в SQLite -> purchase_analysis.db

Использование:
  python run_pipeline.py                 # полный прогон
  python run_pipeline.py --step merge    # только merge + sqlite (если батчи уже собраны)
  python run_pipeline.py --dry-run       # только проверка merge без записи файлов
"""

import argparse
import datetime
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PYTHON = sys.executable

SOURCES = [
    {
        "name": "Sberbank-AST",
        "script": "scripts/sberbank_ast_prompt2_source_sprint_v2.py",
        "batch_flag": "--batch-name",
        "inns_flag": "--inns",
    },
    {
        "name": "B2B-Center",
        "script": "scripts/b2b_center_prompt2_source_sprint_v2.py",
        "batch_flag": "--batch-name",
        "inns_flag": "--inns",
    },
    {
        "name": "EIS",
        "script": "scripts/eis_prompt2_source_sprint_v2.py",
        "batch_flag": "--batch-name",
        "inns_flag": "--inns",
    },
]


def run(cmd: list[str], label: str) -> int:
    print(f"\n{'='*60}")
    print(f"  STEP: {label}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"\n[ERROR] Step '{label}' failed with exit code {result.returncode}")
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Purchase Analysis Pipeline")
    parser.add_argument(
        "--step",
        choices=["parse", "merge", "sqlite", "all"],
        default="all",
        help="Какой шаг выполнить: parse, merge, sqlite, all (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Проверить merge без записи файлов (только шаг merge)",
    )
    parser.add_argument(
        "--batch-suffix",
        default=datetime.date.today().strftime("%Y-%m-%d"),
        help="Суффикс для имён батчей (default: текущая дата YYYY-MM-DD)",
    )
    args = parser.parse_args()

    errors = 0

    # ── 1. Парсинг ────────────────────────────────────────────────────────────
    if args.step in ("parse", "all") and not args.dry_run:
        for src in SOURCES:
            batch_name = f"pipeline-{src['name'].lower().replace(' ', '-').replace('/', '-')}-{args.batch_suffix}"
            cmd = [
                PYTHON,
                str(ROOT / src["script"]),
                src["batch_flag"],
                batch_name,
                src["inns_flag"],
                "all",
            ]
            errors += run(cmd, f"Parsing {src['name']}")

    # ── 2. Merge ──────────────────────────────────────────────────────────────
    if args.step in ("merge", "all") or args.dry_run:
        merge_cmd = [PYTHON, str(ROOT / "scripts/merge_sprints.py")]
        if args.dry_run:
            merge_cmd.append("--dry-run")
        errors += run(merge_cmd, "Merge + Deduplication")

    # ── 3. SQLite ─────────────────────────────────────────────────────────────
    if args.step in ("sqlite", "all") and not args.dry_run:
        errors += run([PYTHON, str(ROOT / "export_to_sqlite.py")], "Export to SQLite")

    print(f"\n{'='*60}")
    if errors == 0:
        print("  PIPELINE COMPLETE — no errors.")
    else:
        print(f"  PIPELINE FINISHED WITH {errors} ERROR(S).")
    print(f"{'='*60}\n")

    sys.exit(errors)


if __name__ == "__main__":
    main()
