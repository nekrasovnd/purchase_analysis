from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from purchase_analysis.config import CONFIG_DIR, CURATED_DIR, OUTPUT_DIR, ROOT_DIR
from purchase_analysis.entity_resolution import (
    normalize_identifier,
    normalize_name,
    normalize_name_without_legal_form,
    remove_parenthetical,
    split_multi,
    strip_legal_form,
)
from purchase_analysis.utils.text import normalize_spaces


SCHEMA_SQL_DIR = ROOT_DIR / "db" / "ddl"
VIEWS_SQL_DIR = ROOT_DIR / "db" / "views"
MARTS_SQL_DIR = ROOT_DIR / "db" / "marts"
SOURCE_SPRINTS_DIR = OUTPUT_DIR / "source_sprints"


@dataclass(slots=True)
class CuratedSnapshot:
    entity_scope: pd.DataFrame
    entity_coverage: pd.DataFrame
    entity_source_links: pd.DataFrame
    source_assessment: pd.DataFrame
    integration_probe: pd.DataFrame
    procurement_lots: pd.DataFrame
    procurement_items: pd.DataFrame
    document_links: pd.DataFrame
    document_texts: pd.DataFrame
    procurement_participants: pd.DataFrame
    external_factors_daily: pd.DataFrame
    enrichment_candidates: pd.DataFrame


@dataclass(slots=True)
class PostgresLoadSummary:
    database: str
    load_audit_id: int | None
    entity_scope_rows: int
    entity_identity_enrichment_rows: int
    entity_source_link_rows: int
    source_assessment_rows: int
    integration_probe_rows: int
    procurement_lot_rows: int
    procurement_item_rows: int
    document_link_rows: int
    document_text_rows: int
    procurement_participant_rows: int
    external_factor_daily_rows: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "load_audit_id": self.load_audit_id,
            "entity_scope_rows": self.entity_scope_rows,
            "entity_identity_enrichment_rows": self.entity_identity_enrichment_rows,
            "entity_source_link_rows": self.entity_source_link_rows,
            "source_assessment_rows": self.source_assessment_rows,
            "integration_probe_rows": self.integration_probe_rows,
            "procurement_lot_rows": self.procurement_lot_rows,
            "procurement_item_rows": self.procurement_item_rows,
            "document_link_rows": self.document_link_rows,
            "document_text_rows": self.document_text_rows,
            "procurement_participant_rows": self.procurement_participant_rows,
            "external_factor_daily_rows": self.external_factor_daily_rows,
        }


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype="string")
    except EmptyDataError:
        return pd.DataFrame()


def _normalize_key(value: object) -> str:
    return normalize_spaces("" if value is None else str(value)).strip().lower()


def _string_value(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return normalize_spaces(str(value))


def _strict_name_variants(value: object) -> set[str]:
    raw_value = _string_value(value)
    if not raw_value:
        return set()
    candidates = {
        normalize_name(raw_value),
        normalize_name(remove_parenthetical(raw_value)),
    }
    return {candidate for candidate in candidates if candidate}


def _relaxed_name_variants(value: object) -> set[str]:
    raw_value = _string_value(value)
    if not raw_value:
        return set()
    candidates = {
        normalize_name(strip_legal_form(raw_value)),
        normalize_name_without_legal_form(raw_value),
    }
    return {candidate for candidate in candidates if candidate}


def _name_variants(value: object) -> set[str]:
    return _strict_name_variants(value).union(_relaxed_name_variants(value))


def _multi_value_tokens(value: object) -> list[str]:
    return split_multi(_string_value(value))


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = pd.NA
    return result


def _coerce_bool(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype("string").str.strip().str.lower()
    return normalized.isin({"1", "true", "t", "yes", "y", "да"})


def _coerce_int(series: pd.Series, default: int = 0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default).astype(int)


def _coerce_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _coerce_datetime(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", format="mixed", utc=True)
    return parsed.dt.tz_convert(None)


def _coerce_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", format="mixed").dt.date


def _python_scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def _frame_records(df: pd.DataFrame, columns: list[str]) -> list[tuple[Any, ...]]:
    rows = df.reindex(columns=columns)
    return [tuple(_python_scalar(value) for value in row) for row in rows.itertuples(index=False, name=None)]


def load_curated_snapshot(
    *,
    scope_path: Path = CONFIG_DIR / "entity_scope.csv",
    curated_dir: Path = CURATED_DIR,
    source_sprints_dir: Path = SOURCE_SPRINTS_DIR,
    include_enrichment: bool = True,
) -> CuratedSnapshot:
    scope_path = Path(scope_path)
    curated_dir = Path(curated_dir)
    source_sprints_dir = Path(source_sprints_dir)
    enrichment_df = pd.DataFrame()
    if include_enrichment and source_sprints_dir.exists():
        enrichment_frames = []
        for csv_path in sorted(source_sprints_dir.rglob("identity_enrichment_candidates.csv")):
            frame = _read_csv(csv_path)
            if not frame.empty:
                frame["source_artifact"] = str(csv_path)
                enrichment_frames.append(frame)
        if enrichment_frames:
            enrichment_df = pd.concat(enrichment_frames, ignore_index=True, sort=False)
    return CuratedSnapshot(
        entity_scope=_read_csv(scope_path),
        entity_coverage=_read_csv(curated_dir / "entity_coverage.csv"),
        entity_source_links=_read_csv(curated_dir / "entity_source_links.csv"),
        source_assessment=_read_csv(curated_dir / "source_assessment.csv"),
        integration_probe=_read_csv(curated_dir / "etp_integration_probe.csv"),
        procurement_lots=_read_csv(curated_dir / "procurement_lots.csv"),
        procurement_items=_read_csv(curated_dir / "procurement_items.csv"),
        document_links=_read_csv(curated_dir / "document_links.csv"),
        document_texts=_read_csv(curated_dir / "document_texts.csv"),
        procurement_participants=_read_csv(curated_dir / "procurement_participants.csv"),
        external_factors_daily=_read_csv(curated_dir / "external_factors_daily.csv"),
        enrichment_candidates=enrichment_df,
    )


def build_entity_scope_load_frame(scope_df: pd.DataFrame, coverage_df: pd.DataFrame) -> pd.DataFrame:
    base_columns = [
        "entity_key",
        "group_name",
        "entity_name",
        "entity_type",
        "inn",
        "ogrn",
        "kpp_list",
        "official_name",
        "short_name",
        "brand_aliases",
        "search_terms",
        "eis_search_term",
        "roseltorg_customer_query",
        "is_priority_focus",
        "identity_source",
        "identity_confidence",
        "notes",
    ]
    coverage_columns = [
        "entity_name",
        "group_name",
        "entity_type",
        "inn",
        "is_priority_focus",
        "eis_search_term",
        "roseltorg_customer_query",
        "resolved_inn",
        "eis_entity_code",
        "eis_entity_name",
        "eis_resolved_inn",
        "eis_resolved_kpp",
        "eis_resolved_ogrn",
        "eis_fz94id",
        "eis_fz223id",
        "eis_223_open_count",
        "eis_results_url",
        "roseltorg_lot_count",
        "sberbank_ast_candidate_count",
        "sberbank_ast_lot_count",
        "zakazrf_candidate_count",
        "zakazrf_lot_count",
        "lot_online_lot_count",
        "lot_online_title_mention_count",
    ]
    scope = _ensure_columns(scope_df, base_columns).copy()
    coverage = _ensure_columns(coverage_df, coverage_columns).copy()
    scope["entity_name_key"] = scope["entity_name"].map(_normalize_key)
    coverage["entity_name_key"] = coverage["entity_name"].map(_normalize_key)
    merged = scope.merge(
        coverage.drop(columns=["entity_name"]),
        on="entity_name_key",
        how="left",
        suffixes=("", "_coverage"),
    )

    for column in ["group_name", "entity_type", "inn", "eis_search_term", "roseltorg_customer_query"]:
        coverage_column = f"{column}_coverage"
        if coverage_column in merged.columns:
            merged[column] = merged[column].fillna(merged[coverage_column])

    if "is_priority_focus_coverage" in merged.columns:
        merged["is_priority_focus"] = merged["is_priority_focus"].fillna(merged["is_priority_focus_coverage"])

    merged["identity_notes"] = merged["notes"]
    merged["is_priority_focus"] = _coerce_bool(merged["is_priority_focus"])

    int_columns = [
        "eis_223_open_count",
        "roseltorg_lot_count",
        "sberbank_ast_candidate_count",
        "sberbank_ast_lot_count",
        "zakazrf_candidate_count",
        "zakazrf_lot_count",
        "lot_online_lot_count",
        "lot_online_title_mention_count",
    ]
    for column in int_columns:
        merged[column] = _coerce_int(merged[column])

    result = merged[
        [
            "entity_key",
            "group_name",
            "entity_name",
            "entity_type",
            "inn",
            "ogrn",
            "kpp_list",
            "official_name",
            "short_name",
            "brand_aliases",
            "search_terms",
            "identity_source",
            "identity_confidence",
            "identity_notes",
            "is_priority_focus",
            "eis_search_term",
            "roseltorg_customer_query",
            "resolved_inn",
            "eis_entity_code",
            "eis_entity_name",
            "eis_resolved_inn",
            "eis_resolved_kpp",
            "eis_resolved_ogrn",
            "eis_fz94id",
            "eis_fz223id",
            "eis_223_open_count",
            "eis_results_url",
            "roseltorg_lot_count",
            "sberbank_ast_candidate_count",
            "sberbank_ast_lot_count",
            "zakazrf_candidate_count",
            "zakazrf_lot_count",
            "lot_online_lot_count",
            "lot_online_title_mention_count",
        ]
    ].copy()
    return result.sort_values(["is_priority_focus", "entity_name"], ascending=[False, True]).reset_index(drop=True)


def build_entity_identity_enrichment_load_frame(enrichment_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "entity_key",
        "entity_name",
        "inn",
        "source_system",
        "field_name",
        "proposed_value",
        "evidence",
        "confidence",
        "decision",
    ]
    if enrichment_df.empty:
        return pd.DataFrame(columns=columns)
    frame = _ensure_columns(enrichment_df, columns).copy()
    return frame[columns].drop_duplicates().sort_values(
        ["entity_name", "source_system", "field_name", "proposed_value"]
    ).reset_index(drop=True)


def build_entity_source_link_load_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "entity_name",
        "source_system",
        "external_customer_key",
        "external_customer_name",
        "external_inn",
        "external_kpp",
        "query_used",
        "resolution_method",
        "records_total",
        "candidate_rank",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = _ensure_columns(frame, columns).copy()
    result["records_total"] = _coerce_int(result["records_total"])
    result["candidate_rank"] = _coerce_int(result["candidate_rank"], default=1)
    return result[columns].drop_duplicates().reset_index(drop=True)


def build_source_assessment_load_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "source_system",
        "platform_name",
        "platform_url",
        "operational_status",
        "inclusion_status",
        "access_mode",
        "rationale",
        "coverage_note",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    return _ensure_columns(frame, columns)[columns].drop_duplicates().reset_index(drop=True)


def build_integration_probe_load_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "source_system",
        "entity_name",
        "probe_mode",
        "query_used",
        "matched_external_id",
        "matched_external_name",
        "matched_external_inn",
        "matched_external_role",
        "records_total",
        "candidate_rank",
        "included_in_core",
        "note",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = _ensure_columns(frame, columns).copy()
    result["records_total"] = _coerce_int(result["records_total"])
    result["candidate_rank"] = _coerce_int(result["candidate_rank"], default=1)
    result["included_in_core"] = _coerce_bool(result["included_in_core"])
    return result[columns].drop_duplicates().reset_index(drop=True)


def _merge_entity_ids(frame: pd.DataFrame, entity_lookup: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.drop(columns=["entity_id"], errors="ignore").copy()
    result = _ensure_columns(result, ["entity_name", "customer_name", "customer_inn"])
    lookup = _ensure_columns(
        entity_lookup,
        [
            "entity_id",
            "entity_name",
            "official_name",
            "short_name",
            "brand_aliases",
            "search_terms",
            "eis_search_term",
            "roseltorg_customer_query",
            "inn",
        ],
    ).copy()

    inn_lookup: dict[str, set[Any]] = {}
    strict_name_lookup: dict[str, set[Any]] = {}
    relaxed_name_lookup: dict[str, set[Any]] = {}
    for row in lookup.to_dict(orient="records"):
        entity_id = row["entity_id"]
        inn = normalize_identifier(_string_value(row.get("inn")))
        if inn:
            inn_lookup.setdefault(inn, set()).add(entity_id)

        raw_names = [
            row.get("entity_name"),
            row.get("official_name"),
            row.get("short_name"),
            row.get("eis_search_term"),
            row.get("roseltorg_customer_query"),
            *_multi_value_tokens(row.get("brand_aliases")),
            *_multi_value_tokens(row.get("search_terms")),
        ]
        for raw_name in raw_names:
            for variant in _strict_name_variants(raw_name):
                strict_name_lookup.setdefault(variant, set()).add(entity_id)
            for variant in _relaxed_name_variants(raw_name):
                relaxed_name_lookup.setdefault(variant, set()).add(entity_id)

    resolved_entity_ids: list[Any] = []
    missing_labels: list[str] = []
    ambiguous_labels: list[str] = []

    def _field_candidates(row: dict[str, Any], field_name: str, lookup_map: dict[str, set[Any]], *, strict: bool) -> set[Any]:
        variants = _strict_name_variants(row.get(field_name)) if strict else _relaxed_name_variants(row.get(field_name))
        matches: set[Any] = set()
        for variant in variants:
            matches.update(lookup_map.get(variant, set()))
        return matches

    for row in result.to_dict(orient="records"):
        customer_inn = normalize_identifier(_string_value(row.get("customer_inn")))
        inn_matches = inn_lookup.get(customer_inn, set()) if customer_inn else set()
        if len(inn_matches) == 1:
            resolved_entity_ids.append(next(iter(inn_matches)))
            continue

        entity_strict_matches = _field_candidates(row, "entity_name", strict_name_lookup, strict=True)
        if len(entity_strict_matches) == 1:
            resolved_entity_ids.append(next(iter(entity_strict_matches)))
            continue

        customer_strict_matches = _field_candidates(row, "customer_name", strict_name_lookup, strict=True)
        if len(customer_strict_matches) == 1:
            resolved_entity_ids.append(next(iter(customer_strict_matches)))
            continue

        strict_intersection = entity_strict_matches.intersection(customer_strict_matches)
        if len(strict_intersection) == 1:
            resolved_entity_ids.append(next(iter(strict_intersection)))
            continue

        entity_relaxed_matches = _field_candidates(row, "entity_name", relaxed_name_lookup, strict=False)
        if len(entity_relaxed_matches) == 1:
            resolved_entity_ids.append(next(iter(entity_relaxed_matches)))
            continue

        customer_relaxed_matches = _field_candidates(row, "customer_name", relaxed_name_lookup, strict=False)
        if len(customer_relaxed_matches) == 1:
            resolved_entity_ids.append(next(iter(customer_relaxed_matches)))
            continue

        relaxed_intersection = entity_relaxed_matches.intersection(customer_relaxed_matches)
        if len(relaxed_intersection) == 1:
            resolved_entity_ids.append(next(iter(relaxed_intersection)))
            continue

        name_matches = strict_intersection or entity_strict_matches or customer_strict_matches
        if not name_matches:
            name_matches = relaxed_intersection or entity_relaxed_matches or customer_relaxed_matches
        if inn_matches:
            name_matches = name_matches.intersection(inn_matches) or inn_matches

        label = _string_value(row.get("entity_name")) or _string_value(row.get("customer_name")) or "<unknown>"
        if len(name_matches) > 1:
            ambiguous_labels.append(label)
        else:
            missing_labels.append(label)
        resolved_entity_ids.append(None)

    result["entity_id"] = resolved_entity_ids
    if ambiguous_labels:
        preview = ", ".join(sorted(dict.fromkeys(ambiguous_labels))[:5])
        raise ValueError(f"Ambiguous entity_id resolution for lots: {preview}")
    missing = sorted(dict.fromkeys(missing_labels))
    if missing:
        preview = ", ".join(missing[:5])
        raise ValueError(f"Could not resolve entity_id for lots: {preview}")
    return result


def build_procurement_lot_load_frame(frame: pd.DataFrame, entity_lookup: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "entity_id",
        "source_system",
        "platform_section",
        "procedure_number",
        "lot_number",
        "subject",
        "customer_name",
        "customer_inn",
        "region",
        "status",
        "tender_type",
        "price_rub",
        "currency",
        "published_at",
        "deadline_at",
        "application_deadline",
        "method_name",
        "detail_url",
        "tags",
        "delivery_place",
        "focus_category",
        "sberb2b_need_id",
        "sberb2b_condition_id",
        "sberb2b_status",
        "sberb2b_state",
        "sberb2b_public_request_status",
        "search_url",
        "duplicate_group_size",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = _ensure_columns(frame, columns + ["entity_name"]).copy()
    result = _merge_entity_ids(result, entity_lookup)
    result["price_rub"] = _coerce_float(result["price_rub"])
    result["published_at"] = _coerce_datetime(result["published_at"])
    result["deadline_at"] = _coerce_datetime(result["deadline_at"])
    result["application_deadline"] = _coerce_datetime(result["application_deadline"])
    result["duplicate_group_size"] = _coerce_int(result["duplicate_group_size"], default=1)
    return result[columns].drop_duplicates(subset=["source_system", "procedure_number", "lot_number"]).reset_index(
        drop=True
    )


def _merge_lot_ids(frame: pd.DataFrame, lot_lookup: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    frame = frame.drop(columns=["lot_id"], errors="ignore")
    lookup = lot_lookup[["lot_id", "source_system", "procedure_number", "lot_number"]].drop_duplicates()
    merged = frame.merge(lookup, on=["source_system", "procedure_number", "lot_number"], how="left")
    fallback_mask = merged["lot_id"].isna()
    if fallback_mask.any():
        fallback_lookup = lookup[["lot_id", "procedure_number", "lot_number"]].drop_duplicates()
        fallback_lookup = fallback_lookup[
            ~fallback_lookup.duplicated(subset=["procedure_number", "lot_number"], keep=False)
        ]
        fallback = merged.loc[fallback_mask, ["procedure_number", "lot_number"]].merge(
            fallback_lookup,
            on=["procedure_number", "lot_number"],
            how="left",
        )
        merged.loc[fallback_mask, "lot_id"] = fallback["lot_id"].values
    missing = merged[merged["lot_id"].isna()][["source_system", "procedure_number", "lot_number"]].drop_duplicates()
    if not missing.empty:
        preview = ", ".join(
            f"{row.source_system}:{row.procedure_number}/{row.lot_number}"
            for row in missing.head(5).itertuples(index=False)
        )
        raise ValueError(f"Could not resolve lot_id for related rows: {preview}")
    return merged


def build_procurement_item_load_frame(frame: pd.DataFrame, lot_lookup: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "lot_id",
        "line_no",
        "item_name",
        "okpd_code",
        "okpd_name",
        "quantity",
        "unit",
        "okei_code",
        "item_description",
        "item_id_external",
        "unit_price_rub",
        "line_total_rub",
        "unit_price_source",
        "sberb2b_need_id",
        "sberb2b_condition_id",
        "focus_category",
        "price_rub",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = _ensure_columns(frame, columns + ["source_system", "procedure_number", "lot_number"]).copy()
    result = _merge_lot_ids(result, lot_lookup)
    result["line_no"] = _coerce_int(result["line_no"], default=1)
    for column in ["quantity", "unit_price_rub", "line_total_rub", "price_rub"]:
        result[column] = _coerce_float(result[column])
    return result[columns].reset_index(drop=True)


def build_document_link_load_frame(frame: pd.DataFrame, lot_lookup: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "lot_id",
        "document_name",
        "document_url",
        "document_storage_name",
        "document_mime_type",
        "document_size_bytes",
        "document_hash",
        "local_path",
        "extraction_method",
        "text_chars",
        "ocr_required",
        "pii_findings_count",
        "is_available",
        "pii_masked",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = _ensure_columns(frame, columns + ["source_system", "procedure_number", "lot_number"]).copy()
    result = _merge_lot_ids(result, lot_lookup)
    result["document_size_bytes"] = _coerce_float(result["document_size_bytes"]).astype("Int64")
    result["text_chars"] = _coerce_int(result["text_chars"])
    result["pii_findings_count"] = _coerce_int(result["pii_findings_count"])
    result["ocr_required"] = _coerce_bool(result["ocr_required"])
    result["is_available"] = _coerce_bool(result["is_available"])
    result["pii_masked"] = True
    return result[columns].drop_duplicates(subset=["lot_id", "document_name", "local_path"]).reset_index(drop=True)


def _merge_document_ids(frame: pd.DataFrame, document_lookup: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    frame = frame.drop(columns=["document_id"], errors="ignore")
    lookup = document_lookup.copy()
    lookup["document_name_key"] = lookup["document_name"].map(_normalize_key)
    lookup["local_path_key"] = lookup["local_path"].map(_normalize_key)

    result = frame.copy()
    result["document_name_key"] = result["document_name"].map(_normalize_key)
    result["local_path_key"] = result["local_path"].map(_normalize_key)
    merged = result.merge(
        lookup[["document_id", "lot_id", "document_name_key", "local_path_key"]],
        on=["lot_id", "document_name_key", "local_path_key"],
        how="left",
    )
    fallback_mask = merged["document_id"].isna()
    if fallback_mask.any():
        fallback_lookup = lookup[["document_id", "lot_id", "document_name_key"]].drop_duplicates(
            subset=["lot_id", "document_name_key"]
        )
        fallback = merged.loc[fallback_mask, ["lot_id", "document_name_key"]].merge(
            fallback_lookup,
            on=["lot_id", "document_name_key"],
            how="left",
        )
        merged.loc[fallback_mask, "document_id"] = fallback["document_id"].values
    return merged.drop(columns=["document_name_key", "local_path_key"])


def build_document_text_load_frame(
    frame: pd.DataFrame,
    lot_lookup: pd.DataFrame,
    document_lookup: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "document_id",
        "lot_id",
        "document_name",
        "local_path",
        "extraction_method",
        "text_chars",
        "ocr_required",
        "pii_findings_count",
        "text_preview",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = _ensure_columns(frame, columns + ["source_system", "procedure_number", "lot_number"]).copy()
    result = _merge_lot_ids(result, lot_lookup)
    result = _merge_document_ids(result, document_lookup)
    result["text_chars"] = _coerce_int(result["text_chars"])
    result["pii_findings_count"] = _coerce_int(result["pii_findings_count"])
    result["ocr_required"] = _coerce_bool(result["ocr_required"])
    return result[columns].drop_duplicates(subset=["lot_id", "document_name", "local_path"]).reset_index(drop=True)


def build_procurement_participant_load_frame(frame: pd.DataFrame, lot_lookup: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "lot_id",
        "source_system",
        "procedure_number",
        "lot_number",
        "participant_role",
        "participant_name",
        "participant_inn",
        "participant_external_id",
        "offer_price_rub",
        "is_winner",
        "evidence_source",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = _ensure_columns(frame, columns).copy()
    result = _merge_lot_ids(result, lot_lookup)
    result["offer_price_rub"] = _coerce_float(result["offer_price_rub"])
    result["is_winner"] = _coerce_bool(result["is_winner"])
    return result[columns].drop_duplicates().reset_index(drop=True)


def build_external_factor_load_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "factor_date",
        "usd_rub",
        "nominal",
        "key_rate",
        "inflation_yoy_pct",
        "inflation_target_pct",
        "key_rate_month_end",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = _ensure_columns(frame, columns).copy()
    result["factor_date"] = _coerce_date(result["factor_date"])
    for column in [
        "usd_rub",
        "nominal",
        "key_rate",
        "inflation_yoy_pct",
        "inflation_target_pct",
        "key_rate_month_end",
    ]:
        result[column] = _coerce_float(result[column])
    return result[columns].drop_duplicates(subset=["factor_date"]).sort_values("factor_date").reset_index(drop=True)


def _sql_file_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in [SCHEMA_SQL_DIR, VIEWS_SQL_DIR, MARTS_SQL_DIR]:
        paths.extend(sorted(directory.glob("*.sql")))
    return paths


def _connect(conninfo: str):
    import psycopg

    return psycopg.connect(conninfo)


def _parse_conninfo(conninfo: str) -> dict[str, Any]:
    from psycopg.conninfo import conninfo_to_dict

    return conninfo_to_dict(conninfo)


def _ensure_database(admin_conninfo: str, database_name: str) -> None:
    from psycopg import sql

    with _connect(admin_conninfo) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("select 1 from pg_database where datname = %s", (database_name,))
            if cur.fetchone() is None:
                cur.execute(sql.SQL("create database {}").format(sql.Identifier(database_name)))


def _query_dataframe(conn, query: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        columns = [column.name for column in cur.description]
    return pd.DataFrame(rows, columns=columns)


def _apply_sql_artifacts(conn) -> None:
    with conn.cursor() as cur:
        for sql_path in _sql_file_paths():
            cur.execute(sql_path.read_text(encoding="utf-8"))


def _truncate_core_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            truncate table
                core.procurement_participant,
                core.document_text,
                core.document_link,
                core.procurement_item,
                core.procurement_lot,
                core.integration_probe,
                core.source_assessment,
                core.entity_source_link,
                core.entity_identity_enrichment,
                core.external_factor_daily,
                core.entity_scope
            restart identity cascade
            """
        )


def _insert_frame(conn, table_name: str, frame: pd.DataFrame, columns: list[str]) -> None:
    if frame.empty:
        return
    column_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql_text = f"insert into {table_name} ({column_list}) values ({placeholders})"
    records = _frame_records(frame, columns)
    with conn.cursor() as cur:
        cur.executemany(sql_text, records)


def _insert_load_audit(
    conn,
    *,
    database_name: str,
    scope_path: Path,
    curated_dir: Path,
    source_sprints_dir: Path,
    include_enrichment: bool,
    started_at: datetime,
    finished_at: datetime,
    summary: dict[str, int],
) -> int:
    sql_text = """
        insert into core.load_audit (
            database_name,
            scope_path,
            curated_dir,
            source_sprints_dir,
            include_enrichment,
            entity_scope_rows,
            entity_identity_enrichment_rows,
            entity_source_link_rows,
            source_assessment_rows,
            integration_probe_rows,
            procurement_lot_rows,
            procurement_item_rows,
            document_link_rows,
            document_text_rows,
            procurement_participant_rows,
            external_factor_daily_rows,
            started_at,
            finished_at
        )
        values (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        returning load_audit_id
    """
    values = (
        database_name,
        str(scope_path),
        str(curated_dir),
        str(source_sprints_dir),
        include_enrichment,
        summary["entity_scope_rows"],
        summary["entity_identity_enrichment_rows"],
        summary["entity_source_link_rows"],
        summary["source_assessment_rows"],
        summary["integration_probe_rows"],
        summary["procurement_lot_rows"],
        summary["procurement_item_rows"],
        summary["document_link_rows"],
        summary["document_text_rows"],
        summary["procurement_participant_rows"],
        summary["external_factor_daily_rows"],
        started_at,
        finished_at,
    )
    with conn.cursor() as cur:
        cur.execute(sql_text, values)
        row = cur.fetchone()
    if row is None:
        raise ValueError("Could not insert load audit row.")
    return int(row[0])


def default_dsn() -> str | None:
    return os.environ.get("PURCHASE_ANALYSIS_PG_DSN") or os.environ.get("DATABASE_URL")


def build_admin_dsn(target_conninfo: str, explicit_admin_conninfo: str | None) -> str:
    if explicit_admin_conninfo:
        return explicit_admin_conninfo
    from psycopg.conninfo import make_conninfo

    conninfo = _parse_conninfo(target_conninfo)
    database = conninfo.get("dbname") or "postgres"
    conninfo["dbname"] = "postgres"
    if database == "postgres":
        return target_conninfo
    return make_conninfo(**conninfo)


def sync_postgres(
    *,
    dsn: str,
    admin_dsn: str | None = None,
    create_database: bool = False,
    scope_path: Path = CONFIG_DIR / "entity_scope.csv",
    curated_dir: Path = CURATED_DIR,
    source_sprints_dir: Path = SOURCE_SPRINTS_DIR,
    include_enrichment: bool = True,
) -> PostgresLoadSummary:
    scope_path = Path(scope_path)
    curated_dir = Path(curated_dir)
    source_sprints_dir = Path(source_sprints_dir)
    conninfo = _parse_conninfo(dsn)
    database_name = str(conninfo.get("dbname") or "")
    if not database_name:
        raise ValueError("PostgreSQL DSN must include a database name.")
    if create_database:
        _ensure_database(build_admin_dsn(dsn, admin_dsn), database_name)
    started_at = datetime.now(timezone.utc)

    snapshot = load_curated_snapshot(
        scope_path=scope_path,
        curated_dir=curated_dir,
        source_sprints_dir=source_sprints_dir,
        include_enrichment=include_enrichment,
    )

    with _connect(dsn) as conn:
        _apply_sql_artifacts(conn)
        _truncate_core_tables(conn)

        entity_scope_df = build_entity_scope_load_frame(snapshot.entity_scope, snapshot.entity_coverage)
        entity_enrichment_df = build_entity_identity_enrichment_load_frame(snapshot.enrichment_candidates)
        entity_source_link_df = build_entity_source_link_load_frame(snapshot.entity_source_links)
        source_assessment_df = build_source_assessment_load_frame(snapshot.source_assessment)
        integration_probe_df = build_integration_probe_load_frame(snapshot.integration_probe)
        external_factors_df = build_external_factor_load_frame(snapshot.external_factors_daily)

        _insert_frame(
            conn,
            "core.entity_scope",
            entity_scope_df,
            [
                "entity_key",
                "group_name",
                "entity_name",
                "entity_type",
                "inn",
                "ogrn",
                "kpp_list",
                "official_name",
                "short_name",
                "brand_aliases",
                "search_terms",
                "identity_source",
                "identity_confidence",
                "identity_notes",
                "is_priority_focus",
                "eis_search_term",
                "roseltorg_customer_query",
                "resolved_inn",
                "eis_entity_code",
                "eis_entity_name",
                "eis_resolved_inn",
                "eis_resolved_kpp",
                "eis_resolved_ogrn",
                "eis_fz94id",
                "eis_fz223id",
                "eis_223_open_count",
                "eis_results_url",
                "roseltorg_lot_count",
                "sberbank_ast_candidate_count",
                "sberbank_ast_lot_count",
                "zakazrf_candidate_count",
                "zakazrf_lot_count",
                "lot_online_lot_count",
                "lot_online_title_mention_count",
            ],
        )
        _insert_frame(
            conn,
            "core.entity_identity_enrichment",
            entity_enrichment_df,
            [
                "entity_key",
                "entity_name",
                "inn",
                "source_system",
                "field_name",
                "proposed_value",
                "evidence",
                "confidence",
                "decision",
            ],
        )
        _insert_frame(
            conn,
            "core.entity_source_link",
            entity_source_link_df,
            [
                "entity_name",
                "source_system",
                "external_customer_key",
                "external_customer_name",
                "external_inn",
                "external_kpp",
                "query_used",
                "resolution_method",
                "records_total",
                "candidate_rank",
            ],
        )
        _insert_frame(
            conn,
            "core.source_assessment",
            source_assessment_df,
            [
                "source_system",
                "platform_name",
                "platform_url",
                "operational_status",
                "inclusion_status",
                "access_mode",
                "rationale",
                "coverage_note",
            ],
        )
        _insert_frame(
            conn,
            "core.integration_probe",
            integration_probe_df,
            [
                "source_system",
                "entity_name",
                "probe_mode",
                "query_used",
                "matched_external_id",
                "matched_external_name",
                "matched_external_inn",
                "matched_external_role",
                "records_total",
                "candidate_rank",
                "included_in_core",
                "note",
            ],
        )
        _insert_frame(
            conn,
            "core.external_factor_daily",
            external_factors_df,
            [
                "factor_date",
                "usd_rub",
                "nominal",
                "key_rate",
                "inflation_yoy_pct",
                "inflation_target_pct",
                "key_rate_month_end",
            ],
        )

        entity_lookup = _query_dataframe(
            conn,
            """
            select
                entity_id,
                entity_name,
                official_name,
                short_name,
                brand_aliases,
                search_terms,
                eis_search_term,
                roseltorg_customer_query,
                inn
            from core.entity_scope
            """,
        )
        procurement_lots_df = build_procurement_lot_load_frame(snapshot.procurement_lots, entity_lookup)
        _insert_frame(
            conn,
            "core.procurement_lot",
            procurement_lots_df,
            [
                "entity_id",
                "source_system",
                "platform_section",
                "procedure_number",
                "lot_number",
                "subject",
                "customer_name",
                "customer_inn",
                "region",
                "status",
                "tender_type",
                "price_rub",
                "currency",
                "published_at",
                "deadline_at",
                "application_deadline",
                "method_name",
                "detail_url",
                "tags",
                "delivery_place",
                "focus_category",
                "sberb2b_need_id",
                "sberb2b_condition_id",
                "sberb2b_status",
                "sberb2b_state",
                "sberb2b_public_request_status",
                "search_url",
                "duplicate_group_size",
            ],
        )

        lot_lookup = _query_dataframe(
            conn,
            "select lot_id, source_system, procedure_number, lot_number from core.procurement_lot",
        )
        procurement_items_df = build_procurement_item_load_frame(snapshot.procurement_items, lot_lookup)
        _insert_frame(
            conn,
            "core.procurement_item",
            procurement_items_df,
            [
                "lot_id",
                "line_no",
                "item_name",
                "okpd_code",
                "okpd_name",
                "quantity",
                "unit",
                "okei_code",
                "item_description",
                "item_id_external",
                "unit_price_rub",
                "line_total_rub",
                "unit_price_source",
                "sberb2b_need_id",
                "sberb2b_condition_id",
                "focus_category",
                "price_rub",
            ],
        )

        document_links_df = build_document_link_load_frame(snapshot.document_links, lot_lookup)
        _insert_frame(
            conn,
            "core.document_link",
            document_links_df,
            [
                "lot_id",
                "document_name",
                "document_url",
                "document_storage_name",
                "document_mime_type",
                "document_size_bytes",
                "document_hash",
                "local_path",
                "extraction_method",
                "text_chars",
                "ocr_required",
                "pii_findings_count",
                "is_available",
                "pii_masked",
            ],
        )

        document_lookup = _query_dataframe(
            conn,
            "select document_id, lot_id, document_name, local_path from core.document_link",
        )
        document_texts_df = build_document_text_load_frame(snapshot.document_texts, lot_lookup, document_lookup)
        _insert_frame(
            conn,
            "core.document_text",
            document_texts_df,
            [
                "document_id",
                "lot_id",
                "document_name",
                "local_path",
                "extraction_method",
                "text_chars",
                "ocr_required",
                "pii_findings_count",
                "text_preview",
            ],
        )

        procurement_participants_df = build_procurement_participant_load_frame(
            snapshot.procurement_participants, lot_lookup
        )
        _insert_frame(
            conn,
            "core.procurement_participant",
            procurement_participants_df,
            [
                "lot_id",
                "source_system",
                "procedure_number",
                "lot_number",
                "participant_role",
                "participant_name",
                "participant_inn",
                "participant_external_id",
                "offer_price_rub",
                "is_winner",
                "evidence_source",
            ],
        )

        finished_at = datetime.now(timezone.utc)
        summary_counts = {
            "entity_scope_rows": len(entity_scope_df),
            "entity_identity_enrichment_rows": len(entity_enrichment_df),
            "entity_source_link_rows": len(entity_source_link_df),
            "source_assessment_rows": len(source_assessment_df),
            "integration_probe_rows": len(integration_probe_df),
            "procurement_lot_rows": len(procurement_lots_df),
            "procurement_item_rows": len(procurement_items_df),
            "document_link_rows": len(document_links_df),
            "document_text_rows": len(document_texts_df),
            "procurement_participant_rows": len(procurement_participants_df),
            "external_factor_daily_rows": len(external_factors_df),
        }
        load_audit_id = _insert_load_audit(
            conn,
            database_name=database_name,
            scope_path=scope_path,
            curated_dir=curated_dir,
            source_sprints_dir=source_sprints_dir,
            include_enrichment=include_enrichment,
            started_at=started_at,
            finished_at=finished_at,
            summary=summary_counts,
        )
        conn.commit()

    return PostgresLoadSummary(
        database=database_name,
        load_audit_id=load_audit_id,
        entity_scope_rows=len(entity_scope_df),
        entity_identity_enrichment_rows=len(entity_enrichment_df),
        entity_source_link_rows=len(entity_source_link_df),
        source_assessment_rows=len(source_assessment_df),
        integration_probe_rows=len(integration_probe_df),
        procurement_lot_rows=len(procurement_lots_df),
        procurement_item_rows=len(procurement_items_df),
        document_link_rows=len(document_links_df),
        document_text_rows=len(document_texts_df),
        procurement_participant_rows=len(procurement_participants_df),
        external_factor_daily_rows=len(external_factors_df),
    )
