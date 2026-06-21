import pandas as pd
from pathlib import Path

ROOT = Path("d:/Nikita/Work/purchase_analysis")
SCOPE_PATH = ROOT / "configs/entity_scope.csv"
COVERAGE_PATH = ROOT / "data/curated/entity_coverage.csv"

def main():
    scope_df = pd.read_csv(SCOPE_PATH, dtype=str, keep_default_na=False)
    coverage_df = pd.read_csv(COVERAGE_PATH, dtype=str, keep_default_na=False)

    # Convert old coverage to lookup by INN (ignoring empty INNs)
    # If there are duplicates, keep the first one
    old_by_inn = coverage_df[coverage_df["inn"] != ""].drop_duplicates(subset=["inn"]).set_index("inn")
    
    new_rows = []
    
    columns = coverage_df.columns.tolist()

    for _, scope_row in scope_df.iterrows():
        new_row = {col: "" for col in columns}
        
        # Base fields from scope
        for col in ["group_name", "entity_name", "entity_type", "inn", "is_priority_focus", "eis_search_term", "roseltorg_customer_query"]:
            if col in scope_row:
                new_row[col] = scope_row[col]
                
        inn = scope_row["inn"]
        if inn and inn in old_by_inn.index:
            old_row = old_by_inn.loc[inn]
            # Copy all fields from old_row that we didn't just populate
            for col in columns:
                if col not in ["group_name", "entity_name", "entity_type", "inn", "is_priority_focus", "eis_search_term", "roseltorg_customer_query"]:
                    new_row[col] = old_row[col]
                    
        new_rows.append(new_row)
        
    new_coverage = pd.DataFrame(new_rows, columns=columns)
    new_coverage.to_csv(COVERAGE_PATH, index=False)
    print("Rebuilt entity_coverage.csv successfully.")

if __name__ == "__main__":
    main()
