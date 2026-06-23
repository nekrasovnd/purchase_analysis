from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.config import CONFIG_DIR, OUTPUT_DIR
from purchase_analysis.utils.io import ensure_dir
from purchase_analysis.utils.text import normalize_spaces


DATE_SCOPE_START = date(2024, 1, 1)
DATE_SCOPE_END = date(2025, 12, 31)
DATE_FROM_DMY = "01.01.2024"
DATE_TO_DMY = "31.12.2025"
DATE_FROM_ISO = "2024-01-01"
DATE_TO_ISO = "2025-12-31"
DATE_FROM_DT = datetime.combine(DATE_SCOPE_START, time.min)
DATE_TO_DT = datetime.combine(DATE_SCOPE_END, time.max.replace(microsecond=0))

DEFAULT_SOURCE_SPRINTS_DIR = OUTPUT_DIR / "source_sprints"
DEFAULT_SOURCE_SPRINT_ALLOWLIST = CONFIG_DIR / "source_sprints_allowlist.csv"
DEFAULT_SOURCE_SPRINT_MANIFEST = CONFIG_DIR / "source_sprints_manifest.csv"

STANDARD_ITEM_COLUMNS = [
    "source_system",
    "platform_section",
    "entity_name",
    "customer_query",
    "procedure_number",
    "lot_number",
    "subject",
    "customer_name",
    "customer_inn",
    "region",
    "status",
    "tender_type",
    "price_rub",
    "deadline_at",
    "detail_url",
    "tags",
    "published_at",
    "application_deadline",
    "method_name",
    "currency",
    "organizer_name",
    "organizer_inn",
]

_COLUMN_ALIASES = {
    "source": "source_system",
    "url": "detail_url",
    "title": "subject",
    "amount": "price_text",
    "stage": "status",
    "date_published": "published_at",
    "company_name": "customer_name",
    "company_inn": "customer_inn",
}

UNSAFE_BATCH_NAME_MARKERS = (
    "probe",
    "diag",
    "diagnostic",
    "scratch",
    "test",
    "_slug_test",
)


@dataclass(frozen=True, slots=True)
class SourceSprintBatch:
    batch_name: str
    source_system: str
    status: str
    include_in_default_merge: bool
    notes: str = ""


@dataclass(frozen=True, slots=True)
class SourceSprintManifestEntry:
    batch_name: str
    source_system: str
    status: str
    include_in_default_merge: bool
    has_items: bool
    item_rows: int
    unique_procedure_numbers: int
    unique_lot_keys: int
    raw_source: str = ""
    raw_exists: bool = False
    notes: str = ""


def read_scope(
    selected_inns: set[str] | None = None,
    *,
    scope_path: Path | None = None,
) -> list[entity_resolution.EntityIdentity]:
    rows = entity_resolution.load_entity_scope(scope_path or CONFIG_DIR / "entity_scope.csv")
    if not selected_inns:
        return rows
    selected = {entity_resolution.normalize_identifier(value) for value in selected_inns}
    return [row for row in rows if row.inn in selected]


def is_unsafe_batch_name(batch_name: str) -> bool:
    normalized = batch_name.casefold()
    return any(marker in normalized for marker in UNSAFE_BATCH_NAME_MARKERS)


def load_source_sprint_allowlist(path: Path = DEFAULT_SOURCE_SPRINT_ALLOWLIST) -> list[SourceSprintBatch]:
    if not path.exists():
        return []
    batches: list[SourceSprintBatch] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            batch_name = normalize_spaces(row.get("batch_name"))
            if not batch_name:
                continue
            include_raw = normalize_spaces(row.get("include_in_default_merge")).casefold()
            batches.append(
                SourceSprintBatch(
                    batch_name=batch_name,
                    source_system=normalize_spaces(row.get("source_system")),
                    status=normalize_spaces(row.get("status")),
                    include_in_default_merge=include_raw in {"1", "true", "yes", "y"},
                    notes=normalize_spaces(row.get("notes")),
                )
            )
    return batches


def _parse_int(value: str | None) -> int:
    try:
        return int(normalize_spaces(value) or "0")
    except ValueError:
        return 0


def _parse_flag(value: str | None) -> bool:
    return normalize_spaces(value).casefold() in {"1", "true", "yes", "y"}


def load_source_sprint_manifest(
    path: Path = DEFAULT_SOURCE_SPRINT_MANIFEST,
) -> list[SourceSprintManifestEntry]:
    if not path.exists():
        return []
    entries: list[SourceSprintManifestEntry] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            batch_name = normalize_spaces(row.get("batch_name"))
            if not batch_name:
                continue
            entries.append(
                SourceSprintManifestEntry(
                    batch_name=batch_name,
                    source_system=normalize_spaces(row.get("source_system")),
                    status=normalize_spaces(row.get("status")),
                    include_in_default_merge=_parse_flag(row.get("include_in_default_merge")),
                    has_items=_parse_flag(row.get("has_items")),
                    item_rows=_parse_int(row.get("item_rows")),
                    unique_procedure_numbers=_parse_int(row.get("unique_procedure_numbers")),
                    unique_lot_keys=_parse_int(row.get("unique_lot_keys")),
                    raw_source=normalize_spaces(row.get("raw_source")),
                    raw_exists=_parse_flag(row.get("raw_exists")),
                    notes=normalize_spaces(row.get("notes")),
                )
            )
    return entries


def default_merge_batch_names(path: Path = DEFAULT_SOURCE_SPRINT_ALLOWLIST) -> list[str]:
    return [batch.batch_name for batch in load_source_sprint_allowlist(path) if batch.include_in_default_merge]


def normalize_item_row(row: dict[str, object], *, default_source_system: str = "") -> dict[str, object]:
    normalized: dict[str, object] = dict(row)
    for old_name, new_name in _COLUMN_ALIASES.items():
        if old_name in normalized and new_name not in normalized:
            normalized[new_name] = normalized[old_name]

    if default_source_system and not normalize_spaces(str(normalized.get("source_system", ""))):
        normalized["source_system"] = default_source_system
    if not normalize_spaces(str(normalized.get("lot_number", ""))):
        normalized["lot_number"] = "1"
    if "detail_url" not in normalized and "url" in normalized:
        normalized["detail_url"] = normalized["url"]
    if "subject" not in normalized and "title" in normalized:
        normalized["subject"] = normalized["title"]

    for column in STANDARD_ITEM_COLUMNS:
        normalized.setdefault(column, "")
    return normalized


def normalize_item_rows(
    rows: Iterable[dict[str, object]],
    *,
    default_source_system: str = "",
) -> list[dict[str, object]]:
    return [
        normalize_item_row(row, default_source_system=default_source_system)
        for row in rows
    ]


def normalize_items_frame(
    frame: pd.DataFrame,
    *,
    default_source_system: str = "",
) -> pd.DataFrame:
    rows = normalize_item_rows(frame.to_dict("records"), default_source_system=default_source_system)
    result = pd.DataFrame(rows)
    return reorder_item_columns(result)


def reorder_item_columns(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = [column for column in STANDARD_ITEM_COLUMNS if column in frame.columns]
    extra = [column for column in frame.columns if column not in ordered]
    return frame[ordered + extra] if ordered or extra else frame


def _dedupe_key_series(frame: pd.DataFrame) -> pd.Series:
    procedure = frame["procedure_number"].fillna("").astype(str).map(normalize_spaces)
    lot = frame["lot_number"].fillna("").astype(str).map(normalize_spaces)
    lot = lot.mask(lot == "", "1")
    return procedure + "|" + lot


def dedupe_items_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        return reorder_item_columns(frame.copy()), frame.copy()

    work = normalize_items_frame(frame)
    procedure = work["procedure_number"].fillna("").astype(str).map(normalize_spaces)
    has_procedure = procedure != ""
    duplicate_mask = pd.Series(False, index=work.index)

    if has_procedure.any():
        keys = _dedupe_key_series(work.loc[has_procedure])
        duplicate_mask.loc[has_procedure] = keys.duplicated(keep="first")

    no_procedure = ~has_procedure
    if no_procedure.any() and "detail_url" in work.columns:
        urls = work.loc[no_procedure, "detail_url"].fillna("").astype(str).map(normalize_spaces)
        has_url = urls != ""
        if has_url.any():
            duplicate_mask.loc[urls[has_url].index] = urls[has_url].duplicated(keep="first")

    duplicates = work.loc[duplicate_mask].copy()
    deduped = work.loc[~duplicate_mask].drop_duplicates().reset_index(drop=True)
    return reorder_item_columns(deduped), reorder_item_columns(duplicates.reset_index(drop=True))


def write_items_csv(
    path: Path,
    rows: Sequence[dict[str, object]],
    *,
    default_source_system: str = "",
) -> pd.DataFrame:
    if rows:
        frame = pd.DataFrame(normalize_item_rows(rows, default_source_system=default_source_system))
    else:
        frame = pd.DataFrame(columns=STANDARD_ITEM_COLUMNS)
    deduped, _duplicates = dedupe_items_frame(frame)
    if deduped.empty:
        deduped = pd.DataFrame(columns=STANDARD_ITEM_COLUMNS)
    ensure_dir(path.parent)
    deduped.to_csv(path, index=False, encoding="utf-8-sig")
    return deduped


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    ensure_dir(path.parent)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame
