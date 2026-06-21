import pandas as pd
from pathlib import Path

ROOT = Path("d:/Nikita/Work/purchase_analysis")
SCOPE_PATH = ROOT / "configs/entity_scope.csv"
COVERAGE_PATH = ROOT / "data/curated/entity_coverage.csv"

def main():
    scope_df = pd.read_csv(SCOPE_PATH, dtype=str, keep_default_na=False)
    coverage_df = pd.read_csv(COVERAGE_PATH, dtype=str, keep_default_na=False)

    # We want to update `inn` and `ogrn` (and other base columns) in coverage_df using scope_df
    # Match by `entity_name`
    scope_lookup = scope_df.set_index("entity_name")[["inn", "ogrn", "entity_type", "is_priority_focus", "eis_search_term", "roseltorg_customer_query"]]

    for idx, row in coverage_df.iterrows():
        name = row["entity_name"]
        if name in scope_lookup.index:
            scope_row = scope_lookup.loc[name]
            coverage_df.at[idx, "inn"] = scope_row["inn"]
            coverage_df.at[idx, "ogrn"] = scope_row["ogrn"]
            coverage_df.at[idx, "entity_type"] = scope_row["entity_type"]
            coverage_df.at[idx, "is_priority_focus"] = scope_row["is_priority_focus"]
            coverage_df.at[idx, "eis_search_term"] = scope_row["eis_search_term"]
            coverage_df.at[idx, "roseltorg_customer_query"] = scope_row["roseltorg_customer_query"]

    coverage_df.to_csv(COVERAGE_PATH, index=False)
    print("Patched entity_coverage.csv successfully.")

if __name__ == "__main__":
    main()
