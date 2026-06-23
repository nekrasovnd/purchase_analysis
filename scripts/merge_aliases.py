from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from purchase_analysis import entity_resolution
from purchase_analysis.config import ROOT_DIR
from purchase_analysis.utils.text import normalize_spaces


DEFAULT_SCOPE_CSV = ROOT_DIR / "configs" / "entity_scope.csv"
DEFAULT_CANDIDATE_DIR = ROOT_DIR / "output" / "source_sprints"


def load_scope(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or []), list(reader)


def save_scope(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize_alias(value: str) -> str:
    return normalize_spaces(value).replace('"', "").replace("'", "").casefold()


def read_aliases(row: dict[str, str]) -> list[str]:
    return entity_resolution.parse_json_list(row.get("aliases"), field_name=f"aliases for {row.get('entity_key')}")


def dump_aliases(values: Iterable[str]) -> str:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = normalize_spaces(raw_value)
        key = normalize_alias(value)
        if value and key not in seen:
            seen.add(key)
            deduped.append(value)
    return json.dumps(deduped, ensure_ascii=False)


def candidate_alias_value(row: dict[str, str], *, include_candidate_name: bool = False) -> str:
    if include_candidate_name and normalize_spaces(row.get("candidate_name")):
        return normalize_spaces(row.get("candidate_name"))
    if normalize_spaces(row.get("field_name")) in {"official_name", "alias", "aliases"}:
        return normalize_spaces(row.get("proposed_value"))
    return ""


def load_candidate_aliases(
    candidate_dir: Path,
    *,
    allowed_decisions: set[str],
    include_candidate_name: bool = False,
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for path in sorted(candidate_dir.glob("*/identity_enrichment_candidates.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                decision = normalize_spaces(row.get("decision")).casefold()
                if decision not in allowed_decisions:
                    continue
                entity_key = normalize_spaces(row.get("entity_key"))
                value = candidate_alias_value(row, include_candidate_name=include_candidate_name)
                if entity_key and value:
                    result[entity_key].append(value)
    return dict(result)


def merge_aliases(
    rows: list[dict[str, str]],
    candidates_by_entity: dict[str, list[str]],
) -> tuple[int, list[str]]:
    changed = 0
    messages: list[str] = []
    rows_by_key = {normalize_spaces(row.get("entity_key")): row for row in rows}

    for entity_key, candidates in sorted(candidates_by_entity.items()):
        row = rows_by_key.get(entity_key)
        if not row:
            continue
        current_aliases = read_aliases(row)
        existing = {normalize_alias(value) for value in [row.get("entity_name", ""), *current_aliases]}
        additions: list[str] = []
        for candidate in candidates:
            key = normalize_alias(candidate)
            if key and key not in existing:
                existing.add(key)
                additions.append(candidate)
        if not additions:
            continue
        row["aliases"] = dump_aliases([*current_aliases, *additions])
        changed += len(additions)
        messages.append(f"{entity_key}: +{len(additions)} aliases -> {', '.join(additions)}")

    return changed, messages


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Review helper for JSON aliases in configs/entity_scope.csv. "
            "Deprecated for normal pipeline runs; use only after manual review."
        )
    )
    parser.add_argument("--scope", type=Path, default=DEFAULT_SCOPE_CSV)
    parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--decision", action="append", default=["accept"])
    parser.add_argument(
        "--include-candidate-name",
        action="store_true",
        help="Also treat candidate_name as an alias proposal. Requires careful manual review.",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to entity_scope.csv.")
    args = parser.parse_args()

    if not args.candidate_dir.exists():
        raise SystemExit(f"No source sprints found in {args.candidate_dir}")

    fieldnames, scope_rows = load_scope(args.scope)
    if "aliases" not in fieldnames:
        fieldnames.append("aliases")
        for row in scope_rows:
            row.setdefault("aliases", "[]")

    allowed_decisions = {normalize_spaces(value).casefold() for value in args.decision}
    candidates = load_candidate_aliases(
        args.candidate_dir,
        allowed_decisions=allowed_decisions,
        include_candidate_name=args.include_candidate_name,
    )
    changed, messages = merge_aliases(scope_rows, candidates)

    print("merge_aliases is a review helper, not part of the default pipeline.")
    print(f"Candidate entity keys: {len(candidates)}")
    print(f"Alias additions proposed: {changed}")
    for message in messages:
        print(f"  {message}")

    if not args.apply:
        print("Dry run: no file written. Re-run with --apply after manual review.")
        return

    save_scope(args.scope, fieldnames, scope_rows)
    print(f"Updated {args.scope}")


if __name__ == "__main__":
    main()
