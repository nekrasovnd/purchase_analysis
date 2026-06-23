from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from purchase_analysis import source_sprint
from purchase_analysis.config import ROOT_DIR
from purchase_analysis.utils.io import ensure_dir
from purchase_analysis.utils.text import normalize_spaces


DEFAULT_INPUT_DIR = ROOT_DIR / "output" / "source_sprints"
DEFAULT_OUTPUT_FILE = ROOT_DIR / "output" / "merged_sprints.csv"
DEFAULT_DUPLICATES_FILE = ROOT_DIR / "output" / "merged_sprints_duplicates.csv"
DEFAULT_SUMMARY_FILE = ROOT_DIR / "output" / "merged_sprints_summary.json"


def _split_batch_args(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        result.extend(part.strip() for part in value.split(",") if part.strip())
    return result


def select_batch_names(
    *,
    input_dir: Path,
    allowlist_file: Path,
    explicit_batches: list[str] | None = None,
    all_batches: bool = False,
    include_unsafe: bool = False,
) -> list[str]:
    if explicit_batches:
        selected = explicit_batches
    elif all_batches:
        selected = sorted(path.name for path in input_dir.iterdir() if path.is_dir())
    else:
        selected = source_sprint.default_merge_batch_names(allowlist_file)
        if not selected:
            raise SystemExit(
                f"No default source sprint batches found in allowlist: {allowlist_file}"
            )

    unsafe = [name for name in selected if source_sprint.is_unsafe_batch_name(name)]
    if unsafe and not include_unsafe:
        raise SystemExit(
            "Refusing to merge probe/diag/scratch batches without --include-unsafe: "
            + ", ".join(unsafe)
        )
    return selected


def load_batch_frame(batch_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    items_path = batch_dir / "items.csv"
    if not items_path.exists() or items_path.stat().st_size <= 5:
        return pd.DataFrame(), pd.DataFrame()

    frame = pd.read_csv(items_path, dtype=str, keep_default_na=False)
    normalized = source_sprint.normalize_items_frame(frame)
    normalized["sprint_batch"] = batch_dir.name
    deduped, duplicates = source_sprint.dedupe_items_frame(normalized)
    if not duplicates.empty:
        duplicates["sprint_batch"] = batch_dir.name
        duplicates["duplicate_scope"] = "within_batch"
    return deduped, duplicates


def _cross_source_key(frame: pd.DataFrame) -> pd.Series:
    procedure = frame["procedure_number"].fillna("").astype(str).map(normalize_spaces)
    lot = frame["lot_number"].fillna("").astype(str).map(normalize_spaces)
    lot = lot.mask(lot == "", "1")
    detail_url = frame["detail_url"].fillna("").astype(str).map(normalize_spaces)

    keys: list[str] = []
    for index, procedure_number in procedure.items():
        if procedure_number:
            keys.append(f"procedure:{procedure_number}|lot:{lot.loc[index]}")
        elif detail_url.loc[index]:
            keys.append(f"detail_url:{detail_url.loc[index]}")
        else:
            keys.append(f"row:{index}")
    return pd.Series(keys, index=frame.index)


def merge_frames(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not frames:
        return pd.DataFrame(), pd.DataFrame()

    merged = source_sprint.normalize_items_frame(pd.concat(frames, ignore_index=True))
    merged["_cross_source_dedupe_key"] = _cross_source_key(merged)
    duplicate_mask = merged["_cross_source_dedupe_key"].duplicated(keep="first")
    group_sizes = merged.groupby("_cross_source_dedupe_key")["_cross_source_dedupe_key"].transform("size")

    duplicate_report = merged.loc[group_sizes > 1].copy()
    if not duplicate_report.empty:
        duplicate_report["duplicate_scope"] = "cross_source"
        duplicate_report["dedupe_action"] = duplicate_mask.loc[duplicate_report.index].map(
            {True: "drop", False: "keep"}
        )
        duplicate_report["duplicate_group_size"] = group_sizes.loc[duplicate_report.index]

    final = merged.loc[~duplicate_mask].drop(columns=["_cross_source_dedupe_key"]).reset_index(drop=True)
    duplicate_report = duplicate_report.drop(columns=["_cross_source_dedupe_key"], errors="ignore").reset_index(
        drop=True
    )
    return source_sprint.reorder_item_columns(final), source_sprint.reorder_item_columns(duplicate_report)


def build_summary(
    *,
    selected_batches: list[str],
    loaded_counts: dict[str, int],
    local_duplicate_count: int,
    cross_duplicate_count: int,
    final_count: int,
) -> dict[str, object]:
    return {
        "selected_batches": selected_batches,
        "loaded_counts": loaded_counts,
        "rows_before_cross_source_dedupe": sum(loaded_counts.values()),
        "within_batch_duplicates": local_duplicate_count,
        "cross_source_duplicates_dropped": cross_duplicate_count,
        "rows_after_cross_source_dedupe": final_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge allowlisted source sprint items.csv files. "
            "Default mode intentionally ignores probe/diag/scratch batches."
        )
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--duplicates-file", type=Path, default=DEFAULT_DUPLICATES_FILE)
    parser.add_argument("--summary-file", type=Path, default=DEFAULT_SUMMARY_FILE)
    parser.add_argument("--allowlist-file", type=Path, default=source_sprint.DEFAULT_SOURCE_SPRINT_ALLOWLIST)
    parser.add_argument(
        "--source-sprint",
        action="append",
        default=[],
        help="Explicit batch name. Can be repeated or comma-separated.",
    )
    parser.add_argument("--all", action="store_true", help="Merge every directory under input-dir.")
    parser.add_argument(
        "--include-unsafe",
        action="store_true",
        help="Allow probe/diag/scratch/test batch names. Intended only for audits.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing files.")
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {args.input_dir}")

    explicit_batches = _split_batch_args(args.source_sprint)
    selected_batches = select_batch_names(
        input_dir=args.input_dir,
        allowlist_file=args.allowlist_file,
        explicit_batches=explicit_batches or None,
        all_batches=args.all,
        include_unsafe=args.include_unsafe,
    )

    frames: list[pd.DataFrame] = []
    local_duplicate_frames: list[pd.DataFrame] = []
    loaded_counts: dict[str, int] = {}

    for batch_name in selected_batches:
        batch_dir = args.input_dir / batch_name
        if not batch_dir.exists():
            print(f"[WARN] missing batch directory: {batch_name}")
            loaded_counts[batch_name] = 0
            continue
        frame, local_duplicates = load_batch_frame(batch_dir)
        loaded_counts[batch_name] = len(frame)
        if not frame.empty:
            frames.append(frame)
        if not local_duplicates.empty:
            local_duplicate_frames.append(local_duplicates)
        print(f"Loaded {len(frame)} unique rows from {batch_name}")

    final, cross_duplicates = merge_frames(frames)
    local_duplicates = (
        pd.concat(local_duplicate_frames, ignore_index=True)
        if local_duplicate_frames
        else pd.DataFrame()
    )
    duplicate_report = pd.concat(
        [df for df in [local_duplicates, cross_duplicates] if not df.empty],
        ignore_index=True,
    ) if (not local_duplicates.empty or not cross_duplicates.empty) else pd.DataFrame()

    summary = build_summary(
        selected_batches=selected_batches,
        loaded_counts=loaded_counts,
        local_duplicate_count=len(local_duplicates),
        cross_duplicate_count=sum(1 for value in cross_duplicates.get("dedupe_action", []) if value == "drop"),
        final_count=len(final),
    )

    print("\n--- MERGE SUMMARY ---")
    for key, value in summary.items():
        print(f"{key}: {value}")

    if args.dry_run:
        print("Dry run: no files written.")
        return

    ensure_dir(args.output_file.parent)
    final.to_csv(args.output_file, index=False, encoding="utf-8-sig")
    if not duplicate_report.empty:
        ensure_dir(args.duplicates_file.parent)
        duplicate_report.to_csv(args.duplicates_file, index=False, encoding="utf-8-sig")
    ensure_dir(args.summary_file.parent)
    args.summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"File saved to: {args.output_file}")
    if not duplicate_report.empty:
        print(f"Duplicate report saved to: {args.duplicates_file}")
    print(f"Summary saved to: {args.summary_file}")


if __name__ == "__main__":
    main()
