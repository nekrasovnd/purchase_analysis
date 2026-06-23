from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
import time

import pandas as pd

from purchase_analysis import entity_resolution, source_sprint
from purchase_analysis.clients import b2b_center
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "b2b_center_prompt2_full_scope_2026-06-18"
DATE_FROM = source_sprint.DATE_SCOPE_START
DATE_TO = source_sprint.DATE_SCOPE_END


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    return source_sprint.read_scope(selected_inns, scope_path=ROOT_DIR / "configs" / "entity_scope.csv")


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
    base_terms = entity_resolution.build_search_terms(entity, source_system="generic")
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


def format_dmy(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def split_window(start: date, end: date) -> tuple[tuple[date, date], tuple[date, date]]:
    midpoint = start + timedelta(days=(end - start).days // 2)
    return (start, midpoint), (midpoint + timedelta(days=1), end)


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


def classify_transport_error(exc: Exception) -> str:
    text = repr(exc).lower()
    if "403" in text or "forbidden" in text:
        return "forbidden"
    if "429" in text:
        return "rate_limited"
    return repr(exc)


def collect_window_items(
    *,
    entity: entity_resolution.EntityIdentity,
    candidate: b2b_center.B2BCenterOrganizationCandidate,
    query_used: str,
    show: str,
    start: date,
    end: date,
    session,
    timeout: int,
    raw_dir: Path,
    window_counter: list[int],
    overflow_rows: list[dict[str, object]],
    throttle_seconds: float,
) -> list[dict[str, object]]:
    window_counter[0] += 1
    html = ""
    url = ""
    last_error = ""
    for attempt in range(3):
        try:
            html, url = b2b_center.fetch_search_page(
                organization_id=candidate.organization_id,
                role_mode=candidate.role_mode,
                show=show,
                date_kind="1",
                date_start=format_dmy(start),
                date_end=format_dmy(end),
                session=session,
                timeout=timeout,
            )
        except Exception as exc:  # pragma: no cover - live transport guard
            last_error = classify_transport_error(exc)
            time.sleep(max(throttle_seconds, 0.5) * (attempt + 1))
            continue
        if not b2b_center.is_rate_limited_page(html) and not b2b_center.is_forbidden_page(html):
            break
        
        if hasattr(session, "pause_for_challenge"):
            session.pause_for_challenge(reason="Rate limit or CAPTCHA detected on search page")
            resp = session.current_page_content()
            html = resp.text
            url = resp.url
            if not b2b_center.is_rate_limited_page(html) and not b2b_center.is_forbidden_page(html):
                break

        last_error = "forbidden" if b2b_center.is_forbidden_page(html) else "rate_limited"
        time.sleep(max(throttle_seconds, 1.0) * (attempt + 1))
    else:
        overflow_rows.append(
            {
                "entity_key": entity.entity_id,
                "entity_name": entity.entity_name,
                "query_used": query_used,
                "role_mode": candidate.role_mode,
                "organization_id": candidate.organization_id,
                "organization_name": candidate.name,
                "organization_inn": candidate.inn,
                "date_start": format_dmy(start),
                "date_end": format_dmy(end),
                "search_url": url,
                "reason": last_error or "window_fetch_error",
                "error": last_error,
            }
        )
        return []

    if throttle_seconds > 0:
        time.sleep(throttle_seconds)

    slug = safe_slug(
        f"{candidate.role_mode}_{candidate.organization_id}_{format_dmy(start)}_{format_dmy(end)}"
    )
    write_text(raw_dir / f"{entity.entity_id}_{slug}.html", html)
    if b2b_center.search_has_pager(html):
        if start >= end:
            overflow_rows.append(
                {
                    "entity_key": entity.entity_id,
                    "entity_name": entity.entity_name,
                    "query_used": query_used,
                    "role_mode": candidate.role_mode,
                    "organization_id": candidate.organization_id,
                    "organization_name": candidate.name,
                    "organization_inn": candidate.inn,
                    "date_start": format_dmy(start),
                    "date_end": format_dmy(end),
                    "search_url": url,
                    "reason": "single_day_window_still_has_pager",
                }
            )
            return []
        left, right = split_window(start, end)
        return [
            *collect_window_items(
                entity=entity,
                candidate=candidate,
                query_used=query_used,
                show=show,
                start=left[0],
                end=left[1],
                session=session,
                timeout=timeout,
                raw_dir=raw_dir,
                window_counter=window_counter,
                overflow_rows=overflow_rows,
                throttle_seconds=throttle_seconds,
            ),
            *collect_window_items(
                entity=entity,
                candidate=candidate,
                query_used=query_used,
                show=show,
                start=right[0],
                end=right[1],
                session=session,
                timeout=timeout,
                raw_dir=raw_dir,
                window_counter=window_counter,
                overflow_rows=overflow_rows,
                throttle_seconds=throttle_seconds,
            ),
        ]

    items = b2b_center.parse_search_items(
        html,
        entity_name=entity.entity_name,
        customer_query=query_used,
        role_mode=candidate.role_mode,
        show=show,
        organization_name=candidate.name,
        organization_inn=candidate.inn,
    )
    rows: list[dict[str, object]] = []
    for item in items:
        row = b2b_center.search_item_to_dict(item)
        row.update(
            {
                "query_used": query_used,
                "organization_id": candidate.organization_id,
                "organization_name": candidate.name,
                "organization_inn": candidate.inn,
                "role_mode": candidate.role_mode,
                "search_action": candidate.search_action,
                "status_scope": show,
                "date_window_start": format_dmy(start),
                "date_window_end": format_dmy(end),
                "search_url": url,
            }
        )
        rows.append(row)
    return rows


def report_text(
    *,
    batch_name: str,
    scope_rows: list[entity_resolution.EntityIdentity],
    summary_payload: dict[str, object],
) -> str:
    lines = [
        "# Source sprint: B2B-Center / date-window workaround",
        "",
        f"Дата: {datetime.now().date().isoformat()}",
        "",
        "Источник: `B2B-Center`",
        "",
        f"URL: `{b2b_center.MARKET_URL}`",
        "",
        f"Период: `{DATE_FROM.isoformat()}` - `{DATE_TO.isoformat()}`",
        "",
        "## Scope",
        "",
        f"- юрлиц проверено: `{len(scope_rows)}`",
        f"- batch: `{batch_name}`",
        "- поиск компаний: exact `ИНН`, затем `ОГРН/КПП`, затем точные названия",
        "- обход сломанной пагинации: `show=all/archive` + `date_start_dmy/date_end_dmy` с рекурсивным делением окна по датам",
        "- detail-страница используется для цены/категории/статуса там, где карточка доступна публично",
        "",
        "## Result",
        "",
        f"- accepted candidates: `{summary_payload['accepted_candidates']}`",
        f"- review candidates: `{summary_payload['review_candidates']}`",
        f"- unique rows: `{summary_payload['unique_rows']}`",
        f"- detail fetched: `{summary_payload['detail_fetched']}`",
        f"- priced rows: `{summary_payload['priced_rows']}`",
        f"- existing duplicates: `{summary_payload['existing_duplicates']}`",
        f"- overflow windows: `{summary_payload['overflow_windows']}`",
        f"- raw dir: `{summary_payload['raw_dir']}`",
        f"- out dir: `{summary_payload['out_dir']}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prompt 2 source sprint for B2B-Center exact organization matching and date-windowed scraping."
    )
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inn", action="append", dest="inns", default=[])
    parser.add_argument("--show", default="all", choices=["all", "archive"])
    parser.add_argument("--request-timeout", type=int, default=60)
    parser.add_argument("--max-detail-pages", type=int, default=250)
    parser.add_argument("--throttle-seconds", type=float, default=0.6)
    parser.add_argument("--browser-profile", help="Path to persistent browser profile directory (enables Playwright)")
    parser.add_argument("--resume", action="store_true", help="Resume from previous state by loading existing CSVs and skipping processed entities")
    args = parser.parse_args()

    raw_dir = RAW_DIR / "b2b_center" / args.batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / args.batch_name
    ensure_dir(raw_dir)
    ensure_dir(out_dir)

    scope_rows = read_scope(set(args.inns) or None)
    existing_keys = load_existing_lot_keys()
    
    if args.browser_profile:
        from purchase_analysis.clients.browser_session import BrowserSession
        session = BrowserSession(user_data_dir=args.browser_profile, headless=False, timeout=args.request_timeout)
        session.start()
    else:
        session = b2b_center.create_session(timeout=args.request_timeout)

    candidate_rows: list[dict[str, object]] = []
    item_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    overflow_rows: list[dict[str, object]] = []
    seen_detail_urls: set[str] = set()

    if args.resume:
        try:
            if (out_dir / "candidate_decisions.csv").exists() and (out_dir / "candidate_decisions.csv").stat().st_size > 5:
                candidate_rows = pd.read_csv(out_dir / "candidate_decisions.csv", dtype=str, keep_default_na=False).to_dict("records")
            if (out_dir / "items.csv").exists() and (out_dir / "items.csv").stat().st_size > 5:
                item_rows = pd.read_csv(out_dir / "items.csv", dtype=str, keep_default_na=False).to_dict("records")
            if (out_dir / "summary.csv").exists() and (out_dir / "summary.csv").stat().st_size > 5:
                summary_rows = pd.read_csv(out_dir / "summary.csv", dtype=str, keep_default_na=False).to_dict("records")
            if (out_dir / "overflow_windows.csv").exists() and (out_dir / "overflow_windows.csv").stat().st_size > 5:
                overflow_rows = pd.read_csv(out_dir / "overflow_windows.csv", dtype=str, keep_default_na=False).to_dict("records")
        except Exception as e:
            print(f"Warning: could not load some resume CSVs: {e}")
            
        for r in item_rows:
            if r.get("detail_url"):
                seen_detail_urls.add(str(r["detail_url"]))

    processed_entity_ids = {str(r.get("entity_key")) for r in summary_rows}
    detail_fetched = 0

    for entity in scope_rows:
        if args.resume and entity.entity_id in processed_entity_ids:
            continue
            
        accepted_candidates: dict[tuple[str, str], b2b_center.B2BCenterOrganizationCandidate] = {}
        review_count = 0
        search_queries_tried: list[str] = []
        window_counter = [0]

        for term in ordered_search_terms(entity):
            for search_action in ("SearchOrganizer", "SearchCustomer"):
                role_mode = b2b_center.normalize_role_mode(search_action)
                search_queries_tried.append(f"{role_mode}:{term}")
                try:
                    candidates = b2b_center.search_organization_candidates(
                        term,
                        search_action=search_action,
                        session=session,
                        timeout=args.request_timeout,
                    )
                except Exception as exc:  # pragma: no cover - live transport guard
                    candidate_rows.append(
                        {
                            "entity_key": entity.entity_id,
                            "entity_name": entity.entity_name,
                            "entity_inn": entity.inn,
                            "query_used": term,
                            "search_action": search_action,
                            "role_mode": role_mode,
                            "decision": "reject",
                            "reason": classify_transport_error(exc),
                            "error": repr(exc),
                        }
                    )
                    continue

                for candidate in candidates:
                    decision = entity_resolution.classify_entity_match(
                        entity,
                        candidate_name=candidate.name,
                        candidate_inn=candidate.inn,
                        role=role_mode,
                    )
                    candidate_rows.append(
                        {
                            "entity_key": entity.entity_id,
                            "entity_name": entity.entity_name,
                            "entity_inn": entity.inn,
                            "query_used": term,
                            "query_type": query_type_for_term(term),
                            "search_action": search_action,
                            "role_mode": role_mode,
                            "organization_id": candidate.organization_id,
                            "candidate_name": candidate.name,
                            "candidate_inn": candidate.inn,
                            "decision": decision.decision,
                            "confidence": decision.confidence,
                            "reason": decision.reason,
                            "matched_field": decision.matched_field,
                        }
                    )
                    if decision.accepted:
                        accepted_candidates[(candidate.role_mode, candidate.organization_id)] = candidate
                    elif decision.needs_review:
                        review_count += 1

        entity_unique_rows = 0
        entity_priced_rows = 0
        entity_duplicate_rows = 0
        for candidate in accepted_candidates.values():
            rows = collect_window_items(
                entity=entity,
                candidate=candidate,
                query_used=candidate.query,
                show=args.show,
                start=DATE_FROM,
                end=DATE_TO,
                session=session,
                timeout=args.request_timeout,
                raw_dir=raw_dir,
                window_counter=window_counter,
                overflow_rows=overflow_rows,
                throttle_seconds=args.throttle_seconds,
            )
            for row in rows:
                key = (normalize_spaces(row["source_system"]), normalize_spaces(row["procedure_number"]), "1")
                row["existing_duplicate"] = key in existing_keys
                if row["existing_duplicate"]:
                    entity_duplicate_rows += 1

                detail_url = normalize_spaces(row.get("detail_url"))
                if detail_url and detail_url not in seen_detail_urls and detail_fetched < args.max_detail_pages:
                    try:
                        detail_html, final_detail_url = b2b_center.fetch_procedure_detail(
                            detail_url,
                            session=session,
                            timeout=args.request_timeout,
                        )
                        if b2b_center.is_rate_limited_page(detail_html) or b2b_center.is_forbidden_page(detail_html):
                            if hasattr(session, "pause_for_challenge"):
                                session.pause_for_challenge(reason="Challenge on detail page")
                                resp = session.current_page_content()
                                detail_html = resp.text
                                final_detail_url = resp.url
                                
                        detail_slug = safe_slug(
                            f"{entity.entity_id}_{row['procedure_number']}_{row['role_mode']}"
                        )
                        write_text(raw_dir / f"{detail_slug}_detail.html", detail_html)
                        detail = b2b_center.parse_procedure_detail(
                            detail_html,
                            detail_url=final_detail_url,
                        )
                        row.update(
                            {
                                "detail_subject": detail.subject,
                                "detail_category": detail.category,
                                "detail_quantity_text": detail.quantity_text,
                                "detail_total_price_text": detail.total_price_text,
                                "detail_total_price_rub": detail.total_price_rub,
                                "detail_currency": detail.currency,
                                "detail_published_at": detail.published_at,
                                "detail_deadline_at": detail.deadline_at,
                                "detail_organizer_name": detail.organizer_name,
                                "detail_organizer_profile_url": detail.organizer_profile_url,
                                "detail_procedure_status": detail.procedure_status,
                                "detail_price_note": detail.price_note,
                                "detail_location": detail.location,
                            }
                        )
                        if detail.total_price_rub is not None:
                            row["price_rub"] = detail.total_price_rub
                            row["currency"] = detail.currency or row.get("currency") or ""
                            row["price_source"] = "b2b_center_detail"
                        else:
                            row["price_source"] = ""
                        seen_detail_urls.add(detail_url)
                        detail_fetched += 1
                        if args.throttle_seconds > 0:
                            time.sleep(args.throttle_seconds)
                    except Exception as exc:  # pragma: no cover - live transport guard
                        row["detail_error"] = classify_transport_error(exc)

                item_rows.append(row)
                entity_unique_rows += 1
                if row.get("price_rub") is not None:
                    entity_priced_rows += 1

        summary_rows.append(
            {
                "entity_key": entity.entity_id,
                "entity_name": entity.entity_name,
                "entity_inn": entity.inn,
                "accepted_candidates": len(accepted_candidates),
                "review_candidates": review_count,
                "unique_rows": entity_unique_rows,
                "priced_rows": entity_priced_rows,
                "existing_duplicates": entity_duplicate_rows,
                "search_queries_tried": " | ".join(search_queries_tried),
                "window_requests": window_counter[0],
            }
        )

    write_frame(out_dir / "identity_enrichment_candidates.csv", candidate_rows)
    item_df = source_sprint.write_items_csv(
        out_dir / "items.csv",
        item_rows,
        default_source_system="b2b_center",
    )
    write_frame(out_dir / "summary.csv", summary_rows)
    write_frame(out_dir / "overflow_windows.csv", overflow_rows)

    summary_payload = {
        "accepted_candidates": sum(int(row["accepted_candidates"]) for row in summary_rows),
        "review_candidates": sum(int(row["review_candidates"]) for row in summary_rows),
        "unique_rows": len(item_df),
        "detail_fetched": detail_fetched,
        "priced_rows": sum(1 for row in item_rows if row.get("price_rub") not in (None, "")),
        "existing_duplicates": sum(1 for row in item_rows if row.get("existing_duplicate")),
        "overflow_windows": len(overflow_rows),
        "raw_dir": str(raw_dir),
        "out_dir": str(out_dir),
    }
    (out_dir / "report.md").write_text(
        report_text(
            batch_name=args.batch_name,
            scope_rows=scope_rows,
            summary_payload=summary_payload,
        ),
        encoding="utf-8",
    )
    if hasattr(session, "stop"):
        session.stop()


if __name__ == "__main__":
    main()
