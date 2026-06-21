from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from purchase_analysis.clients import b2b_center
from purchase_analysis.utils.io import ensure_dir
from purchase_analysis.utils.text import normalize_spaces


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ITEMS = ROOT_DIR / "output" / "source_sprints" / "b2b_center_probe_7736663049" / "items.csv"
DEFAULT_DETAIL_DIR = ROOT_DIR / "data" / "raw" / "b2b_center" / "b2b_center_probe_7736663049"
DEFAULT_OUTPUT = ROOT_DIR / "output" / "source_sprints" / "b2b_center_probe_7736663049" / "items_reenriched.csv"


def locate_detail_file(row: dict[str, str], detail_dir: Path) -> Path | None:
    procedure_number = normalize_spaces(row.get("procedure_number"))
    role_mode = normalize_spaces(row.get("role_mode"))
    if not procedure_number:
        return None

    patterns = [
        f"*{procedure_number}-{role_mode}_detail.html" if role_mode else "",
        f"*{procedure_number}*_detail.html",
    ]
    for pattern in patterns:
        if not pattern:
            continue
        matches = sorted(detail_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def apply_detail(row: dict[str, str], detail: b2b_center.B2BCenterProcedureDetail) -> dict[str, str]:
    row["detail_subject"] = detail.subject or row.get("detail_subject", "")
    row["detail_category"] = detail.category
    row["detail_quantity_text"] = detail.quantity_text
    row["detail_total_price_text"] = detail.total_price_text
    row["detail_total_price_rub"] = "" if detail.total_price_rub is None else str(detail.total_price_rub)
    row["detail_currency"] = detail.currency
    row["detail_published_at"] = detail.published_at or ""
    row["detail_deadline_at"] = detail.deadline_at or ""
    row["detail_organizer_name"] = detail.organizer_name
    row["detail_organizer_profile_url"] = detail.organizer_profile_url
    row["detail_procedure_status"] = detail.procedure_status
    row["detail_price_note"] = detail.price_note
    row["detail_location"] = detail.location
    if detail.total_price_rub is not None:
        row["price_rub"] = str(detail.total_price_rub)
        row["currency"] = detail.currency or row.get("currency", "")
        row["price_source"] = "b2b_center_detail"
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-enrich saved B2B-Center items from local detail HTML files.")
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--detail-dir", type=Path, default=DEFAULT_DETAIL_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    frame = pd.read_csv(args.items, dtype=str, keep_default_na=False)
    rows = frame.to_dict("records")

    parsed_count = 0
    priced_count = 0
    blocked_count = 0
    missing_count = 0

    for row in rows:
        detail_file = locate_detail_file(row, args.detail_dir)
        if detail_file is None:
            missing_count += 1
            continue
        try:
            detail = b2b_center.parse_procedure_detail(
                detail_file.read_text(encoding="utf-8"),
                detail_url=normalize_spaces(row.get("detail_url")),
            )
        except ValueError as exc:
            row["detail_error"] = str(exc)
            blocked_count += 1
            continue

        apply_detail(row, detail)
        parsed_count += 1
        if detail.total_price_rub is not None:
            priced_count += 1

    result = pd.DataFrame(rows)
    ensure_dir(args.output.parent)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"items={len(rows)}")
    print(f"parsed={parsed_count}")
    print(f"priced={priced_count}")
    print(f"blocked={blocked_count}")
    print(f"missing_detail_files={missing_count}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
