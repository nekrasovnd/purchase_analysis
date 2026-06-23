from __future__ import annotations

import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Iterable

from purchase_analysis.utils.text import normalize_spaces


SAFE_CORE_ROLES = {
    "customer",
    "buyer",
    "organizer",
    "заказчик",
    "покупатель",
    "организатор",
}
UNSAFE_CORE_ROLES = {
    "supplier",
    "seller",
    "operator",
    "platform",
    "title_mention",
    "text_mention",
    "поставщик",
    "продавец",
    "оператор",
    "площадка",
    "упоминание",
}


@dataclass(slots=True)
class EntityIdentity:
    entity_id: str
    group_name: str
    entity_name: str
    entity_type: str
    inn: str = ""
    ogrn: str = ""
    kpp_list: list[str] = field(default_factory=list)
    official_name: str = ""
    short_name: str = ""
    brand_aliases: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    eis_search_term: str = ""
    roseltorg_customer_query: str = ""
    is_priority_focus: bool = False
    identity_source: str = ""
    identity_confidence: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class EntityMatchDecision:
    decision: str
    confidence: str
    reason: str
    matched_field: str = ""

    @property
    def accepted(self) -> bool:
        return self.decision == "accept"

    @property
    def needs_review(self) -> bool:
        return self.decision == "review"


def normalize_identifier(value: str | None) -> str:
    return re.sub(r"\D+", "", value or "")


def split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    values: list[str] = []
    for item in re.split(r"[;|]", value):
        item = normalize_spaces(item)
        if item and item not in values:
            values.append(item)
    return values


def _parse_bool(value: str | None) -> bool:
    return normalize_spaces(value).lower() in {"1", "true", "yes", "y", "да"}


def parse_json_list(value: str | None, *, field_name: str = "value") -> list[str]:
    cleaned = normalize_spaces(value)
    if not cleaned:
        return []
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be a JSON array") from exc
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"{field_name} must be a JSON array of strings")
    return _dedupe(payload)


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = normalize_spaces(raw_value)
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def remove_parenthetical(value: str | None) -> str:
    return normalize_spaces(re.sub(r"\([^)]*\)", " ", value or ""))


def parenthetical_terms(value: str | None) -> list[str]:
    return _dedupe(re.findall(r"\(([^)]*)\)", value or ""))


def strip_legal_form(value: str | None) -> str:
    result = remove_parenthetical(value)
    legal_patterns = (
        r"^(?:ПАО|АО|ООО|ОАО|ЗАО)\s+",
        r"^ПУБЛИЧНОЕ\s+АКЦИОНЕРНОЕ\s+ОБЩЕСТВО\s+",
        r"^АКЦИОНЕРНОЕ\s+ОБЩЕСТВО\s+",
        r"^ОБЩЕСТВО\s+С\s+ОГРАНИЧЕННОЙ\s+ОТВЕТСТВЕННОСТЬЮ\s+",
    )
    for pattern in legal_patterns:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    return normalize_spaces(result.strip(" \"'«»"))


def normalize_name(value: str | None) -> str:
    value = normalize_spaces(value).casefold()
    value = value.replace("ё", "е")
    value = re.sub(r"[\"'«»(),.]", " ", value)
    value = re.sub(r"[-–—]+", " ", value)
    return normalize_spaces(value)


def normalize_name_without_legal_form(value: str | None) -> str:
    return normalize_name(strip_legal_form(value))


def legal_name_variants(entity: EntityIdentity) -> list[str]:
    source_name = entity.entity_name or entity.short_name or entity.official_name
    clean_name = remove_parenthetical(source_name)
    short_name = entity.short_name or strip_legal_form(source_name)
    if not short_name:
        return []
    upper_clean = clean_name.upper()
    variants: list[str] = []
    if upper_clean.startswith("ООО "):
        variants.append(f'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "{short_name}"')
    elif upper_clean.startswith("АО "):
        variants.append(f'АКЦИОНЕРНОЕ ОБЩЕСТВО "{short_name}"')
    elif upper_clean.startswith("ПАО "):
        variants.append(f'ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "{short_name}"')
    return variants


def load_entity_scope(path: Path) -> list[EntityIdentity]:
    rows: list[EntityIdentity] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for index, row in enumerate(reader, start=1):
            entity_name = normalize_spaces(row.get("entity_name"))
            entity_id = normalize_spaces(row.get("entity_key") or row.get("entity_id")) or f"entity_{index:03d}"
            rows.append(
                EntityIdentity(
                    entity_id=entity_id,
                    group_name=normalize_spaces(row.get("group_name")),
                    entity_name=entity_name,
                    entity_type=normalize_spaces(row.get("entity_type")),
                    inn=normalize_identifier(row.get("inn")),
                    ogrn=normalize_identifier(row.get("ogrn")),
                    kpp_list=[normalize_identifier(value) for value in split_multi(row.get("kpp_list"))],
                    official_name=normalize_spaces(row.get("official_name")) or entity_name,
                    short_name=normalize_spaces(row.get("short_name")) or strip_legal_form(entity_name),
                    brand_aliases=split_multi(row.get("brand_aliases")),
                    search_terms=split_multi(row.get("search_terms")),
                    aliases=parse_json_list(row.get("aliases"), field_name=f"aliases row {index}"),
                    eis_search_term=normalize_spaces(row.get("eis_search_term")) or entity_name,
                    roseltorg_customer_query=normalize_spaces(row.get("roseltorg_customer_query"))
                    or entity_name.upper(),
                    is_priority_focus=_parse_bool(row.get("is_priority_focus")),
                    identity_source=normalize_spaces(row.get("identity_source")),
                    identity_confidence=normalize_spaces(row.get("identity_confidence")),
                    notes=normalize_spaces(row.get("notes")),
                )
            )
    return rows


def identity_names(entity: EntityIdentity) -> list[str]:
    return _dedupe(
        [
            entity.official_name,
            entity.entity_name,
            entity.short_name,
            remove_parenthetical(entity.entity_name),
            entity.eis_search_term,
            entity.roseltorg_customer_query,
            *entity.brand_aliases,
            *entity.search_terms,
            *entity.aliases,
            *legal_name_variants(entity),
            *parenthetical_terms(entity.entity_name),
        ]
    )


def build_search_terms(
    entity: EntityIdentity,
    source_system: str = "generic",
    include_identifiers: bool = True,
) -> list[str]:
    source = source_system.lower()
    identifier_terms: list[str] = []
    if include_identifiers:
        identifier_terms.extend([entity.inn, entity.ogrn])
        if source in {"zakazrf", "sberbank_ast", "ast", "generic"}:
            identifier_terms.extend(entity.kpp_list)

    source_specific: list[str] = []
    if source == "eis":
        source_specific = [entity.eis_search_term, entity.official_name, entity.entity_name]
    elif source == "roseltorg":
        source_specific = [entity.roseltorg_customer_query, entity.eis_search_term, entity.official_name]
    else:
        source_specific = [entity.eis_search_term, entity.roseltorg_customer_query, entity.official_name]

    return _dedupe(
        [
            *source_specific,
            *identifier_terms,
            *entity.search_terms,
            *entity.aliases,
            entity.short_name,
            remove_parenthetical(entity.entity_name),
            *entity.brand_aliases,
            *legal_name_variants(entity),
            *parenthetical_terms(entity.entity_name),
        ]
    )


def is_safe_core_role(role: str | None) -> bool:
    role_norm = normalize_name(role)
    if not role_norm:
        return True
    if any(unsafe in role_norm for unsafe in UNSAFE_CORE_ROLES):
        return False
    if any(safe in role_norm for safe in SAFE_CORE_ROLES):
        return True
    return True


def classify_entity_match(
    entity: EntityIdentity,
    *,
    candidate_name: str | None = None,
    candidate_inn: str | None = None,
    candidate_ogrn: str | None = None,
    candidate_kpp: str | None = None,
    role: str | None = "customer",
) -> EntityMatchDecision:
    if not is_safe_core_role(role):
        return EntityMatchDecision("reject", "high", "unsafe_core_role", "role")

    candidate_inn_norm = normalize_identifier(candidate_inn)
    candidate_ogrn_norm = normalize_identifier(candidate_ogrn)
    candidate_kpp_norm = normalize_identifier(candidate_kpp)

    if entity.inn and candidate_inn_norm == entity.inn:
        return EntityMatchDecision("accept", "high", "inn_exact", "inn")
    if entity.ogrn and candidate_ogrn_norm == entity.ogrn:
        return EntityMatchDecision("accept", "high", "ogrn_exact", "ogrn")

    candidate_name_norm = normalize_name(candidate_name)
    candidate_name_short_norm = normalize_name_without_legal_form(candidate_name)
    trusted_names = {normalize_name(name) for name in identity_names(entity)}
    trusted_short_names = {normalize_name_without_legal_form(name) for name in identity_names(entity)}

    if (
        candidate_kpp_norm
        and candidate_kpp_norm in set(entity.kpp_list)
        and candidate_name_norm
        and candidate_name_norm in trusted_names
    ):
        return EntityMatchDecision("accept", "medium", "kpp_and_exact_name", "kpp+name")

    if candidate_name_norm and candidate_name_norm in trusted_names:
        return EntityMatchDecision("review", "medium", "exact_name_without_identifier", "name")
    if candidate_name_short_norm and candidate_name_short_norm in trusted_short_names:
        return EntityMatchDecision("review", "medium", "short_name_without_identifier", "name")

    return EntityMatchDecision("reject", "high", "no_exact_identity", "")


def enrichment_row(
    entity: EntityIdentity,
    *,
    source_system: str,
    field_name: str,
    proposed_value: str,
    evidence: str,
    confidence: str,
    decision: str = "review",
) -> dict[str, str]:
    return {
        "entity_key": entity.entity_id,
        "entity_name": entity.entity_name,
        "inn": entity.inn,
        "source_system": source_system,
        "field_name": field_name,
        "proposed_value": normalize_spaces(proposed_value),
        "evidence": normalize_spaces(evidence),
        "confidence": confidence,
        "decision": decision,
    }


def propose_identity_enrichment(
    entity: EntityIdentity,
    *,
    source_system: str,
    candidate_name: str | None = None,
    candidate_ogrn: str | None = None,
    candidate_kpp: str | None = None,
    evidence: str,
    confidence: str = "high",
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    candidate_ogrn_norm = normalize_identifier(candidate_ogrn)
    if candidate_ogrn_norm and not entity.ogrn:
        rows.append(
            enrichment_row(
                entity,
                source_system=source_system,
                field_name="ogrn",
                proposed_value=candidate_ogrn_norm,
                evidence=evidence,
                confidence=confidence,
            )
        )

    candidate_kpp_norm = normalize_identifier(candidate_kpp)
    if candidate_kpp_norm and candidate_kpp_norm not in set(entity.kpp_list):
        rows.append(
            enrichment_row(
                entity,
                source_system=source_system,
                field_name="kpp",
                proposed_value=candidate_kpp_norm,
                evidence=evidence,
                confidence=confidence,
            )
        )

    candidate_name_clean = normalize_spaces(candidate_name)
    trusted_names = {normalize_name(name) for name in identity_names(entity)}
    if candidate_name_clean and normalize_name(candidate_name_clean) not in trusted_names:
        rows.append(
            enrichment_row(
                entity,
                source_system=source_system,
                field_name="official_name",
                proposed_value=candidate_name_clean,
                evidence=evidence,
                confidence=confidence,
            )
        )

    return rows
