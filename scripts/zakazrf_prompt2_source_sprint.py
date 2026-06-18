from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from purchase_analysis import entity_resolution
from purchase_analysis.clients import zakazrf
from purchase_analysis.config import RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_json, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "zakazrf_prompt2_full_scope_2026-06-14"
DATE_FROM = datetime(2024, 1, 1)
DATE_TO = datetime(2025, 12, 31, 23, 59, 59)


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    rows = entity_resolution.load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
    if not selected_inns:
        return rows
    return [row for row in rows if row.inn in selected_inns]


def search_kwargs_for_term(term: str) -> tuple[str, dict[str, str]]:
    normalized = entity_resolution.normalize_identifier(term)
    clean_term = normalize_spaces(term)
    if normalized and clean_term == normalized:
        if len(normalized) in {10, 12}:
            return "inn", {"inn": normalized}
        if len(normalized) == 13:
            return "ogrn", {"ogrn": normalized}
        if len(normalized) == 9:
            return "kpp", {"kpp": normalized}
    return "full_name", {"full_name": clean_term}


def merge_candidates(
    existing: list[zakazrf.ZakazRfCustomerCandidate],
    incoming: list[zakazrf.ZakazRfCustomerCandidate],
) -> list[zakazrf.ZakazRfCustomerCandidate]:
    seen = {(item.internal_id, item.inn, item.full_name) for item in existing}
    merged = list(existing)
    for item in incoming:
        key = (item.internal_id, item.inn, item.full_name)
        if key not in seen:
            seen.add(key)
            merged.append(item)
    return merged


def extract_form_state(html_text: str) -> dict[str, str]:
    soup = BeautifulSoup(html_text, "lxml")
    form = soup.select_one("form[id^='form']") or soup.select_one("form")
    if form is None:
        raise ValueError("Could not find ZakazRF form state for pagination")

    values: dict[str, str] = {}
    for element in form.select("input[name], select[name], textarea[name]"):
        name = normalize_spaces(element.get("name"))
        if not name:
            continue
        if element.name == "input":
            input_type = (element.get("type") or "").lower()
            if input_type in {"checkbox", "radio"} and not element.has_attr("checked"):
                continue
            values[name] = element.get("value", "")
            continue
        if element.name == "select":
            selected = element.select("option[selected]")
            if selected:
                values[name] = selected[-1].get("value", "")
            else:
                first = element.select_one("option")
                values[name] = first.get("value", "") if first else ""
            continue
        values[name] = normalize_spaces(element.get_text(" ", strip=True))
    return values


def notifications_index_url(current_url: str) -> str:
    parsed = urlparse(current_url)
    path = parsed.path.rstrip("/")
    if not path.endswith("/Index"):
        path = f"{path}/Index"
    return urlunparse(parsed._replace(path=path))


def fetch_notification_pages(
    first_html: str,
    first_url: str,
    *,
    session: requests.Session,
    timeout: int,
    max_pages: int | None,
) -> list[tuple[int, str, str]]:
    pages = [(1, first_html, first_url)]
    total_rows = zakazrf.parse_total_rows(first_html)
    if total_rows <= 0:
        return pages

    state = extract_form_state(first_html)
    page_id = state.get("_orm_PageID", "")
    if not page_id:
        return pages

    page_size = int(state.get(f"PageSize{page_id}", "20") or 20)
    if page_size <= 0:
        page_size = 20
    page_count = math.ceil(total_rows / page_size)
    if max_pages is not None:
        page_count = min(page_count, max_pages)

    post_url = notifications_index_url(first_url)
    for page_number in range(2, page_count + 1):
        payload = dict(state)
        payload[f"PageNumber{page_id}"] = str(page_number)
        response = session.post(post_url, data=payload, timeout=timeout)
        response.raise_for_status()
        pages.append((page_number, response.text, response.url))
    return pages


def event_date(item: zakazrf.ZakazRfSearchItem) -> tuple[datetime | None, str]:
    for field_name in ("published_at", "application_deadline", "deadline_at"):
        raw_value = getattr(item, field_name, None)
        if not raw_value:
            continue
        try:
            return datetime.fromisoformat(raw_value), field_name
        except ValueError:
            continue
    return None, ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ZakazRF Prompt 2 source sprint.")
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inn", action="append", dest="inns")
    parser.add_argument("--max-pages-per-candidate", type=int, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    selected_inns = set(args.inns or [])
    out_dir = ROOT_DIR / "output" / "source_sprints" / args.batch_name
    raw_dir = RAW_DIR / "zakazrf" / args.batch_name
    ensure_dir(out_dir)
    ensure_dir(raw_dir)

    scope_rows = read_scope(selected_inns or None)
    session = zakazrf.create_session(timeout=60)
    session.trust_env = False

    raw_files_written: list[str] = []
    summary_rows: list[dict[str, object]] = []
    accepted_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    rejected_rows: list[dict[str, object]] = []
    enrichment_rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    registry_html = zakazrf.fetch_registry_page(session=session, timeout=60)
    registry_path = raw_dir / "registry.html"
    write_text(registry_path, registry_html)
    raw_files_written.append(str(registry_path))
    main_page_id = zakazrf.parse_main_page_id(registry_html)

    exact_candidate_entities = 0
    truncated_candidate_pages = 0

    for scope in scope_rows:
        entity_name = scope.entity_name
        slug = safe_slug(entity_name)
        queries_tried: list[str] = []
        query_modes: dict[str, str] = {}
        candidate_counts_by_query: dict[str, int] = {}
        all_candidates: list[zakazrf.ZakazRfCustomerCandidate] = []
        exact_candidates: list[zakazrf.ZakazRfCustomerCandidate] = []
        exact_candidate_keys: set[tuple[str, str, str]] = set()
        notification_total_rows = 0
        notification_page_rows = 0
        in_period_rows = 0
        review_probe_seen: set[tuple[str, str, str, str, str]] = set()

        try:
            dialog_html, dialog_url = zakazrf.fetch_customer_dialog(
                main_page_id,
                dialog_id=f"dialog_{slug}",
                session=session,
                timeout=60,
            )
            dialog_path = raw_dir / f"{slug}_customer_dialog.html"
            write_text(dialog_path, dialog_html)
            raw_files_written.append(str(dialog_path))
            context = zakazrf.parse_customer_dialog_context(
                dialog_html,
                main_page_id=main_page_id,
                dialog_url=dialog_url,
            )

            for query in entity_resolution.build_search_terms(scope, source_system="zakazrf"):
                query_mode, query_kwargs = search_kwargs_for_term(query)
                queries_tried.append(query)
                query_modes[query] = query_mode
                query_suffix = safe_slug(f"{query_mode}_{query}")
                customer_search_html, customer_search_url = zakazrf.search_customer_candidates(
                    context,
                    dialog_id=f"dialog_{slug}",
                    session=session,
                    timeout=60,
                    **query_kwargs,
                )
                search_path = raw_dir / f"{slug}_customer_search_{query_suffix}.html"
                write_text(search_path, customer_search_html)
                raw_files_written.append(str(search_path))

                current_candidates = zakazrf.parse_customer_candidates(customer_search_html)
                candidate_counts_by_query[query] = len(current_candidates)
                all_candidates = merge_candidates(all_candidates, current_candidates)

                for candidate in current_candidates:
                    candidate_decision = entity_resolution.classify_entity_match(
                        scope,
                        candidate_name=candidate.full_name,
                        candidate_inn=candidate.inn,
                        role="customer",
                    )
                    candidate_key = (
                        candidate.internal_id,
                        candidate.inn,
                        candidate.full_name,
                    )
                    if candidate_decision.accepted:
                        if candidate_key not in exact_candidate_keys:
                            exact_candidate_keys.add(candidate_key)
                            exact_candidates.append(candidate)
                            enrichment_rows.extend(
                                row
                                | {
                                    "query_used": query,
                                    "query_mode": query_mode,
                                    "raw_search_file": str(search_path),
                                    "customer_search_url": customer_search_url,
                                }
                                for row in entity_resolution.propose_identity_enrichment(
                                    scope,
                                    source_system="zakazrf",
                                    candidate_name=candidate.full_name,
                                    evidence=(
                                        f"query={query}; search_file={search_path.name}; "
                                        f"candidate_name={normalize_spaces(candidate.full_name)}; inn={candidate.inn}"
                                    ),
                                )
                            )
                        continue

                    probe_key = (
                        query,
                        candidate.internal_id,
                        candidate.inn,
                        candidate.full_name,
                        candidate_decision.reason,
                    )
                    if probe_key in review_probe_seen:
                        continue
                    review_probe_seen.add(probe_key)
                    probe_row = {
                        "stage": "customer_search",
                        "entity_key": scope.entity_id,
                        "entity_name": entity_name,
                        "query": query,
                        "query_mode": query_mode,
                        "candidate_internal_id": candidate.internal_id,
                        "candidate_name": candidate.full_name,
                        "candidate_inn": candidate.inn,
                        "candidate_role_name": candidate.role_name,
                        "candidate_registration_date": candidate.registration_date,
                        "candidate_address": candidate.address,
                        "decision": candidate_decision.decision,
                        "reason": candidate_decision.reason,
                        "confidence": candidate_decision.confidence,
                        "matched_field": candidate_decision.matched_field,
                        "raw_search_file": str(search_path),
                        "customer_search_url": customer_search_url,
                    }
                    if candidate_decision.needs_review:
                        review_rows.append(probe_row)
                    else:
                        rejected_rows.append(probe_row)

            if exact_candidates:
                exact_candidate_entities += 1

            for candidate_rank, candidate in enumerate(exact_candidates, start=1):
                notifications_html, notifications_url = zakazrf.fetch_notifications(
                    candidate.internal_id,
                    session=session,
                    timeout=60,
                )
                notification_pages = fetch_notification_pages(
                    notifications_html,
                    notifications_url,
                    session=session,
                    timeout=60,
                    max_pages=args.max_pages_per_candidate,
                )
                total_rows = zakazrf.parse_total_rows(notifications_html)
                notification_total_rows += total_rows
                if args.max_pages_per_candidate is not None:
                    page_id = extract_form_state(notifications_html).get("_orm_PageID", "")
                    page_size = int(
                        extract_form_state(notifications_html).get(f"PageSize{page_id}", "20") or 20
                    )
                    page_count = math.ceil(total_rows / page_size) if page_size > 0 else 0
                    if page_count > args.max_pages_per_candidate:
                        truncated_candidate_pages += 1

                for page_number, page_html, page_url in notification_pages:
                    page_suffix = "" if page_number == 1 else f"_page_{page_number}"
                    notifications_path = (
                        raw_dir
                        / f"{slug}_customer_{candidate.internal_id}_notifications{page_suffix}.html"
                    )
                    write_text(notifications_path, page_html)
                    raw_files_written.append(str(notifications_path))

                    page_items = zakazrf.parse_notification_rows(
                        page_html,
                        entity_name=entity_name,
                        customer_query=candidate.full_name,
                    )
                    notification_page_rows += len(page_items)

                    for item in page_items:
                        item_date, date_field = event_date(item)
                        if item_date is None:
                            rejected_rows.append(
                                {
                                    "stage": "notification_row",
                                    "entity_key": scope.entity_id,
                                    "entity_name": entity_name,
                                    "candidate_internal_id": candidate.internal_id,
                                    "candidate_name": candidate.full_name,
                                    "procedure_number": item.procedure_number,
                                    "decision": "reject",
                                    "reason": "missing_event_date",
                                    "date_field": "",
                                    "published_at": item.published_at,
                                    "application_deadline": item.application_deadline,
                                    "deadline_at": item.deadline_at,
                                    "raw_notifications_file": str(notifications_path),
                                    "notifications_url": page_url,
                                }
                            )
                            continue
                        if not (DATE_FROM <= item_date <= DATE_TO):
                            rejected_rows.append(
                                {
                                    "stage": "notification_row",
                                    "entity_key": scope.entity_id,
                                    "entity_name": entity_name,
                                    "candidate_internal_id": candidate.internal_id,
                                    "candidate_name": candidate.full_name,
                                    "procedure_number": item.procedure_number,
                                    "decision": "reject",
                                    "reason": "out_of_period",
                                    "date_field": date_field,
                                    "published_at": item.published_at,
                                    "application_deadline": item.application_deadline,
                                    "deadline_at": item.deadline_at,
                                    "raw_notifications_file": str(notifications_path),
                                    "notifications_url": page_url,
                                }
                            )
                            continue

                        in_period_rows += 1
                        item_payload = zakazrf.search_item_to_dict(item)
                        accepted_rows.append(
                            item_payload
                            | {
                                "entity_key": scope.entity_id,
                                "query_used": candidate.full_name,
                                "candidate_rank": candidate_rank,
                                "candidate_internal_id": candidate.internal_id,
                                "candidate_name": candidate.full_name,
                                "candidate_inn": candidate.inn,
                                "candidate_role_name": candidate.role_name,
                                "raw_notifications_file": str(notifications_path),
                                "notifications_url": page_url,
                                "records_total_for_candidate": total_rows,
                                "page_number": page_number,
                                "acceptance_reason": "accepted_by_exact_customer_candidate",
                            }
                        )

            status = "no_exact_candidate"
            if exact_candidates and notification_total_rows == 0:
                status = "exact_probe_zero"
            elif in_period_rows:
                status = "accepted_notifications_need_dedup"
            elif exact_candidates:
                status = "notification_rows_out_of_period_or_empty_page"

            summary_rows.append(
                {
                    "entity_key": scope.entity_id,
                    "entity_name": entity_name,
                    "queries_tried": " | ".join(queries_tried),
                    "query_modes_json": json.dumps(query_modes, ensure_ascii=False),
                    "candidate_counts_by_query_json": json.dumps(
                        candidate_counts_by_query, ensure_ascii=False
                    ),
                    "raw_candidate_count": len(all_candidates),
                    "exact_candidate_count": len(exact_candidates),
                    "notification_total_rows": notification_total_rows,
                    "notification_page_rows": notification_page_rows,
                    "accepted_rows_in_period": in_period_rows,
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
                    "candidate_counts_by_query_json": json.dumps(
                        candidate_counts_by_query, ensure_ascii=False
                    ),
                    "raw_candidate_count": len(all_candidates),
                    "exact_candidate_count": len(exact_candidates),
                    "notification_total_rows": notification_total_rows,
                    "notification_page_rows": notification_page_rows,
                    "accepted_rows_in_period": in_period_rows,
                    "status": f"error:{exc.__class__.__name__}",
                }
            )

    summary_df = pd.DataFrame(summary_rows)
    accepted_df = pd.DataFrame(accepted_rows)
    review_df = pd.DataFrame(review_rows)
    rejected_df = pd.DataFrame(rejected_rows)
    enrichment_df = pd.DataFrame(enrichment_rows)
    if not enrichment_df.empty:
        enrichment_df = enrichment_df.drop_duplicates().reset_index(drop=True)

    if not accepted_df.empty:
        accepted_df = accepted_df.drop_duplicates(
            subset=["entity_key", "procedure_number", "lot_number"]
        ).reset_index(drop=True)

    lots_path = ROOT_DIR / "data" / "curated" / "procurement_lots.csv"
    if lots_path.exists() and not accepted_df.empty:
        lots_df = pd.read_csv(lots_path, encoding="utf-8-sig", dtype=str)
        lot_numbers = lots_df["procedure_number"].astype(str)
        core_numbers = set(lot_numbers)
        accepted_df["duplicate_in_core"] = accepted_df["procedure_number"].astype(str).isin(
            core_numbers
        )
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
    elif exact_candidate_entities:
        conclusion = "exact_probe_zero"
    else:
        conclusion = "probe_only"

    summary_payload = {
        "source_system": "zakazrf",
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
        "exact_candidate_entities": exact_candidate_entities,
        "truncated_candidate_pages": truncated_candidate_pages,
        "errors": len(errors),
        "raw_files_saved": sorted(set(raw_files_written)),
        "conclusion": conclusion,
        "out_dir": str(out_dir),
        "raw_dir": str(raw_dir),
    }

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
