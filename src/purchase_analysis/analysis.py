from __future__ import annotations

from io import StringIO
from math import atanh, erfc, isfinite, sqrt
from typing import Any

import pandas as pd

from purchase_analysis.utils.text import normalize_spaces, token_category


MAX_PLAUSIBLE_PRICE_RUB = 1_000_000_000_000


def _sum_with_min_count(series: pd.Series) -> float | None:
    return series.sum(min_count=1)


def _clean_price_series(series: pd.Series) -> pd.Series:
    prices = pd.to_numeric(series, errors="coerce")
    return prices.where((prices > 0) & (prices <= MAX_PLAUSIBLE_PRICE_RUB))


def build_entities_frame(entity_records: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(entity_records)
    if df.empty:
        return df
    numeric_columns = [
        column
        for column in df.columns
        if column.endswith("_count")
        or column.endswith("_lot_count")
        or column.endswith("_candidate_count")
        or column.endswith("_records_total")
    ]
    for column in sorted(set(numeric_columns)):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)
    return df.sort_values(["is_priority_focus", "entity_name"], ascending=[False, True]).reset_index(
        drop=True
    )


def build_procurements_frame(
    search_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
) -> pd.DataFrame:
    base_df = pd.DataFrame(search_rows)
    if base_df.empty:
        return base_df
    detail_df = pd.DataFrame(detail_rows)
    if not detail_df.empty:
        df = base_df.merge(
            detail_df,
            on=["procedure_number", "lot_number"],
            how="left",
            suffixes=("", "_detail"),
        )
    else:
        df = base_df.copy()

    base_price = _clean_price_series(df["price_rub"])
    if "detail_price_rub" in df.columns:
        detail_price = _clean_price_series(df["detail_price_rub"])
        df["price_rub"] = detail_price.combine_first(base_price)
    else:
        df["price_rub"] = base_price

    for column in ["published_at", "application_deadline", "method_name", "currency"]:
        detail_column = f"{column}_detail"
        if detail_column in df.columns:
            if "published" in column or "deadline" in column:
                df[column] = pd.to_datetime(df[column], errors="coerce").combine_first(
                    pd.to_datetime(df[detail_column], errors="coerce")
                )
            else:
                df[column] = df[column].combine_first(df[detail_column])

    df["published_at"] = pd.to_datetime(df.get("published_at"), errors="coerce")
    df["deadline_at"] = pd.to_datetime(df.get("deadline_at"), errors="coerce")
    df["application_deadline"] = pd.to_datetime(df.get("application_deadline"), errors="coerce")
    df["publication_month"] = df["published_at"].dt.to_period("M").astype("string")
    df["publication_year"] = df["published_at"].dt.year.astype("Int64")
    df["focus_category"] = [
        token_category(subject, tags, okpd_name)
        for subject, tags, okpd_name in zip(
            df["subject"],
            df.get("tags", pd.Series(dtype="string")),
            df.get("okpd_name", pd.Series(dtype="string")),
            strict=False,
        )
    ]
    duplicate_key = ["source_system", "procedure_number", "lot_number"]
    df["duplicate_group_size"] = (
        df.groupby(duplicate_key, dropna=False)["procedure_number"].transform("count").fillna(1).astype(int)
    )
    df = df.sort_values(
        ["duplicate_group_size", "published_at", "price_rub", "procedure_number", "lot_number"],
        ascending=[False, False, False, True, True],
        na_position="last",
    )
    df = df.drop_duplicates(subset=duplicate_key, keep="first")
    return df.reset_index(drop=True)


def build_procurement_items_frame(
    lots_df: pd.DataFrame,
    extra_item_rows: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    if lots_df.empty:
        return pd.DataFrame()
    for column in ["okpd_code", "okpd_name", "quantity", "unit"]:
        if column not in lots_df.columns:
            lots_df[column] = pd.NA
    items_df = lots_df[
        [
            "source_system",
            "entity_name",
            "procedure_number",
            "lot_number",
            "subject",
            "okpd_code",
            "okpd_name",
            "quantity",
            "unit",
            "focus_category",
            "price_rub",
        ]
    ].copy()
    items_df.insert(4, "line_no", 1)
    items_df = items_df.rename(columns={"subject": "item_name"})
    items_df["item_description"] = pd.NA
    items_df["item_id_external"] = pd.NA
    items_df["okei_code"] = pd.NA
    items_df["unit_price_rub"] = pd.NA
    items_df["line_total_rub"] = items_df["price_rub"]
    items_df["sberb2b_need_id"] = pd.NA
    items_df["sberb2b_condition_id"] = pd.NA
    items_df["unit_price_source"] = "lot_total_fallback"

    extra_df = pd.DataFrame(extra_item_rows or [])
    if not extra_df.empty:
        key_columns = ["source_system", "procedure_number", "lot_number"]
        extra_keys = extra_df[key_columns].drop_duplicates()
        items_df = items_df.merge(
            extra_keys.assign(has_extra_items=True),
            on=key_columns,
            how="left",
        )
        items_df = items_df[items_df["has_extra_items"].isna()].drop(columns=["has_extra_items"])
        for column in items_df.columns:
            if column not in extra_df.columns:
                extra_df[column] = pd.NA
        extra_df = extra_df[items_df.columns]
        ordered_columns = list(items_df.columns)
        items_df = pd.concat(
            [
                items_df.dropna(axis=1, how="all"),
                extra_df.dropna(axis=1, how="all"),
            ],
            ignore_index=True,
            sort=False,
        ).reindex(columns=ordered_columns)

    lot_categories = lots_df[
        ["source_system", "procedure_number", "lot_number", "focus_category"]
    ].drop_duplicates()
    items_df = items_df.drop(columns=["focus_category"]).merge(
        lot_categories,
        on=["source_system", "procedure_number", "lot_number"],
        how="left",
    )

    numeric_columns = ["quantity", "price_rub", "unit_price_rub", "line_total_rub"]
    for column in numeric_columns:
        if column in items_df.columns:
            items_df[column] = pd.to_numeric(items_df[column], errors="coerce")
    return items_df.sort_values(
        ["source_system", "procedure_number", "lot_number", "line_no"],
        na_position="last",
    ).reset_index(drop=True)


def build_document_links_frame(document_rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not document_rows:
        return pd.DataFrame(
            columns=["procedure_number", "lot_number", "document_name", "document_url", "is_available"]
        )
    return pd.DataFrame(document_rows)


def build_document_texts_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=[
                "procedure_number",
                "lot_number",
                "document_name",
                "local_path",
                "extraction_method",
                "text_chars",
                "ocr_required",
                "pii_findings_count",
                "text_preview",
            ]
        )
    df = pd.DataFrame(rows).drop_duplicates(
        subset=["procedure_number", "lot_number", "document_name", "local_path"]
    )
    for column in ["text_chars", "pii_findings_count"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)
    if "ocr_required" in df.columns:
        df["ocr_required"] = df["ocr_required"].fillna(False).astype(bool)
    return df.sort_values(["procedure_number", "document_name"]).reset_index(drop=True)


def build_participants_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=[
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
        )
    df = pd.DataFrame(rows).drop_duplicates(
        subset=[
            "source_system",
            "procedure_number",
            "lot_number",
            "participant_role",
            "participant_name",
            "participant_inn",
            "participant_external_id",
        ]
    )
    if "offer_price_rub" in df.columns:
        df["offer_price_rub"] = pd.to_numeric(df["offer_price_rub"], errors="coerce")
    if "is_winner" in df.columns:
        df["is_winner"] = df["is_winner"].fillna(False).astype(bool)
    return df.sort_values(["procedure_number", "participant_role", "participant_name"]).reset_index(
        drop=True
    )


def build_entity_source_links_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)
    for column in ["records_total", "candidate_rank"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)
    return df.sort_values(["entity_name", "source_system", "candidate_rank"]).reset_index(drop=True)


def build_integration_probe_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)
    for column in ["records_total", "candidate_rank"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)
    if "included_in_core" in df.columns:
        df["included_in_core"] = df["included_in_core"].fillna(False).astype(bool)
    sort_columns = [
        column
        for column in [
            "source_system",
            "entity_name",
            "probe_mode",
            "candidate_rank",
            "records_total",
            "matched_external_name",
        ]
        if column in df.columns
    ]
    return df.sort_values(sort_columns, na_position="last").reset_index(drop=True)


def build_source_assessment_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates().sort_values(["operational_status", "source_system"]).reset_index(
        drop=True
    )


def build_duplicate_stats_frame(lots_df: pd.DataFrame) -> pd.DataFrame:
    if lots_df.empty or "duplicate_group_size" not in lots_df.columns:
        return pd.DataFrame(
            columns=["source_system", "entity_name", "duplicate_groups", "duplicate_rows_removed"]
        )
    duplicate_groups = lots_df[lots_df["duplicate_group_size"] > 1].copy()
    if duplicate_groups.empty:
        return pd.DataFrame(
            columns=["source_system", "entity_name", "duplicate_groups", "duplicate_rows_removed"]
        )
    summary = (
        duplicate_groups.groupby(["source_system", "entity_name"], dropna=False)
        .agg(
            duplicate_groups=("procedure_number", "count"),
            duplicate_rows_removed=("duplicate_group_size", lambda series: int((series - 1).sum())),
        )
        .reset_index()
    )
    return summary.sort_values(["duplicate_rows_removed", "duplicate_groups"], ascending=[False, False]).reset_index(
        drop=True
    )


def build_external_factors_frame(
    usd_rows: list[dict[str, Any]],
    key_rate_rows: list[dict[str, Any]],
    inflation_rows: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    usd_df = pd.DataFrame(usd_rows)
    key_df = pd.DataFrame(key_rate_rows)
    inflation_df = pd.DataFrame(inflation_rows or [])
    if usd_df.empty and key_df.empty and inflation_df.empty:
        return pd.DataFrame()
    if usd_df.empty:
        usd_df = pd.DataFrame(columns=["factor_date", "usd_rub", "nominal"])
    if key_df.empty:
        key_df = pd.DataFrame(columns=["factor_date", "key_rate"])
    df = usd_df.merge(key_df, on="factor_date", how="outer")
    if df.empty and not inflation_df.empty:
        df = inflation_df.rename(columns={"month_date": "factor_date"}).copy()
    df["factor_date"] = pd.to_datetime(df["factor_date"], errors="coerce")
    if not inflation_df.empty and "month_date" in inflation_df.columns:
        inflation_df["month_date"] = pd.to_datetime(inflation_df["month_date"], errors="coerce")
        inflation_df["publication_month"] = inflation_df["month_date"].dt.to_period("M").astype(str)
        df["publication_month"] = df["factor_date"].dt.to_period("M").astype(str)
        df = df.merge(
            inflation_df.drop(columns=["month_date"]),
            on="publication_month",
            how="left",
        )
        df = df.drop(columns=["publication_month"])
    df = df.sort_values("factor_date").reset_index(drop=True)
    return df


def build_monthly_activity_mart(lots_df: pd.DataFrame) -> pd.DataFrame:
    if lots_df.empty:
        return pd.DataFrame()
    filtered = lots_df.dropna(subset=["published_at"]).copy()
    filtered["publication_month"] = filtered["published_at"].dt.to_period("M").astype(str)
    monthly = (
        filtered
        .groupby(["publication_month", "focus_category"], dropna=False)
        .agg(
            lots_count=("procedure_number", "count"),
            total_price_rub=("price_rub", _sum_with_min_count),
            avg_price_rub=("price_rub", "mean"),
        )
        .reset_index()
    )
    return monthly.sort_values(["publication_month", "focus_category"]).reset_index(drop=True)


def build_yearly_summary_mart(lots_df: pd.DataFrame) -> pd.DataFrame:
    if lots_df.empty:
        return pd.DataFrame()
    yearly = (
        lots_df.dropna(subset=["publication_year"])
        .groupby("publication_year", dropna=False)
        .agg(
            lots_count=("procedure_number", "count"),
            total_price_rub=("price_rub", _sum_with_min_count),
            median_price_rub=("price_rub", "median"),
            unique_regions=("region", "nunique"),
            unique_categories=("focus_category", "nunique"),
            unique_sources=("source_system", "nunique"),
        )
        .reset_index()
    )
    return yearly.sort_values("publication_year").reset_index(drop=True)


def build_category_mix_mart(lots_df: pd.DataFrame) -> pd.DataFrame:
    if lots_df.empty:
        return pd.DataFrame()
    category = (
        lots_df.groupby(["publication_year", "focus_category"], dropna=False)
        .agg(
            lots_count=("procedure_number", "count"),
            total_price_rub=("price_rub", _sum_with_min_count),
        )
        .reset_index()
    )
    category["share_of_year_value"] = category.groupby("publication_year")["total_price_rub"].transform(
        lambda series: series / series.sum(min_count=1) if pd.notna(series.sum(min_count=1)) and series.sum(min_count=1) else pd.NA
    )
    return category.sort_values(["publication_year", "total_price_rub"], ascending=[True, False]).reset_index(
        drop=True
    )


def build_category_yoy_mart(lots_df: pd.DataFrame) -> pd.DataFrame:
    if lots_df.empty:
        return pd.DataFrame()
    base = (
        lots_df.dropna(subset=["publication_year"])
        .groupby(["publication_year", "focus_category"], dropna=False)
        .agg(
            lots_count=("procedure_number", "count"),
            total_price_rub=("price_rub", _sum_with_min_count),
        )
        .reset_index()
        .sort_values(["focus_category", "publication_year"])
    )
    base["prev_year_lots_count"] = base.groupby("focus_category")["lots_count"].shift(1)
    base["prev_year_total_price_rub"] = base.groupby("focus_category")["total_price_rub"].shift(1)
    base["lots_count_delta"] = base["lots_count"] - base["prev_year_lots_count"]
    base["lots_count_growth_ratio"] = base["lots_count"] / base["prev_year_lots_count"]
    base["total_price_delta_rub"] = base["total_price_rub"] - base["prev_year_total_price_rub"]
    base["total_price_growth_ratio"] = base["total_price_rub"] / base["prev_year_total_price_rub"]
    return base.reset_index(drop=True)


def build_anomalies_mart(lots_df: pd.DataFrame) -> pd.DataFrame:
    if lots_df.empty:
        return pd.DataFrame()
    df = lots_df.copy()
    results: list[pd.DataFrame] = []

    if df["price_rub"].notna().sum() > 0:
        df["category_median_price"] = df.groupby("focus_category")["price_rub"].transform("median")
        df["value_ratio_to_category_median"] = df["price_rub"] / df["category_median_price"]
        threshold = df["price_rub"].quantile(0.85)
        price_anomalies = df[
            (df["value_ratio_to_category_median"] >= 2)
            | ((threshold is not None) & (df["price_rub"] >= threshold))
        ].copy()
        price_anomalies["anomaly_type"] = "price_outlier"
        price_anomalies["anomaly_reason"] = price_anomalies.apply(
            lambda row: (
                "price >= 2x category median"
                if pd.notna(row["value_ratio_to_category_median"])
                and row["value_ratio_to_category_median"] >= 2
                else "top 15% by price"
            ),
            axis=1,
        )
        results.append(price_anomalies)

    with_price = df.dropna(subset=["price_rub", "published_at"]).copy()
    if not with_price.empty:
        with_price["subject_key"] = (
            with_price["subject"].fillna("").str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
        )
        subject_stats = (
            with_price.groupby(["entity_name", "subject_key"], dropna=False)
            .agg(
                price_min=("price_rub", "min"),
                price_max=("price_rub", "max"),
                observations=("procedure_number", "count"),
            )
            .reset_index()
        )
        volatile_subjects = subject_stats[
            (subject_stats["observations"] >= 2)
            & (subject_stats["price_min"] > 0)
            & ((subject_stats["price_max"] / subject_stats["price_min"]) >= 2)
        ]
        if not volatile_subjects.empty:
            repeated = with_price.merge(
                volatile_subjects[["entity_name", "subject_key", "price_min", "price_max"]],
                on=["entity_name", "subject_key"],
                how="inner",
            )
            repeated["category_median_price"] = pd.NA
            repeated["value_ratio_to_category_median"] = repeated["price_max"] / repeated["price_min"]
            repeated["anomaly_type"] = "repeated_subject_price_shift"
            repeated["anomaly_reason"] = repeated.apply(
                lambda row: f"same subject price spread {row['price_max'] / row['price_min']:.2f}x",
                axis=1,
            )
            results.append(repeated)

    if not df.dropna(subset=["published_at"]).empty:
        monthly_bursts = (
            df.dropna(subset=["published_at"])
            .groupby(["entity_name", "publication_month"], dropna=False)
            .agg(lots_count=("procedure_number", "count"))
            .reset_index()
        )
        monthly_bursts["baseline"] = monthly_bursts.groupby("entity_name")["lots_count"].transform("median")
        burst_rows = monthly_bursts[
            (monthly_bursts["lots_count"] >= 3) & (monthly_bursts["baseline"] > 0)
            & (monthly_bursts["lots_count"] >= monthly_bursts["baseline"] * 2)
        ]
        if not burst_rows.empty:
            burst_lots = df.merge(
                burst_rows[["entity_name", "publication_month", "lots_count", "baseline"]],
                on=["entity_name", "publication_month"],
                how="inner",
            )
            burst_lots["category_median_price"] = pd.NA
            burst_lots["value_ratio_to_category_median"] = pd.NA
            burst_lots["anomaly_type"] = "publication_burst"
            burst_lots["anomaly_reason"] = burst_lots.apply(
                lambda row: (
                    f"month {row['publication_month']} has {int(row['lots_count'])} lots "
                    f"vs baseline {row['baseline']:.1f}"
                ),
                axis=1,
            )
            results.append(burst_lots)

    standard_columns = [
        "entity_name",
        "procedure_number",
        "lot_number",
        "subject",
        "focus_category",
        "price_rub",
        "category_median_price",
        "value_ratio_to_category_median",
        "anomaly_type",
        "anomaly_reason",
        "detail_url",
    ]
    results = [frame.reindex(columns=standard_columns) for frame in results if not frame.empty]
    if not results:
        return pd.DataFrame(
            columns=standard_columns
        )

    anomaly_records: list[dict[str, Any]] = []
    for frame in results:
        anomaly_records.extend(frame.to_dict("records"))
    anomalies = pd.DataFrame.from_records(anomaly_records, columns=standard_columns)
    anomalies = anomalies.drop_duplicates(
        subset=["entity_name", "procedure_number", "lot_number", "anomaly_type", "anomaly_reason"]
    )
    return anomalies[standard_columns].sort_values(
        ["anomaly_type", "price_rub"], ascending=[True, False]
    ).reset_index(drop=True)


def _normal_item_key(value: object) -> str:
    text = normalize_spaces("" if value is None else str(value)).lower()
    text = text.replace("ё", "е")
    text = pd.Series([text]).str.replace(r"[^0-9a-zа-я]+", " ", regex=True).iloc[0]
    tokens = [token for token in text.split() if len(token) > 2]
    return " ".join(tokens[:10])


def build_unit_price_benchmarks_mart(items_df: pd.DataFrame) -> pd.DataFrame:
    if items_df.empty or "unit_price_rub" not in items_df.columns:
        return pd.DataFrame()
    df = items_df.copy()
    df["unit_price_rub"] = pd.to_numeric(df["unit_price_rub"], errors="coerce")
    df["quantity"] = pd.to_numeric(df.get("quantity"), errors="coerce")
    df = df[df["unit_price_rub"].notna() & (df["unit_price_rub"] > 0)].copy()
    if df.empty:
        return pd.DataFrame()
    df["item_key"] = df["item_name"].map(_normal_item_key)
    df["benchmark_key"] = df.apply(
        lambda row: "|".join(
            [
                normalize_spaces(str(row.get("okpd_code") or ""))[:8],
                normalize_spaces(str(row.get("unit") or "")).lower(),
                row["item_key"],
            ]
        ),
        axis=1,
    )
    stats = (
        df.groupby("benchmark_key", dropna=False)
        .agg(
            observations=("unit_price_rub", "count"),
            median_unit_price_rub=("unit_price_rub", "median"),
            p75_unit_price_rub=("unit_price_rub", lambda series: series.quantile(0.75)),
            min_unit_price_rub=("unit_price_rub", "min"),
            max_unit_price_rub=("unit_price_rub", "max"),
        )
        .reset_index()
    )
    enriched = df.merge(stats, on="benchmark_key", how="left")
    enriched["ratio_to_median_unit_price"] = (
        enriched["unit_price_rub"] / enriched["median_unit_price_rub"]
    )
    enriched["unit_price_anomaly_flag"] = (
        (enriched["observations"] >= 2)
        & (enriched["median_unit_price_rub"] > 0)
        & (enriched["ratio_to_median_unit_price"] >= 1.8)
    )
    columns = [
        "source_system",
        "entity_name",
        "procedure_number",
        "lot_number",
        "line_no",
        "item_name",
        "okpd_code",
        "okpd_name",
        "quantity",
        "unit",
        "unit_price_rub",
        "line_total_rub",
        "benchmark_key",
        "observations",
        "median_unit_price_rub",
        "p75_unit_price_rub",
        "ratio_to_median_unit_price",
        "unit_price_anomaly_flag",
    ]
    return enriched[columns].sort_values(
        ["unit_price_anomaly_flag", "ratio_to_median_unit_price", "unit_price_rub"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)


def _correlation_p_value(r: float | None, n: int) -> float | None:
    if r is None or n < 4 or not isfinite(r) or abs(r) >= 1:
        return None
    z_score = abs(atanh(r)) * sqrt(n - 3)
    return erfc(z_score / sqrt(2))


def build_macro_diagnostics_mart(monthly_macro_df: pd.DataFrame) -> pd.DataFrame:
    if monthly_macro_df.empty:
        return pd.DataFrame()
    pairs = [
        ("total_price_rub", "avg_usd_rub"),
        ("total_price_rub", "avg_key_rate"),
        ("total_price_rub", "inflation_yoy_pct"),
        ("lots_count", "avg_usd_rub"),
        ("lots_count", "avg_key_rate"),
        ("lots_count", "inflation_yoy_pct"),
    ]
    rows: list[dict[str, Any]] = []
    for left, right in pairs:
        if left not in monthly_macro_df.columns or right not in monthly_macro_df.columns:
            continue
        pair_df = monthly_macro_df[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
        n = len(pair_df)
        r = float(pair_df[left].corr(pair_df[right])) if n >= 2 else None
        rows.append(
            {
                "metric": left,
                "factor": right,
                "observations": n,
                "pearson_r": r,
                "approx_p_value_fisher_z": _correlation_p_value(r, n),
                "statistical_note": (
                    "directional_only_small_sample"
                    if n < 24
                    else "interpret_with_procurement_coverage_limits"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_monthly_macro_join_mart(
    lots_df: pd.DataFrame,
    external_factors_df: pd.DataFrame,
) -> pd.DataFrame:
    if lots_df.empty or external_factors_df.empty:
        return pd.DataFrame()
    filtered = lots_df.dropna(subset=["published_at"]).copy()
    filtered["publication_month"] = filtered["published_at"].dt.to_period("M").astype(str)
    monthly_lots = (
        filtered
        .groupby("publication_month")
        .agg(
            lots_count=("procedure_number", "count"),
            total_price_rub=("price_rub", _sum_with_min_count),
            avg_price_rub=("price_rub", "mean"),
        )
        .reset_index()
    )
    macro = external_factors_df.copy()
    for column in ["usd_rub", "key_rate", "inflation_yoy_pct", "inflation_target_pct"]:
        if column not in macro.columns:
            macro[column] = pd.NA
    macro["publication_month"] = macro["factor_date"].dt.to_period("M").astype(str)
    monthly_macro = (
        macro.groupby("publication_month")
        .agg(
            avg_usd_rub=("usd_rub", "mean"),
            avg_key_rate=("key_rate", "mean"),
            inflation_yoy_pct=("inflation_yoy_pct", "mean"),
            inflation_target_pct=("inflation_target_pct", "mean"),
        )
        .reset_index()
    )
    joined = monthly_lots.merge(monthly_macro, on="publication_month", how="left")
    if len(joined) >= 2:
        joined["corr_total_vs_usd"] = joined["total_price_rub"].corr(joined["avg_usd_rub"])
        joined["corr_total_vs_key_rate"] = joined["total_price_rub"].corr(joined["avg_key_rate"])
        joined["corr_total_vs_inflation"] = joined["total_price_rub"].corr(joined["inflation_yoy_pct"])
        joined["corr_lots_vs_usd"] = joined["lots_count"].corr(joined["avg_usd_rub"])
        joined["corr_lots_vs_key_rate"] = joined["lots_count"].corr(joined["avg_key_rate"])
        joined["corr_lots_vs_inflation"] = joined["lots_count"].corr(joined["inflation_yoy_pct"])
    else:
        joined["corr_total_vs_usd"] = pd.NA
        joined["corr_total_vs_key_rate"] = pd.NA
        joined["corr_total_vs_inflation"] = pd.NA
        joined["corr_lots_vs_usd"] = pd.NA
        joined["corr_lots_vs_key_rate"] = pd.NA
        joined["corr_lots_vs_inflation"] = pd.NA
    return joined.sort_values("publication_month").reset_index(drop=True)


def build_quality_summary(
    entities_df: pd.DataFrame,
    lots_df: pd.DataFrame,
    items_df: pd.DataFrame,
    document_links_df: pd.DataFrame,
    external_factors_df: pd.DataFrame,
    document_texts_df: pd.DataFrame | None = None,
    participants_df: pd.DataFrame | None = None,
    unit_price_benchmarks_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    duplicate_lots_removed = 0
    if not lots_df.empty and "duplicate_group_size" in lots_df.columns:
        duplicate_lots_removed = int((lots_df["duplicate_group_size"] - 1).clip(lower=0).sum())
    non_zero_entities = 0
    if not lots_df.empty and "entity_name" in lots_df.columns:
        non_zero_entities = int(lots_df["entity_name"].nunique())
    price_coverage = 0.0
    if not lots_df.empty and "price_rub" in lots_df.columns:
        price_coverage = float(lots_df["price_rub"].notna().mean())
    source_breakdown: dict[str, int] = {}
    if not lots_df.empty and "source_system" in lots_df.columns:
        source_breakdown = {str(key): int(value) for key, value in lots_df["source_system"].value_counts().items()}
    document_texts_df = document_texts_df if document_texts_df is not None else pd.DataFrame()
    participants_df = participants_df if participants_df is not None else pd.DataFrame()
    unit_price_benchmarks_df = (
        unit_price_benchmarks_df if unit_price_benchmarks_df is not None else pd.DataFrame()
    )
    return {
        "entities_total": int(len(entities_df)),
        "entities_with_observed_lots": non_zero_entities,
        "lots_total": int(len(lots_df)),
        "lots_duplicates_removed": duplicate_lots_removed,
        "lots_with_disclosed_price": int(lots_df["price_rub"].notna().sum()) if not lots_df.empty else 0,
        "price_coverage_ratio": round(price_coverage, 4),
        "items_total": int(len(items_df)),
        "items_with_unit_price": int(items_df["unit_price_rub"].notna().sum()) if "unit_price_rub" in items_df else 0,
        "document_links_total": int(len(document_links_df)),
        "document_texts_total": int(len(document_texts_df)),
        "document_text_chars_total": (
            int(document_texts_df["text_chars"].sum())
            if not document_texts_df.empty and "text_chars" in document_texts_df
            else 0
        ),
        "participants_total": int(len(participants_df)),
        "winners_total": (
            int(participants_df["is_winner"].sum())
            if not participants_df.empty and "is_winner" in participants_df
            else 0
        ),
        "unit_price_benchmarks_total": int(len(unit_price_benchmarks_df)),
        "unit_price_anomalies_total": (
            int(unit_price_benchmarks_df["unit_price_anomaly_flag"].sum())
            if not unit_price_benchmarks_df.empty and "unit_price_anomaly_flag" in unit_price_benchmarks_df
            else 0
        ),
        "macro_days_total": int(len(external_factors_df)),
        "macro_has_inflation": bool(
            "inflation_yoy_pct" in external_factors_df.columns
            and external_factors_df["inflation_yoy_pct"].notna().any()
        )
        if not external_factors_df.empty
        else False,
        "source_breakdown": source_breakdown,
        "coverage_note": (
            "EIS works as official coverage control; Roseltorg and Sberbank-AST supply the observed lot-level "
            "sample; SberB2B public cards enrich AST rows with goods, documents, and any public participant data; "
            "ZakazRF, Lot-Online, RTS-Tender, ETP GPB, and Tektorg are reproduced or documented as exact "
            "probe sources with zero new 2024-2025 core rows after deduplication and precision checks."
        ),
    }


def build_llm_prompt_context(
    quality: dict[str, Any],
    source_assessment_df: pd.DataFrame,
    yearly_summary_df: pd.DataFrame,
    category_yoy_df: pd.DataFrame,
    anomalies_df: pd.DataFrame,
    unit_price_benchmarks_df: pd.DataFrame | None = None,
    macro_diagnostics_df: pd.DataFrame | None = None,
    document_texts_df: pd.DataFrame | None = None,
) -> str:
    sections = [
        "# LLM Prompt Pack",
        "",
        "Ниже собран компактный контекст для внешнего LLM-анализа закупок группы Сбер.",
        "Использование:",
        "1. Передайте этот файл в модель как контекст.",
        "2. Попросите модель сформировать наблюдения, гипотезы и ограничения.",
        "3. Не запрашивайте персональные данные и не скачивайте бинарные вложения без отдельного контура доступа.",
        "",
        "## Quality Summary",
        "",
        "```json",
        pd.Series(quality).to_json(force_ascii=False, indent=2),
        "```",
        "",
    ]

    def _frame_section(title: str, df: pd.DataFrame, limit: int = 20) -> list[str]:
        if df.empty:
            return [f"## {title}", "", "_no rows_", ""]
        buffer = StringIO()
        df.head(limit).to_csv(buffer, index=False)
        return [f"## {title}", "", "```csv", buffer.getvalue().strip(), "```", ""]

    sections.extend(_frame_section("Source Assessment", source_assessment_df, limit=20))
    sections.extend(_frame_section("Yearly Summary", yearly_summary_df, limit=20))
    sections.extend(_frame_section("YoY Category Changes", category_yoy_df, limit=50))
    sections.extend(_frame_section("Anomalies", anomalies_df, limit=50))
    if unit_price_benchmarks_df is not None:
        flagged = unit_price_benchmarks_df
        if not flagged.empty and "unit_price_anomaly_flag" in flagged.columns:
            flagged = flagged[flagged["unit_price_anomaly_flag"] == True]  # noqa: E712
        sections.extend(_frame_section("Unit Price Benchmarks", flagged, limit=50))
    if macro_diagnostics_df is not None:
        sections.extend(_frame_section("Macro Diagnostics", macro_diagnostics_df, limit=20))
    if document_texts_df is not None:
        preview_columns = [
            column
            for column in [
                "procedure_number",
                "document_name",
                "extraction_method",
                "text_chars",
                "ocr_required",
                "text_preview",
            ]
            if column in document_texts_df.columns
        ]
        sections.extend(_frame_section("Document Text Extracts", document_texts_df[preview_columns], limit=20))
    sections.extend(
        [
            "## Suggested Prompt",
            "",
            (
                "Сформируй аналитическую записку по закупкам группы Сбер за 2024–2025 годы. "
                "Для каждого блока дай Observation, Interpretation, Significance и Limitation. "
                "Отдельно перечисли аномалии, оцени полноту покрытия по источникам и предложи 5 гипотез для следующего исследования."
            ),
            "",
        ]
    )
    return "\n".join(sections)
