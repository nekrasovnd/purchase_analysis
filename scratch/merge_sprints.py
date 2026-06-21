from pathlib import Path
import pandas as pd
from datetime import date

from purchase_analysis.analysis import (
    build_procurements_frame,
    build_procurement_items_frame,
    build_monthly_activity_mart,
    build_yearly_summary_mart,
    build_category_mix_mart,
    build_category_yoy_mart,
    build_anomalies_mart,
    build_monthly_macro_join_mart,
    build_unit_price_benchmarks_mart,
    build_macro_diagnostics_mart
)

ROOT = Path("d:/Nikita/Work/purchase_analysis")
SPRINTS_DIR = ROOT / "output/source_sprints"
CURATED_DIR = ROOT / "data/curated"

def safe_read(path):
    if path.exists():
        return pd.read_csv(path, keep_default_na=False)
    return pd.DataFrame()

def main():
    all_search_rows = []
    for p in SPRINTS_DIR.rglob("items.csv"):
        print(f"Loading sprint items from {p.parent.name}...")
        try:
            df = pd.read_csv(p, dtype=str, keep_default_na=False)
            all_search_rows.extend(df.to_dict('records'))
        except pd.errors.EmptyDataError:
            print(f"Skipping {p.parent.name} (file is empty)")

    if not all_search_rows:
        print("No sprint items found.")
        return

    all_detail_rows = []
    for p in SPRINTS_DIR.rglob("details.csv"):
        try:
            df = pd.read_csv(p, dtype=str, keep_default_na=False)
            all_detail_rows.extend(df.to_dict('records'))
        except pd.errors.EmptyDataError:
            pass

    print(f"Found {len(all_search_rows)} raw sprint items and {len(all_detail_rows)} raw details.")
    new_lots_df = build_procurements_frame(all_search_rows, detail_rows=all_detail_rows, date_from="2024-01-01", date_to="2025-12-31")

    # Load existing lots
    lots_path = CURATED_DIR / "procurement_lots.csv"
    existing_lots_df = safe_read(lots_path)
    if not existing_lots_df.empty:
        combined_lots_df = pd.concat([existing_lots_df, new_lots_df], ignore_index=True)
    else:
        combined_lots_df = new_lots_df

    initial_len = len(combined_lots_df)
    combined_lots_df.drop_duplicates(subset=["source_system", "procedure_number", "lot_number"], keep="last", inplace=True)
    dedup_len = len(combined_lots_df)
    print(f"Combined lots: {initial_len} -> deduped to {dedup_len}")
    combined_lots_df.to_csv(lots_path, index=False)

    # Process items
    new_items_df = build_procurement_items_frame(new_lots_df, extra_item_rows=all_search_rows)
    items_path = CURATED_DIR / "procurement_items.csv"
    existing_items_df = safe_read(items_path)
    if not existing_items_df.empty:
        combined_items_df = pd.concat([existing_items_df, new_items_df], ignore_index=True)
    else:
        combined_items_df = new_items_df

    combined_items_df.drop_duplicates(subset=["source_system", "procedure_number", "lot_number", "line_no"], keep="last", inplace=True)
    combined_items_df.to_csv(items_path, index=False)

    # Update Marts
    print("Rebuilding Python data marts...")
    combined_lots_df["published_at"] = pd.to_datetime(combined_lots_df["published_at"], errors="coerce")
    combined_lots_df["price_rub"] = pd.to_numeric(combined_lots_df["price_rub"], errors="coerce")
    external_factors_df = pd.read_csv(CURATED_DIR / "external_factors_daily.csv")
    external_factors_df["factor_date"] = pd.to_datetime(external_factors_df["factor_date"], errors="coerce")

    build_monthly_activity_mart(combined_lots_df).to_csv(CURATED_DIR / "mart_monthly_activity.csv", index=False)
    build_yearly_summary_mart(combined_lots_df).to_csv(CURATED_DIR / "mart_yearly_summary.csv", index=False)
    build_category_mix_mart(combined_lots_df).to_csv(CURATED_DIR / "mart_category_mix.csv", index=False)
    build_category_yoy_mart(combined_lots_df).to_csv(CURATED_DIR / "mart_category_yoy.csv", index=False)
    build_anomalies_mart(combined_lots_df).to_csv(CURATED_DIR / "mart_anomalies.csv", index=False)
    
    monthly_macro_df = build_monthly_macro_join_mart(combined_lots_df, external_factors_df)
    monthly_macro_df.to_csv(CURATED_DIR / "mart_monthly_macro_join.csv", index=False)
    
    build_unit_price_benchmarks_mart(combined_items_df).to_csv(CURATED_DIR / "mart_unit_price_benchmarks.csv", index=False)
    build_macro_diagnostics_mart(monthly_macro_df).to_csv(CURATED_DIR / "mart_macro_diagnostics.csv", index=False)

    print("Successfully merged and rebuilt curated datasets.")

if __name__ == "__main__":
    main()
