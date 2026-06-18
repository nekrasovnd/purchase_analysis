from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.clients import lot_online
from purchase_analysis.config import RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_json, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug


ROOT_DIR = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://tender.lot-online.ru/etp/app/SearchLots/"
DEFAULT_BATCH_NAME = "lot_online_prompt2_full_scope_2026-06-14"
DATE_FROM = datetime(2024, 1, 1)
DATE_TO = datetime(2025, 12, 31, 23, 59, 59)
PAGE_SIZE = 20


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    rows = entity_resolution.load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
    if not selected_inns:
        return rows
    return [row for row in rows if row.inn in selected_inns]


def query_type_for_term(term: str) -> str:
    normalized = entity_resolution.normalize_identifier(term)
    clean_term = normalize_spaces(term)
    if normalized and clean_term == normalized:
        if len(normalized) in {10, 12}:
            return "inn"
        if len(normalized) == 13:
            return "ogrn"
        if len(normalized) == 9:
            return "kpp"
    return "name"


def probe_plans_for_term(term: str) -> list[tuple[str, dict]]:
    query_type = query_type_for_term(term)
    clean_term = normalize_spaces(term)
    if query_type == "name":
        return [
            ("customer_search", lot_online.build_query_payload(customer_title=clean_term)),
            ("organizer_search", lot_online.build_query_payload(organizer_title=clean_term)),
            ("title_search", lot_online.build_query_payload(title=clean_term)),
        ]
    normalized = entity_resolution.normalize_identifier(term)
    return [
        ("customer_exact", lot_online.build_query_payload(customer_title=normalized)),
        ("organizer_exact", lot_online.build_query_payload(organizer_title=normalized)),
    ]


def write_payload(path: Path, payload: dict) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def event_date(item: lot_online.LotOnlineSearchItem) -> tuple[datetime | None, str]:
    for field_name in ("published_at", "application_deadline", "deadline_at"):
        raw_value = getattr(item, field_name, None)
        if not raw_value:
            continue
        try:
            return datetime.fromisoformat(raw_value), field_name
        except ValueError:
            continue
    return None, ""


def row_reflects_query(item: lot_online.LotOnlineSearchItem, query: str) -> bool:
    query_digits = entity_resolution.normalize_identifier(query)
    if query_digits:
        haystack_digits = "".join(
            [
                entity_resolution.normalize_identifier(item.customer_inn),
                entity_resolution.normalize_identifier(item.organizer_inn),
                entity_resolution.normalize_identifier(item.subject),
            ]
        )
        if query_digits in haystack_digits:
            return True

    query_text = entity_resolution.normalize_name(query)
    if not query_text:
        return False
    haystack = entity_resolution.normalize_name(
        " ".join(
            value
            for value in [
                item.subject,
                item.customer_name,
                item.organizer_name,
            ]
            if normalize_spaces(value)
        )
    )
    return bool(query_text and query_text in haystack)


def candidate_rows_for_item(
    raw_item: dict,
    item: lot_online.LotOnlineSearchItem,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for customer in raw_item.get("customer") or []:
        name = normalize_spaces(customer.get("title"))
        inn = normalize_spaces(customer.get("inn"))
        key = ("customer", name, inn)
        if key in seen or not (name or inn):
            continue
        seen.add(key)
        rows.append(
            {
                "role": "customer",
                "candidate_name": name,
                "candidate_inn": inn,
            }
        )

    organizer = raw_item.get("organizer") or {}
    organizer_name = normalize_spaces(organizer.get("title"))
    organizer_inn = normalize_spaces(organizer.get("inn"))
    organizer_key = ("organizer", organizer_name, organizer_inn)
    if organizer_key not in seen and (organizer_name or organizer_inn):
        seen.add(organizer_key)
        rows.append(
            {
                "role": "organizer",
                "candidate_name": organizer_name,
                "candidate_inn": organizer_inn,
            }
        )

    if rows:
        return rows

    customer_inns = entity_resolution.split_multi(item.customer_inn) or [""]
    for customer_inn in customer_inns:
        key = ("customer", normalize_spaces(item.customer_name), customer_inn)
        if key in seen or not (normalize_spaces(item.customer_name) or customer_inn):
            continue
        seen.add(key)
        rows.append(
            {
                "role": "customer",
                "candidate_name": normalize_spaces(item.customer_name),
                "candidate_inn": customer_inn,
            }
        )

    organizer_key = ("organizer", normalize_spaces(item.organizer_name), normalize_spaces(item.organizer_inn))
    if organizer_key not in seen and (
        normalize_spaces(item.organizer_name) or normalize_spaces(item.organizer_inn)
    ):
        rows.append(
            {
                "role": "organizer",
                "candidate_name": normalize_spaces(item.organizer_name),
                "candidate_inn": normalize_spaces(item.organizer_inn),
            }
        )

    return rows


def build_report_text(
    *,
    batch_name: str,
    scope_rows: list[entity_resolution.EntityIdentity],
    summary_payload: dict[str, object],
    summary_df: pd.DataFrame,
    review_df: pd.DataFrame,
    rejected_df: pd.DataFrame,
    enrichment_df: pd.DataFrame,
) -> str:
    lines = [
        "# Source sprint: LotOnline / full current scope",
        "",
        f"Дата: {datetime.now().date().isoformat()}",
        "",
        "Источник: `LotOnline`",
        "",
        f"URL: `{SOURCE_URL}`",
        "",
        f"Период: `{DATE_FROM.date().isoformat()}` - `{DATE_TO.date().isoformat()}`",
        "",
        "## Scope",
        "",
        "Проверен весь текущий `configs/entity_scope.csv`:",
        "",
        f"- юрлиц: `{len(scope_rows)}`",
        f"- проверок source sprint: `{len(summary_df)}`",
        "- поиск: `build_search_terms(...)` через `customer / organizer / title` и identifier probes",
        "- принятие exact match: только через `classify_entity_match(...)` по структурным `customer/organizer` полям",
        "- период `2024-2025` проверялся локально по `published_at / application_deadline / deadline_at`",
        "",
        "Raw evidence сохранен в:",
        "",
        f"- `{summary_payload['raw_dir']}`",
        "",
        "Итоговые артефакты сохранены в:",
        "",
        f"- `{summary_payload['out_dir']}`",
        "",
        "## Результат",
        "",
        f"- summary rows: `{len(summary_df)}`",
    ]

    status_counts = summary_payload.get("status_counts", {})
    for key, value in status_counts.items():
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(
        [
            f"- accepted new rows: `{summary_payload['accepted_new_rows']}`",
            f"- duplicates: `{summary_payload['duplicates']}`",
            f"- review rows: `{summary_payload['review_count']}`",
            f"- rejected rows: `{int(len(rejected_df))}`",
            f"- enrichment candidates: `{summary_payload['enrichment_candidates']}`",
            f"- exact match entities: `{summary_payload['exact_match_entities']}`",
            f"- query-not-reflected rows: `{summary_payload['query_not_reflected_rows']}`",
            f"- truncated queries: `{summary_payload['truncated_queries']}`",
            f"- errors: `{summary_payload['errors']}`",
        ]
    )

    exact_entities = []
    if not summary_df.empty:
        exact_entities = (
            summary_df.loc[summary_df["exact_match_rows_total"] > 0, "entity_name"]
            .dropna()
            .astype(str)
            .tolist()
        )
    if exact_entities:
        lines.extend(
            [
                "",
                "Структурные exact match rows были найдены для:",
                "",
            ]
        )
        for entity_name in exact_entities:
            lines.append(f"- `{entity_name}`")

    if not rejected_df.empty:
        lines.extend(
            [
                "",
                "## Reject profile",
                "",
            ]
        )
        reject_counts = rejected_df["reason"].fillna("unknown").value_counts().to_dict()
        for key, value in reject_counts.items():
            lines.append(f"- `{key}`: `{int(value)}`")

    if not review_df.empty:
        lines.extend(
            [
                "",
                "## Review profile",
                "",
            ]
        )
        review_counts = review_df["reason"].fillna("unknown").value_counts().to_dict()
        for key, value in review_counts.items():
            lines.append(f"- `{key}`: `{int(value)}`")

    if not enrichment_df.empty:
        lines.extend(
            [
                "",
                "## Identity enrichment",
                "",
                f"В `identity_enrichment_candidates.csv` попали `{len(enrichment_df)}` review-кандидатов.",
            ]
        )

    lines.extend(
        [
            "",
            "## Вывод",
            "",
        ]
    )

    conclusion = str(summary_payload["conclusion"])
    if conclusion == "used_in_pipeline":
        lines.append("`LotOnline` дал новые rows для core после strict entity resolution.")
    elif conclusion == "exact_probe_zero":
        lines.append(
            "`LotOnline` воспроизводится как exact-probe источник, но точных публичных rows `2024-2025` для текущего scope не дал."
        )
    else:
        lines.append(
            "`LotOnline` подтвержден как `probe_only` источник для текущего scope: reproducible search есть, но strict resolver не получил безопасного прироста core rows."
        )

    if int(summary_payload["query_not_reflected_rows"]) > 0:
        lines.extend(
            [
                "",
                "Главное ограничение текущего sprint: часть name-based запросов возвращает rows, где сам query не отражается в `subject/customer/organizer`,",
                "поэтому такие ответы учитываются как probe evidence, а не как пригодная core-выдача.",
            ]
        )

    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LotOnline Prompt 2 source sprint.")
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inn", action="append", dest="inns")
    parser.add_argument("--max-pages-per-query", type=int, default=2)
    parser.add_argument("--max-title-pages-per-query", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    selected_inns = set(args.inns or [])
    out_dir = ROOT_DIR / "output" / "source_sprints" / args.batch_name
    raw_dir = RAW_DIR / "lot_online" / args.batch_name
    ensure_dir(out_dir)
    ensure_dir(raw_dir)

    scope_rows = read_scope(selected_inns or None)
    session = lot_online.create_session(timeout=60)
    session.trust_env = False

    raw_files_written: list[str] = []
    summary_rows: list[dict[str, object]] = []
    accepted_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    rejected_rows: list[dict[str, object]] = []
    enrichment_rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    exact_match_entities = 0
    truncated_queries = 0
    query_not_reflected_rows = 0

    for scope in scope_rows:
        entity_name = scope.entity_name
        slug = safe_slug(entity_name)
        queries_tried: list[str] = []
        query_modes: dict[str, str] = {}
        query_result_counts: dict[str, int] = {}
        pages_fetched = 0
        raw_rows_total = 0
        review_rows_generated = 0
        rejected_rows_generated = 0
        title_mention_rows = 0
        identifier_probe_zero_count = 0
        exact_row_keys: set[tuple[str, str]] = set()
        accepted_row_keys: set[tuple[str, str]] = set()

        try:
            for query in entity_resolution.build_search_terms(scope, source_system="lot_online"):
                query_type = query_type_for_term(query)
                queries_tried.append(query)
                query_modes[query] = query_type

                for probe_mode, payload in probe_plans_for_term(query):
                    max_pages = (
                        args.max_title_pages_per_query
                        if probe_mode == "title_search"
                        else args.max_pages_per_query
                    )
                    pages = lot_online.fetch_all_search_pages(
                        payload,
                        max_pages=max_pages,
                        session=session,
                        timeout=60,
                    )

                    first_payload = pages[0][0] if pages else {}
                    total_count = int(
                        first_payload.get("totalCount")
                        or first_payload.get("count")
                        or len(first_payload.get("list") or [])
                    )
                    expected_pages = math.ceil(total_count / PAGE_SIZE) if total_count else 0
                    if expected_pages > len(pages):
                        truncated_queries += 1
                    query_result_counts[f"{probe_mode}:{query}"] = total_count

                    if query_type != "name" and total_count == 0:
                        identifier_probe_zero_count += 1

                    for page_number, (page_payload, search_url) in enumerate(pages, start=1):
                        query_suffix = safe_slug(f"{probe_mode}_{query}")
                        search_path = raw_dir / f"{slug}_{query_suffix}_page_{page_number}.json"
                        write_payload(search_path, page_payload)
                        raw_files_written.append(str(search_path))
                        pages_fetched += 1

                        parsed_items = lot_online.parse_search_items(
                            page_payload,
                            entity_name=entity_name,
                            customer_query=query,
                        )
                        raw_items = page_payload.get("list") or []

                        for item_index, item in enumerate(parsed_items):
                            raw_rows_total += 1
                            raw_item = raw_items[item_index] if item_index < len(raw_items) else {}
                            query_reflected = row_reflects_query(item, query)
                            candidate_rows = candidate_rows_for_item(raw_item, item)
                            accepted_probe: dict[str, str] | None = None
                            review_probes: list[dict[str, str]] = []

                            for candidate in candidate_rows:
                                decision = entity_resolution.classify_entity_match(
                                    scope,
                                    candidate_name=candidate["candidate_name"],
                                    candidate_inn=candidate["candidate_inn"],
                                    role=candidate["role"],
                                )
                                candidate_payload = candidate | {
                                    "decision": decision.decision,
                                    "reason": decision.reason,
                                    "confidence": decision.confidence,
                                    "matched_field": decision.matched_field,
                                }
                                if decision.accepted and accepted_probe is None:
                                    accepted_probe = candidate_payload
                                elif decision.needs_review:
                                    review_probes.append(candidate_payload)

                            if accepted_probe is not None:
                                exact_key = (item.procedure_number, item.lot_number)
                                exact_row_keys.add(exact_key)

                                item_date, date_field = event_date(item)
                                if not item.procedure_number:
                                    rejected_rows.append(
                                        {
                                            "stage": "search_item",
                                            "entity_key": scope.entity_id,
                                            "entity_name": entity_name,
                                            "query": query,
                                            "query_mode": probe_mode,
                                            "query_type": query_type,
                                            "procedure_number": item.procedure_number,
                                            "lot_number": item.lot_number,
                                            "subject": item.subject,
                                            "candidate_role": accepted_probe["role"],
                                            "candidate_name": accepted_probe["candidate_name"],
                                            "candidate_inn": accepted_probe["candidate_inn"],
                                            "decision": "reject",
                                            "reason": "missing_procedure_number",
                                            "confidence": "high",
                                            "matched_field": accepted_probe["matched_field"],
                                            "published_at": item.published_at,
                                            "application_deadline": item.application_deadline,
                                            "deadline_at": item.deadline_at,
                                            "date_field": date_field,
                                            "query_reflected": query_reflected,
                                            "raw_search_file": str(search_path),
                                            "search_url": search_url,
                                            "page_number": page_number,
                                        }
                                    )
                                    rejected_rows_generated += 1
                                    continue

                                if item_date is None:
                                    rejected_rows.append(
                                        {
                                            "stage": "search_item",
                                            "entity_key": scope.entity_id,
                                            "entity_name": entity_name,
                                            "query": query,
                                            "query_mode": probe_mode,
                                            "query_type": query_type,
                                            "procedure_number": item.procedure_number,
                                            "lot_number": item.lot_number,
                                            "subject": item.subject,
                                            "candidate_role": accepted_probe["role"],
                                            "candidate_name": accepted_probe["candidate_name"],
                                            "candidate_inn": accepted_probe["candidate_inn"],
                                            "decision": "reject",
                                            "reason": "missing_event_date",
                                            "confidence": "high",
                                            "matched_field": accepted_probe["matched_field"],
                                            "published_at": item.published_at,
                                            "application_deadline": item.application_deadline,
                                            "deadline_at": item.deadline_at,
                                            "date_field": "",
                                            "query_reflected": query_reflected,
                                            "raw_search_file": str(search_path),
                                            "search_url": search_url,
                                            "page_number": page_number,
                                        }
                                    )
                                    rejected_rows_generated += 1
                                    continue

                                if not (DATE_FROM <= item_date <= DATE_TO):
                                    rejected_rows.append(
                                        {
                                            "stage": "search_item",
                                            "entity_key": scope.entity_id,
                                            "entity_name": entity_name,
                                            "query": query,
                                            "query_mode": probe_mode,
                                            "query_type": query_type,
                                            "procedure_number": item.procedure_number,
                                            "lot_number": item.lot_number,
                                            "subject": item.subject,
                                            "candidate_role": accepted_probe["role"],
                                            "candidate_name": accepted_probe["candidate_name"],
                                            "candidate_inn": accepted_probe["candidate_inn"],
                                            "decision": "reject",
                                            "reason": "out_of_period",
                                            "confidence": "high",
                                            "matched_field": accepted_probe["matched_field"],
                                            "published_at": item.published_at,
                                            "application_deadline": item.application_deadline,
                                            "deadline_at": item.deadline_at,
                                            "date_field": date_field,
                                            "query_reflected": query_reflected,
                                            "raw_search_file": str(search_path),
                                            "search_url": search_url,
                                            "page_number": page_number,
                                        }
                                    )
                                    rejected_rows_generated += 1
                                    continue

                                accepted_key = (item.procedure_number, item.lot_number)
                                if accepted_key in accepted_row_keys:
                                    continue
                                accepted_row_keys.add(accepted_key)
                                item_payload = lot_online.search_item_to_dict(item)
                                accepted_rows.append(
                                    item_payload
                                    | {
                                        "entity_key": scope.entity_id,
                                        "query_used": query,
                                        "query_mode": probe_mode,
                                        "query_type": query_type,
                                        "matched_role": accepted_probe["role"],
                                        "matched_name": accepted_probe["candidate_name"],
                                        "matched_inn": accepted_probe["candidate_inn"],
                                        "matched_field": accepted_probe["matched_field"],
                                        "acceptance_reason": "accepted_by_structured_exact_identity",
                                        "query_reflected": query_reflected,
                                        "raw_search_file": str(search_path),
                                        "search_url": search_url,
                                        "page_number": page_number,
                                        "records_total_for_query": total_count,
                                    }
                                )
                                enrichment_rows.extend(
                                    row
                                    | {
                                        "query_used": query,
                                        "query_mode": probe_mode,
                                        "query_type": query_type,
                                        "raw_search_file": str(search_path),
                                        "search_url": search_url,
                                    }
                                    for row in entity_resolution.propose_identity_enrichment(
                                        scope,
                                        source_system="lot_online",
                                        candidate_name=accepted_probe["candidate_name"],
                                        evidence=(
                                            f"query={query}; probe_mode={probe_mode}; "
                                            f"procedure={item.procedure_number}; lot={item.lot_number}; "
                                            f"candidate_role={accepted_probe['role']}; "
                                            f"candidate_name={normalize_spaces(accepted_probe['candidate_name'])}; "
                                            f"candidate_inn={accepted_probe['candidate_inn']}"
                                        ),
                                    )
                                )
                                continue

                            if review_probes:
                                for review_probe in review_probes:
                                    review_rows.append(
                                        {
                                            "stage": "structured_candidate",
                                            "entity_key": scope.entity_id,
                                            "entity_name": entity_name,
                                            "query": query,
                                            "query_mode": probe_mode,
                                            "query_type": query_type,
                                            "procedure_number": item.procedure_number,
                                            "lot_number": item.lot_number,
                                            "subject": item.subject,
                                            "candidate_role": review_probe["role"],
                                            "candidate_name": review_probe["candidate_name"],
                                            "candidate_inn": review_probe["candidate_inn"],
                                            "decision": review_probe["decision"],
                                            "reason": review_probe["reason"],
                                            "confidence": review_probe["confidence"],
                                            "matched_field": review_probe["matched_field"],
                                            "published_at": item.published_at,
                                            "application_deadline": item.application_deadline,
                                            "deadline_at": item.deadline_at,
                                            "query_reflected": query_reflected,
                                            "raw_search_file": str(search_path),
                                            "search_url": search_url,
                                            "page_number": page_number,
                                        }
                                    )
                                    review_rows_generated += 1
                                continue

                            if probe_mode == "title_search" and query_reflected:
                                review_rows.append(
                                    {
                                        "stage": "title_search",
                                        "entity_key": scope.entity_id,
                                        "entity_name": entity_name,
                                        "query": query,
                                        "query_mode": probe_mode,
                                        "query_type": query_type,
                                        "procedure_number": item.procedure_number,
                                        "lot_number": item.lot_number,
                                        "subject": item.subject,
                                        "candidate_role": "title_mention",
                                        "candidate_name": "",
                                        "candidate_inn": "",
                                        "decision": "review",
                                        "reason": "title_mention_without_identifier",
                                        "confidence": "medium",
                                        "matched_field": "title",
                                        "published_at": item.published_at,
                                        "application_deadline": item.application_deadline,
                                        "deadline_at": item.deadline_at,
                                        "query_reflected": True,
                                        "raw_search_file": str(search_path),
                                        "search_url": search_url,
                                        "page_number": page_number,
                                    }
                                )
                                review_rows_generated += 1
                                title_mention_rows += 1
                                continue

                            reject_reason = (
                                "query_not_reflected_in_row" if not query_reflected else "no_exact_identity"
                            )
                            if reject_reason == "query_not_reflected_in_row":
                                query_not_reflected_rows += 1
                            rejected_rows.append(
                                {
                                    "stage": "search_item",
                                    "entity_key": scope.entity_id,
                                    "entity_name": entity_name,
                                    "query": query,
                                    "query_mode": probe_mode,
                                    "query_type": query_type,
                                    "procedure_number": item.procedure_number,
                                    "lot_number": item.lot_number,
                                    "subject": item.subject,
                                    "candidate_role": "",
                                    "candidate_name": item.customer_name or item.organizer_name,
                                    "candidate_inn": item.customer_inn or item.organizer_inn,
                                    "decision": "reject",
                                    "reason": reject_reason,
                                    "confidence": "high",
                                    "matched_field": "",
                                    "published_at": item.published_at,
                                    "application_deadline": item.application_deadline,
                                    "deadline_at": item.deadline_at,
                                    "query_reflected": query_reflected,
                                    "raw_search_file": str(search_path),
                                    "search_url": search_url,
                                    "page_number": page_number,
                                }
                            )
                            rejected_rows_generated += 1

            if exact_row_keys:
                exact_match_entities += 1

            accepted_rows_in_period = len(accepted_row_keys)
            exact_match_rows_total = len(exact_row_keys)

            status = "no_exact_candidate"
            if accepted_rows_in_period:
                status = "accepted_rows_need_dedup"
            elif exact_match_rows_total:
                status = "exact_rows_out_of_period"
            elif review_rows_generated:
                status = "review_only"
            elif raw_rows_total == 0:
                status = "zero_results"

            summary_rows.append(
                {
                    "entity_key": scope.entity_id,
                    "entity_name": entity_name,
                    "queries_tried": " | ".join(queries_tried),
                    "query_modes_json": json.dumps(query_modes, ensure_ascii=False),
                    "query_result_counts_json": json.dumps(query_result_counts, ensure_ascii=False),
                    "pages_fetched": pages_fetched,
                    "raw_rows": raw_rows_total,
                    "exact_match_rows_total": exact_match_rows_total,
                    "accepted_rows_in_period": accepted_rows_in_period,
                    "review_rows_generated": review_rows_generated,
                    "rejected_rows_generated": rejected_rows_generated,
                    "title_mention_rows": title_mention_rows,
                    "identifier_probe_zero_count": identifier_probe_zero_count,
                    "status": status,
                }
            )
        except Exception as exc:  # pragma: no cover - source diagnostics
            errors.append({"entity_name": entity_name, "error": repr(exc)})
            summary_rows.append(
                {
                    "entity_key": scope.entity_id,
                    "entity_name": entity_name,
                    "queries_tried": " | ".join(queries_tried),
                    "query_modes_json": json.dumps(query_modes, ensure_ascii=False),
                    "query_result_counts_json": json.dumps(query_result_counts, ensure_ascii=False),
                    "pages_fetched": pages_fetched,
                    "raw_rows": raw_rows_total,
                    "exact_match_rows_total": len(exact_row_keys),
                    "accepted_rows_in_period": len(accepted_row_keys),
                    "review_rows_generated": review_rows_generated,
                    "rejected_rows_generated": rejected_rows_generated,
                    "title_mention_rows": title_mention_rows,
                    "identifier_probe_zero_count": identifier_probe_zero_count,
                    "status": f"error:{exc.__class__.__name__}",
                }
            )

    summary_df = pd.DataFrame(summary_rows)
    accepted_df = pd.DataFrame(accepted_rows)
    review_df = pd.DataFrame(review_rows)
    rejected_df = pd.DataFrame(rejected_rows)
    enrichment_df = pd.DataFrame(enrichment_rows)

    if not accepted_df.empty:
        accepted_df = accepted_df.drop_duplicates(
            subset=["entity_key", "procedure_number", "lot_number"]
        ).reset_index(drop=True)
    if not review_df.empty:
        review_df = review_df.drop_duplicates().reset_index(drop=True)
    if not rejected_df.empty:
        rejected_df = rejected_df.drop_duplicates().reset_index(drop=True)
    if not enrichment_df.empty:
        enrichment_df = enrichment_df.drop_duplicates().reset_index(drop=True)

    lots_path = ROOT_DIR / "data" / "curated" / "procurement_lots.csv"
    if lots_path.exists() and not accepted_df.empty:
        lots_df = pd.read_csv(lots_path, encoding="utf-8-sig", dtype=str)
        lot_numbers = lots_df["procedure_number"].astype(str)
        core_numbers = set(lot_numbers)
        accepted_df["duplicate_in_core"] = accepted_df["procedure_number"].astype(str).isin(core_numbers)
        accepted_df["core_source_system"] = accepted_df["procedure_number"].map(
            lambda number: ";".join(
                sorted(set(lots_df.loc[lot_numbers == str(number), "source_system"].dropna().astype(str)))
            )
        )
        accepted_df["decision"] = accepted_df["duplicate_in_core"].map(
            lambda duplicate: "duplicate_skip_core" if duplicate else "new_candidate_manual_review"
        )
    elif not accepted_df.empty:
        accepted_df["duplicate_in_core"] = False
        accepted_df["core_source_system"] = ""
        accepted_df["decision"] = "new_candidate_manual_review"

    duplicates_df = (
        accepted_df.loc[accepted_df["decision"] == "duplicate_skip_core"].copy()
        if not accepted_df.empty
        else accepted_df.copy()
    )
    accepted_new_df = (
        accepted_df.loc[accepted_df["decision"] == "new_candidate_manual_review"].copy()
        if not accepted_df.empty
        else accepted_df.copy()
    )

    if len(accepted_new_df):
        conclusion = "used_in_pipeline"
    elif len(duplicates_df):
        conclusion = "probe_only"
    elif exact_match_entities:
        conclusion = "exact_probe_zero"
    else:
        conclusion = "probe_only"

    summary_payload = {
        "source_system": "lot_online",
        "batch_name": args.batch_name,
        "scope_entities": len(scope_rows),
        "date_from": DATE_FROM.date().isoformat(),
        "date_to": DATE_TO.date().isoformat(),
        "checks": len(summary_df),
        "status_counts": {
            str(key): int(value)
            for key, value in Counter(summary_df["status"]).items()
        }
        if not summary_df.empty
        else {},
        "accepted_new_rows": len(accepted_new_df),
        "duplicates": len(duplicates_df),
        "review_count": len(review_df),
        "rejected_count_by_reason": {
            str(key): int(value)
            for key, value in rejected_df["reason"].fillna("unknown").value_counts().to_dict().items()
        }
        if not rejected_df.empty
        else {},
        "enrichment_candidates": len(enrichment_df),
        "exact_match_entities": exact_match_entities,
        "query_not_reflected_rows": query_not_reflected_rows,
        "truncated_queries": truncated_queries,
        "errors": len(errors),
        "raw_files_saved": sorted(set(raw_files_written)),
        "conclusion": conclusion,
        "out_dir": str(out_dir),
        "raw_dir": str(raw_dir),
    }

    report_text = build_report_text(
        batch_name=args.batch_name,
        scope_rows=scope_rows,
        summary_payload=summary_payload,
        summary_df=summary_df,
        review_df=review_df,
        rejected_df=rejected_df,
        enrichment_df=enrichment_df,
    )

    summary_df.to_csv(out_dir / "summary.csv", index=False, encoding="utf-8-sig")
    accepted_df.to_csv(out_dir / "accepted_candidate_rows.csv", index=False, encoding="utf-8-sig")
    accepted_new_df.to_csv(out_dir / "accepted_new_rows.csv", index=False, encoding="utf-8-sig")
    duplicates_df.to_csv(out_dir / "duplicates.csv", index=False, encoding="utf-8-sig")
    review_df.to_csv(out_dir / "review_rows.csv", index=False, encoding="utf-8-sig")
    rejected_df.to_csv(out_dir / "rejected_rows.csv", index=False, encoding="utf-8-sig")
    enrichment_df.to_csv(
        out_dir / "identity_enrichment_candidates.csv", index=False, encoding="utf-8-sig"
    )
    write_json(out_dir / "summary.json", summary_payload)
    write_json(out_dir / "errors.json", errors)
    write_text(out_dir / f"{args.batch_name}_report.md", report_text, utf8_bom=True)

    print(summary_df["status"].value_counts().to_string())
    print(f"accepted_new_rows={len(accepted_new_df)}")
    print(f"duplicates={len(duplicates_df)}")
    print(f"review_count={len(review_df)}")
    print(f"rejected_rows={len(rejected_df)}")
    print(f"conclusion={conclusion}")
    print(f"out_dir={out_dir}")
    print(f"raw_dir={raw_dir}")


if __name__ == "__main__":
    main()
