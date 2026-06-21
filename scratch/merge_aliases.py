import pandas as pd
from pathlib import Path
import json

ROOT = Path("d:/Nikita/Work/purchase_analysis")
SCOPE_FILE = ROOT / "configs" / "entity_scope.csv"
DECISIONS_FILE = ROOT / "output/source_sprints/sberbank-ast-prompt2-full-scope-2026-06-19/candidate_decisions.csv"

# Load scope
scope_df = pd.read_csv(SCOPE_FILE, dtype=str, keep_default_na=False)

# Load decisions
dec_df = pd.read_csv(DECISIONS_FILE, dtype=str, keep_default_na=False)
accept_df = dec_df[dec_df["decision"] == "accept"]

# Group aliases by entity_key
aliases_to_add = {}
for _, row in accept_df.iterrows():
    key = row["entity_key"]
    name = row["candidate_name"].strip()
    if not name:
        continue
    if key not in aliases_to_add:
        aliases_to_add[key] = set()
    aliases_to_add[key].add(name)

# Update scope
updated_rows = []
for _, row in scope_df.iterrows():
    row_dict = row.to_dict()
    key = row_dict["entity_key"]
    if key in aliases_to_add:
        existing_aliases = []
        if row_dict.get("aliases"):
            try:
                # the aliases are stored as JSON list strings in CSV
                existing_aliases = json.loads(row_dict["aliases"])
            except:
                existing_aliases = [x.strip() for x in row_dict["aliases"].split("|") if x.strip()]
        
        if not isinstance(existing_aliases, list):
            existing_aliases = []
            
        combined = set(existing_aliases)
        combined.update(aliases_to_add[key])
        
        # Remove empty or identical to official/short
        to_remove = set()
        for a in combined:
            if a.lower() == str(row_dict.get("official_name", "")).lower() or a.lower() == str(row_dict.get("short_name", "")).lower():
                to_remove.add(a)
        
        combined = list(combined - to_remove)
        row_dict["aliases"] = json.dumps(combined, ensure_ascii=False) if combined else ""
        
    updated_rows.append(row_dict)

# Save scope
out_df = pd.DataFrame(updated_rows)
out_df.to_csv(SCOPE_FILE, index=False, encoding="utf-8-sig")
print(f"Added aliases to {len(aliases_to_add)} entities in entity_scope.csv")
