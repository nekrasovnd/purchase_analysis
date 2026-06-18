from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.clients import tender_pro
from purchase_analysis.config import RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_json, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug


ROOT_DIR = Path(__file__).resolve().parents[1]
SOURCE_URL = tender_pro.COMPANY_SEARCH_URL
DEFAULT_BATCH_NAME = "tender_pro_prompt2_full_scope_2026-06-18"
DATE_FROM = datetime(2024, 1, 1)
DATE_TO = datetime(2025, 12, 31, 23, 59, 59)


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


def ordered_search_terms(entity: entity_resolution.EntityIdentity) -> list[str]:
    base_terms = entity_resolution.build_search_terms(entity, source_system="tender_pro")
    priority_map = {
        normalize_spaces(entity.inn): 0,
        normalize_spaces(entity.ogrn): 1,
        normalize_spaces(entity.official_name): 2,
        normalize_spaces(entity.short_name): 3,
        normalize_spaces(entity.entity_name): 4,
    }

    def sort_key(term: str) -> tuple[int, int, str]:
        clean_term = normalize_spaces(term)
        query_type = query_type_for_term(clean_term)
        query_priority = {"inn": 0, "ogrn": 1, "kpp": 2, "name": 3}[query_type]
        explicit_priority = priority_map.get(clean_term, 10)
        return explicit_priority, query_priority, clean_term.casefold()

    return sorted(base_terms, key=sort_key)


def search_requests_for_term(term: str) -> list[tuple[str, dict[str, str]]]:
    query_type = query_type_for_term(term)
    clean_term = normalize_spaces(term)
    normalized = entity_resolution.normalize_identifier(term)
    if query_type == "inn":
        return [("inn_search", {"inn": normalized})]
    if query_type in {"ogrn", "kpp"}:
        return [("title_identifier_fallback", {"title": normalized})]
    return [("title_search", {"title": clean_term})]


def event_date(item: tender_pro.TenderProPurchaseItem) -> tuple[datetime | None, str]:
    for field_name in ("published_at", "application_deadline", "deadline_at"):
        raw_value = getattr(item, field_name, None)
        if not raw_value:
            continue
        try:
            return datetime.fromisoformat(raw_value), field_name
        except ValueError:
            continue
    return None, ""


def within_window(item: tender_pro.TenderProPurchaseItem) -> tuple[bool, str]:
    current_date, field_name = event_date(item)
    if current_date is None:
        return False, "missing_event_date"
    if current_date < DATE_FROM:
        return False, f"{field_name}_before_window"
    if current_date > DATE_TO:
        return False, f"{field_name}_after_window"
    return True, field_name


def load_existing_lot_keys() -> set[tuple[str, str, str]]:
    path = ROOT_DIR / "data" / "curated" / "procurement_lots.csv"
    if not path.exists():
        return set()
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    keys: set[tuple[str, str, str]] = set()
    for record in frame.to_dict("records"):
        key = (
            normalize_spaces(record.get("source_system")),
            normalize_spaces(record.get("procedure_number")),
            normalize_spaces(record.get("lot_number") or "1"),
        )
        if key[0] and key[1]:
            keys.add(key)
    return keys


def write_frame(path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    ensure_dir(path.parent)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame


def report_text(
    *,
    batch_name: str,
    scope_rows: list[entity_resolution.EntityIdentity],
    summary_payload: dict[str, object],
) -> str:
    status_counts = summary_payload.get("status_counts", {})
    lines = [
        "# Source sprint: Tender.Pro / full current scope",
        "",
        f"Дата: {datetime.now().date().isoformat()}",
        "",
        "Источник: `Tender.Pro`",
        "",
        f"URL: `{SOURCE_URL}`",
        "",
        f"Период: `{DATE_FROM.date().isoformat()}` - `{DATE_TO.date().isoformat()}`",
        "",
        "## Scope",
        "",
        f"- юрлиц проверено: `{len(scope_rows)}`",
        f"- batch: `{batch_name}`",
        "- поиск компаний: сначала exact `ИНН`, затем fallback `ОГРН/КПП -> title`, затем точные названия",
        "- core-safe принятие компании: только через `classify_entity_match(...)` по `ИНН/ОГРН/КПП+имя`",
        "- сами закупки берутся только после exact company match по публичной странице `Закупки компании ...`",
        "",
        "## Result",
        "",
    ]
    for key, value in status_counts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            f"- accepted new rows: `{summary_payload['accepted_new_rows']}`",
            f"- duplicates: `{summary_payload['duplicates']}`",
            f"- review rows: `{summary_payload['review_count']}`",
            f"- rejected rows: `{summary_payload['rejected_count']}`",
            f"- enrichment candidates: `{summary_payload['enrichment_candidates']}`",
            f"- exact company matches: `{summary_payload['exact_company_matches']}`",
            f"- raw dir: `{summary_payload['raw_dir']}`",
            f"- out dir: `{summary_payload['out_dir']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prompt 2 source sprint for Tender.Pro exact company matching and public purchases."
    )
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inn", action="append", dest="inns", default=[])
    parser.add_argument("--max-company-pages", type=int, default=10)
    parser.add_argument("--max-exact-companies", type=int, default=8)
    parser.add_argument("--request-timeout", type=int, default=60)
    args = parser.parse_args()

    raw_dir = RAW_DIR / "tender_pro" / args.batch_name
    out_dir = ROOT_DIR / "output" / "source_sprints" / args.batch_name
    ensure_dir(raw_dir)
    ensure_dir(out_dir)

    scope_rows = read_scope(set(args.inns) or None)
    existing_keys = load_existing_lot_keys()
    session = tender_pro.create_session(timeout=args.request_timeout)

    accepted_rows: list[dict[str, object]] = []
    duplicate_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    rejected_rows: list[dict[str, object]] = []
    enrichment_rows: list[dict[str, object]] = []
    matched_company_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()

    for entity in scope_rows:
        entity_slug = safe_slug(entity.entity_name)
        exact_company_matches: dict[str, tuple[tender_pro.TenderProCompanyProfile, str, str, str, str, int]] = {}
        rejected_reason_counter: Counter[str] = Counter()
        search_queries_tried: list[str] = []
        company_candidates_total = 0
        purchase_rows_total = 0
        purchase_pages_fetched = 0
        queries_fetched = 0
        entity_status = "no_exact_candidate"
        cached_profiles: dict[str, tuple[tender_pro.TenderProCompanyProfile, str, str]] = {}
        seen_proc_keys: set[tuple[str, str, str]] = set()

        try:
            for term in ordered_search_terms(entity):
                for search_mode, search_kwargs in search_requests_for_term(term):
                    search_queries_tried.append(f"{search_mode}:{term}")
                    search_html, search_url = tender_pro.fetch_company_search_page(
                        session=session,
                        timeout=args.request_timeout,
                        **search_kwargs,
                    )
                    queries_fetched += 1
                    search_slug = safe_slug(f"{search_mode}_{term}")[:120]
                    write_text(raw_dir / f"{entity_slug}_{queries_fetched:02d}_{search_slug}.html", search_html)

                    candidates = tender_pro.parse_company_candidates(search_html)
                    company_candidates_total += len(candidates)

                    for candidate_rank, candidate in enumerate(candidates, start=1):
                        if candidate.company_id in cached_profiles:
                            profile, company_html, page_url = cached_profiles[candidate.company_id]
                        else:
                            try:
                                company_html, page_url = tender_pro.fetch_url(
                                    candidate.company_url.replace("?sid=", "?active_tab=purchases"),
                                    session=session,
                                    timeout=args.request_timeout,
                                )
                                purchase_pages_fetched += 1
                                write_text(
                                    raw_dir / f"{entity_slug}_company_{candidate.company_id}_purchases_page_1.html",
                                    company_html,
                                )
                                profile = tender_pro.parse_company_profile(company_html, url=page_url)
                                cached_profiles[candidate.company_id] = (profile, company_html, page_url)
                            except Exception as exc:  # pragma: no cover - live transport guard
                                rejected_rows.append(
                                    {
                                        "entity_key": entity.entity_id,
                                        "entity_name": entity.entity_name,
                                        "entity_inn": entity.inn,
                                        "query_used": term,
                                        "search_mode": search_mode,
                                        "search_url": search_url,
                                        "candidate_rank": candidate_rank,
                                        "company_id": candidate.company_id,
                                        "display_name": candidate.display_name,
                                        "company_url": candidate.company_url,
                                        "decision": "reject",
                                        "reason": "candidate_fetch_error",
                                        "error": repr(exc),
                                    }
                                )
                                rejected_reason_counter["candidate_fetch_error"] += 1
                                continue

                        decision = entity_resolution.classify_entity_match(
                            entity,
                            candidate_name=profile.full_name or profile.short_name or candidate.display_name,
                            candidate_inn=profile.inn,
                            candidate_ogrn=profile.ogrn,
                            candidate_kpp=profile.kpp,
                            role="customer",
                        )
                        candidate_row = {
                            "entity_key": entity.entity_id,
                            "entity_name": entity.entity_name,
                            "entity_inn": entity.inn,
                            "query_used": term,
                            "search_mode": search_mode,
                            "search_url": search_url,
                            "candidate_rank": candidate_rank,
                            "company_id": profile.company_id or candidate.company_id,
                            "display_name": candidate.display_name,
                            "full_name": profile.full_name,
                            "short_name": profile.short_name,
                            "company_url": profile.company_url or candidate.company_url,
                            "purchases_url": profile.purchases_url,
                            "candidate_inn": profile.inn,
                            "candidate_kpp": profile.kpp,
                            "candidate_ogrn": profile.ogrn,
                            "roles": profile.roles or candidate.roles,
                            "decision": decision.decision,
                            "confidence": decision.confidence,
                            "reason": decision.reason,
                            "matched_field": decision.matched_field,
                        }
                        if decision.accepted:
                            exact_company_matches[candidate.company_id] = (
                                profile,
                                company_html,
                                page_url,
                                term,
                                search_mode,
                                candidate_rank,
                            )
                        elif decision.needs_review:
                            review_rows.append(candidate_row)
                        else:
                            rejected_rows.append(candidate_row)
                            rejected_reason_counter[decision.reason] += 1

                    if exact_company_matches:
                        break
                if exact_company_matches:
                    break

            if not exact_company_matches:
                entity_status = "no_exact_candidate"
            else:
                matched_items_for_entity = 0
                for company_id, (
                    profile,
                    page_one_html,
                    page_one_url,
                    query_used,
                    search_mode,
                    candidate_rank,
                ) in list(exact_company_matches.items())[: args.max_exact_companies]:
                    matched_company_rows.append(
                        {
                            "entity_key": entity.entity_id,
                            "entity_name": entity.entity_name,
                            "entity_inn": entity.inn,
                            "query_used": query_used,
                            "search_mode": search_mode,
                            "candidate_rank": candidate_rank,
                            "company_id": company_id,
                            "full_name": profile.full_name,
                            "short_name": profile.short_name,
                            "company_url": profile.company_url,
                            "purchases_url": profile.purchases_url,
                            "inn": profile.inn,
                            "kpp": profile.kpp,
                            "ogrn": profile.ogrn,
                            "roles": profile.roles,
                            "region": profile.region,
                        }
                    )
                    enrichment_rows.extend(
                        entity_resolution.propose_identity_enrichment(
                            entity,
                            source_system="tender_pro",
                            candidate_name=profile.full_name,
                            candidate_ogrn=profile.ogrn,
                            candidate_kpp=profile.kpp,
                            evidence=profile.company_url,
                        )
                    )

                    page_urls = tender_pro.parse_purchase_page_urls(page_one_html)
                    page_numbers = tender_pro.parse_purchase_pages(page_one_html, current_url=page_one_url)
                    max_page = min(max(page_numbers or [1]), args.max_company_pages)
                    reference_url = page_urls[0] if page_urls else tender_pro.build_company_view_url(company_id, active_tab="purchases", page=1)

                    for page_number in range(1, max_page + 1):
                        if page_number == 1:
                            current_html, current_url = page_one_html, page_one_url
                        else:
                            current_url = tender_pro.build_paged_url(reference_url, page=page_number)
                            try:
                                current_html, current_url = tender_pro.fetch_url(
                                    current_url,
                                    session=session,
                                    timeout=args.request_timeout,
                                )
                                purchase_pages_fetched += 1
                                write_text(
                                    raw_dir / f"{entity_slug}_company_{company_id}_purchases_page_{page_number}.html",
                                    current_html,
                                )
                            except Exception as exc:  # pragma: no cover - live transport guard
                                rejected_rows.append(
                                    {
                                        "entity_key": entity.entity_id,
                                        "entity_name": entity.entity_name,
                                        "entity_inn": entity.inn,
                                        "query_used": query_used,
                                        "search_mode": search_mode,
                                        "company_id": company_id,
                                        "page_number": page_number,
                                        "decision": "reject",
                                        "reason": "purchase_page_fetch_error",
                                        "error": repr(exc),
                                    }
                                )
                                rejected_reason_counter["purchase_page_fetch_error"] += 1
                                break

                        page_items = tender_pro.parse_purchase_items(
                            current_html,
                            entity_name=entity.entity_name,
                            profile=profile,
                        )
                        purchase_rows_total += len(page_items)
                        page_dates: list[datetime] = []
                        for item in page_items:
                            row = tender_pro.purchase_item_to_dict(item)
                            row.update(
                                {
                                    "entity_key": entity.entity_id,
                                    "query_used": query_used,
                                    "search_mode": search_mode,
                                    "candidate_rank": candidate_rank,
                                    "page_number": page_number,
                                    "search_url": current_url,
                                }
                            )
                            current_date, date_field = event_date(item)
                            if current_date is not None:
                                page_dates.append(current_date)
                                row["event_date_field"] = date_field
                                row["event_date"] = current_date.isoformat()
                            keep_row, keep_reason = within_window(item)
                            row["window_reason"] = keep_reason
                            row_key = (row["source_system"], row["procedure_number"], row["lot_number"])
                            if row_key in seen_proc_keys or row_key in existing_keys:
                                duplicate_rows.append(row)
                                continue
                            if not keep_row:
                                rejected_rows.append(
                                    {
                                        "entity_key": entity.entity_id,
                                        "entity_name": entity.entity_name,
                                        "entity_inn": entity.inn,
                                        "query_used": query_used,
                                        "search_mode": search_mode,
                                        "company_id": company_id,
                                        "procedure_number": row["procedure_number"],
                                        "lot_number": row["lot_number"],
                                        "subject": row["subject"],
                                        "reason": keep_reason,
                                        "decision": "reject",
                                    }
                                )
                                rejected_reason_counter[keep_reason] += 1
                                continue
                            seen_proc_keys.add(row_key)
                            accepted_rows.append(row)
                            matched_items_for_entity += 1

                        if page_dates and max(page_dates) < DATE_FROM:
                            break

                if matched_items_for_entity > 0:
                    entity_status = "accepted_rows"
                else:
                    entity_status = "exact_company_zero_in_window"

            status_counts[entity_status] += 1
            summary_rows.append(
                {
                    "entity_key": entity.entity_id,
                    "entity_name": entity.entity_name,
                    "entity_inn": entity.inn,
                    "status": entity_status,
                    "queries_fetched": queries_fetched,
                    "queries_tried": " | ".join(search_queries_tried),
                    "company_candidates_total": company_candidates_total,
                    "exact_company_matches": len(exact_company_matches),
                    "purchase_pages_fetched": purchase_pages_fetched,
                    "purchase_rows_total": purchase_rows_total,
                    "accepted_rows_total": sum(1 for row in accepted_rows if row.get("entity_key") == entity.entity_id),
                    "duplicates_total": sum(1 for row in duplicate_rows if row.get("entity_key") == entity.entity_id),
                    "rejected_reasons": json.dumps(dict(rejected_reason_counter), ensure_ascii=False),
                }
            )
        except Exception as exc:  # pragma: no cover - operational safety
            entity_status = "error"
            status_counts[entity_status] += 1
            summary_rows.append(
                {
                    "entity_key": entity.entity_id,
                    "entity_name": entity.entity_name,
                    "entity_inn": entity.inn,
                    "status": entity_status,
                    "queries_fetched": queries_fetched,
                    "queries_tried": " | ".join(search_queries_tried),
                    "company_candidates_total": company_candidates_total,
                    "exact_company_matches": len(exact_company_matches),
                    "purchase_pages_fetched": purchase_pages_fetched,
                    "purchase_rows_total": purchase_rows_total,
                    "accepted_rows_total": sum(1 for row in accepted_rows if row.get("entity_key") == entity.entity_id),
                    "duplicates_total": sum(1 for row in duplicate_rows if row.get("entity_key") == entity.entity_id),
                    "rejected_reasons": json.dumps(dict(rejected_reason_counter), ensure_ascii=False),
                    "error": repr(exc),
                }
            )

    summary_payload = {
        "source_system": "tender_pro",
        "batch_name": args.batch_name,
        "source_url": SOURCE_URL,
        "scope_entities": len(scope_rows),
        "status_counts": dict(status_counts),
        "accepted_new_rows": len(accepted_rows),
        "duplicates": len(duplicate_rows),
        "review_count": len(review_rows),
        "rejected_count": len(rejected_rows),
        "enrichment_candidates": len(enrichment_rows),
        "exact_company_matches": len(matched_company_rows),
        "raw_dir": str(raw_dir),
        "out_dir": str(out_dir),
    }

    write_json(out_dir / "summary.json", summary_payload)
    write_frame(out_dir / "summary.csv", summary_rows)
    write_frame(out_dir / "accepted_new_rows.csv", accepted_rows)
    write_frame(out_dir / "duplicates.csv", duplicate_rows)
    write_frame(out_dir / "review_candidates.csv", review_rows)
    write_frame(out_dir / "rejected_rows.csv", rejected_rows)
    write_frame(out_dir / "matched_companies.csv", matched_company_rows)
    write_frame(out_dir / "identity_enrichment_candidates.csv", enrichment_rows)
    write_text(
        out_dir / "report.md",
        report_text(batch_name=args.batch_name, scope_rows=scope_rows, summary_payload=summary_payload),
    )


if __name__ == "__main__":
    main()
