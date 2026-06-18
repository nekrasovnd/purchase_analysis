from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.clients import tektorg
from purchase_analysis.config import RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_json, write_text
from purchase_analysis.utils.text import safe_slug


ROOT_DIR = Path(__file__).resolve().parents[1]
SOURCE_URL = tektorg.SOAP_URL
DEFAULT_BATCH_NAME = "tektorg_prompt2_full_scope_2026-06-15"
EKB_TZ = timezone(timedelta(hours=5))
DATE_FROM = datetime(2024, 1, 1, 0, 0, 0, tzinfo=EKB_TZ)
DATE_TO = datetime(2025, 12, 31, 23, 59, 59, tzinfo=EKB_TZ)

SUMMARY_COLUMNS = [
    "entity_key",
    "entity_name",
    "inn",
    "queries_tried",
    "customer_fault",
    "organizer_fault",
    "customer_total_rows",
    "organizer_total_rows",
    "raw_rows_total",
    "exact_match_rows_total",
    "accepted_rows_in_period",
    "status",
]
ACCEPTED_COLUMNS = [
    "source_system",
    "platform_section",
    "entity_name",
    "customer_query",
    "procedure_number",
    "lot_number",
    "subject",
    "customer_name",
    "customer_inn",
    "region",
    "status",
    "tender_type",
    "price_rub",
    "deadline_at",
    "detail_url",
    "tags",
    "published_at",
    "application_deadline",
    "method_name",
    "currency",
    "organizer_name",
    "organizer_inn",
    "entity_key",
    "query_used",
    "query_field",
    "matched_role",
    "matched_name",
    "matched_inn",
    "matched_field",
    "acceptance_reason",
    "raw_request_file",
    "raw_response_file",
    "page_number",
    "records_total_for_query",
    "duplicate_in_core",
    "core_source_system",
    "decision",
]
REVIEW_COLUMNS = [
    "stage",
    "entity_key",
    "entity_name",
    "query",
    "query_field",
    "procedure_number",
    "lot_number",
    "subject",
    "candidate_role",
    "candidate_name",
    "candidate_inn",
    "decision",
    "reason",
    "confidence",
    "matched_field",
    "published_at",
    "application_deadline",
    "deadline_at",
    "raw_request_file",
    "raw_response_file",
    "page_number",
]
REJECTED_COLUMNS = [
    "stage",
    "entity_key",
    "entity_name",
    "query",
    "query_field",
    "procedure_number",
    "lot_number",
    "subject",
    "candidate_role",
    "candidate_name",
    "candidate_inn",
    "decision",
    "reason",
    "confidence",
    "matched_field",
    "fault_text",
    "published_at",
    "application_deadline",
    "deadline_at",
    "raw_request_file",
    "raw_response_file",
    "page_number",
]
ENRICHMENT_COLUMNS = [
    "entity_key",
    "entity_name",
    "inn",
    "source_system",
    "field_name",
    "proposed_value",
    "evidence",
    "confidence",
    "decision",
    "query_used",
    "query_field",
    "raw_response_file",
]


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    rows = entity_resolution.load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
    if not selected_inns:
        return rows
    return [row for row in rows if row.inn in selected_inns]


def event_date(item: tektorg.TektorgSearchItem) -> tuple[datetime | None, str]:
    for field_name in ("published_at", "application_deadline", "deadline_at"):
        raw_value = getattr(item, field_name, None)
        if not raw_value:
            continue
        try:
            return datetime.fromisoformat(raw_value), field_name
        except ValueError:
            continue
    return None, ""


def reason_from_fault(fault_text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (fault_text or "").casefold()).strip("_")
    return f"soap_fault_{normalized}" if normalized else "soap_fault_unknown"


def probe_fields(entity: entity_resolution.EntityIdentity) -> list[tuple[str, str]]:
    if not entity.inn:
        return []
    return [
        ("customerINN", entity.inn),
        ("organizerINN", entity.inn),
    ]


def build_response_report(
    *,
    summary_payload: dict[str, object],
    summary_df: pd.DataFrame,
    rejected_df: pd.DataFrame,
) -> str:
    lines = [
        "# Source sprint: ТЭК-Торг / full current scope",
        "",
        f"Дата: {datetime.now().date().isoformat()}",
        "",
        "Источник: `ТЭК-Торг`",
        "",
        f"URL: `{SOURCE_URL}`",
        "",
        f"Период: `{DATE_FROM.date().isoformat()}` - `{DATE_TO.date().isoformat()}`",
        "",
        "## Scope",
        "",
        f"- юрлиц: `{summary_payload['scope_entities']}`",
        f"- exact probes: `{summary_payload['checks']}`",
        "- source-specific exact fields: `customerINN`, `organizerINN`",
        "- принятие в core: только через `classify_entity_match(...)` после exact SOAP response",
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
    ]

    for key, value in summary_payload["status_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            f"- accepted new rows: `{summary_payload['accepted_new_rows']}`",
            f"- duplicates: `{summary_payload['duplicates']}`",
            f"- review rows: `{summary_payload['review_count']}`",
            f"- rejected rows: `{int(len(rejected_df))}`",
            f"- enrichment candidates: `{summary_payload['enrichment_candidates']}`",
            f"- exact match entities: `{summary_payload['exact_match_entities']}`",
            f"- errors: `{summary_payload['errors']}`",
        ]
    )

    if not rejected_df.empty:
        lines.extend(["", "## Reject profile", ""])
        for key, value in rejected_df["reason"].fillna("unknown").value_counts().to_dict().items():
            lines.append(f"- `{key}`: `{int(value)}`")

    lines.extend(
        [
            "",
            "## Вывод",
            "",
            "`ТЭК-Торг` подтвержден как `exact_probe_zero / probe_only`, если все exact INN пробы дали только SOAP faults или пустые exact rows.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tektorg Prompt 2 source sprint.")
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inn", action="append", dest="inns")
    parser.add_argument("--max-pages-per-probe", type=int, default=5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    selected_inns = set(args.inns or [])
    out_dir = ROOT_DIR / "output" / "source_sprints" / args.batch_name
    raw_dir = RAW_DIR / "tektorg" / args.batch_name
    ensure_dir(out_dir)
    ensure_dir(raw_dir)

    scope_rows = read_scope(selected_inns or None)
    session = tektorg.create_session(timeout=60)

    raw_files_written: list[str] = []
    summary_rows: list[dict[str, object]] = []
    accepted_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    rejected_rows: list[dict[str, object]] = []
    enrichment_rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    wsdl_text = session.get(tektorg.WSDL_URL, timeout=60).text
    wsdl_path = raw_dir / "procedures.wsdl.xml"
    write_text(wsdl_path, wsdl_text)
    raw_files_written.append(str(wsdl_path))

    exact_match_entities = 0
    probe_checks = 0

    for scope in scope_rows:
        slug = safe_slug(scope.entity_name)
        customer_fault = ""
        organizer_fault = ""
        customer_total_rows = 0
        organizer_total_rows = 0
        raw_rows_total = 0
        exact_match_rows_total = 0
        accepted_rows_in_period = 0
        queries_tried: list[str] = [scope.inn] if scope.inn else []
        accepted_keys: set[tuple[str, str]] = set()

        try:
            for query_field, query_value in probe_fields(scope):
                probe_checks += 1
                role = "customer" if query_field == "customerINN" else "organizer"
                request_xml = tektorg.build_request_xml(
                    customer_inn=query_value if query_field == "customerINN" else None,
                    organizer_inn=query_value if query_field == "organizerINN" else None,
                    start_date=DATE_FROM.isoformat(),
                    end_date=DATE_TO.isoformat(),
                    page=1,
                    limit_page=100,
                )
                request_path = raw_dir / f"{slug}_{query_field}_page_1_request.xml"
                write_text(request_path, request_xml)
                raw_files_written.append(str(request_path))

                response_xml = tektorg.fetch_procedures(
                    request_xml,
                    session=session,
                    timeout=60,
                )
                response_path = raw_dir / f"{slug}_{query_field}_page_1.xml"
                write_text(response_path, response_xml)
                raw_files_written.append(str(response_path))

                response = tektorg.parse_search_response(
                    response_xml,
                    entity_name=scope.entity_name,
                    customer_query=query_value,
                )

                fault_text = response.fault_string
                if query_field == "customerINN":
                    customer_fault = fault_text
                    customer_total_rows += response.total_procedures
                else:
                    organizer_fault = fault_text
                    organizer_total_rows += response.total_procedures

                if fault_text:
                    rejected_rows.append(
                        {
                            "stage": "soap_probe",
                            "entity_key": scope.entity_id,
                            "entity_name": scope.entity_name,
                            "query": query_value,
                            "query_field": query_field,
                            "procedure_number": "",
                            "lot_number": "",
                            "subject": "",
                            "candidate_role": role,
                            "candidate_name": "",
                            "candidate_inn": query_value,
                            "decision": "reject",
                            "reason": reason_from_fault(fault_text),
                            "confidence": "high",
                            "matched_field": "inn",
                            "fault_text": fault_text,
                            "published_at": "",
                            "application_deadline": "",
                            "deadline_at": "",
                            "raw_request_file": str(request_path),
                            "raw_response_file": str(response_path),
                            "page_number": 1,
                        }
                    )
                    continue

                page_items = list(response.items)
                total_pages = min(max(response.total_pages, 1), args.max_pages_per_probe)
                if response.total_pages > 1:
                    for page_number in range(2, total_pages + 1):
                        next_request_xml = tektorg.build_request_xml(
                            customer_inn=query_value if query_field == "customerINN" else None,
                            organizer_inn=query_value if query_field == "organizerINN" else None,
                            start_date=DATE_FROM.isoformat(),
                            end_date=DATE_TO.isoformat(),
                            page=page_number,
                            limit_page=response.limit_per_page or 100,
                        )
                        next_request_path = (
                            raw_dir / f"{slug}_{query_field}_page_{page_number}_request.xml"
                        )
                        write_text(next_request_path, next_request_xml)
                        raw_files_written.append(str(next_request_path))

                        next_response_xml = tektorg.fetch_procedures(
                            next_request_xml,
                            session=session,
                            timeout=60,
                        )
                        next_response_path = raw_dir / f"{slug}_{query_field}_page_{page_number}.xml"
                        write_text(next_response_path, next_response_xml)
                        raw_files_written.append(str(next_response_path))

                        next_response = tektorg.parse_search_response(
                            next_response_xml,
                            entity_name=scope.entity_name,
                            customer_query=query_value,
                        )
                        if next_response.fault_string:
                            rejected_rows.append(
                                {
                                    "stage": "soap_probe",
                                    "entity_key": scope.entity_id,
                                    "entity_name": scope.entity_name,
                                    "query": query_value,
                                    "query_field": query_field,
                                    "procedure_number": "",
                                    "lot_number": "",
                                    "subject": "",
                                    "candidate_role": role,
                                    "candidate_name": "",
                                    "candidate_inn": query_value,
                                    "decision": "reject",
                                    "reason": reason_from_fault(next_response.fault_string),
                                    "confidence": "high",
                                    "matched_field": "inn",
                                    "fault_text": next_response.fault_string,
                                    "published_at": "",
                                    "application_deadline": "",
                                    "deadline_at": "",
                                    "raw_request_file": str(next_request_path),
                                    "raw_response_file": str(next_response_path),
                                    "page_number": page_number,
                                }
                            )
                            break
                        page_items.extend(next_response.items)

                for item in page_items:
                    raw_rows_total += 1
                    if role == "customer":
                        candidate_name = item.customer_name
                        candidate_inns = entity_resolution.split_multi(item.customer_inn) or [query_value]
                    else:
                        candidate_name = item.organizer_name
                        candidate_inns = [item.organizer_inn or query_value]

                    accepted_match = None
                    review_match = None
                    for candidate_inn in candidate_inns:
                        decision = entity_resolution.classify_entity_match(
                            scope,
                            candidate_name=candidate_name,
                            candidate_inn=candidate_inn,
                            role=role,
                        )
                        if decision.accepted:
                            accepted_match = (candidate_inn, decision)
                            break
                        if decision.needs_review and review_match is None:
                            review_match = (candidate_inn, decision)

                    if accepted_match:
                        exact_match_rows_total += 1
                        item_date, date_field = event_date(item)
                        if item_date is None:
                            rejected_rows.append(
                                {
                                    "stage": "search_item",
                                    "entity_key": scope.entity_id,
                                    "entity_name": scope.entity_name,
                                    "query": query_value,
                                    "query_field": query_field,
                                    "procedure_number": item.procedure_number,
                                    "lot_number": item.lot_number,
                                    "subject": item.subject,
                                    "candidate_role": role,
                                    "candidate_name": candidate_name,
                                    "candidate_inn": accepted_match[0],
                                    "decision": "reject",
                                    "reason": "missing_event_date",
                                    "confidence": "high",
                                    "matched_field": accepted_match[1].matched_field,
                                    "fault_text": "",
                                    "published_at": item.published_at or "",
                                    "application_deadline": item.application_deadline or "",
                                    "deadline_at": item.deadline_at or "",
                                    "raw_request_file": str(request_path),
                                    "raw_response_file": str(response_path),
                                    "page_number": 1,
                                }
                            )
                            continue

                        if not (DATE_FROM <= item_date <= DATE_TO):
                            rejected_rows.append(
                                {
                                    "stage": "search_item",
                                    "entity_key": scope.entity_id,
                                    "entity_name": scope.entity_name,
                                    "query": query_value,
                                    "query_field": query_field,
                                    "procedure_number": item.procedure_number,
                                    "lot_number": item.lot_number,
                                    "subject": item.subject,
                                    "candidate_role": role,
                                    "candidate_name": candidate_name,
                                    "candidate_inn": accepted_match[0],
                                    "decision": "reject",
                                    "reason": "out_of_period",
                                    "confidence": "high",
                                    "matched_field": accepted_match[1].matched_field,
                                    "fault_text": "",
                                    "published_at": item.published_at or "",
                                    "application_deadline": item.application_deadline or "",
                                    "deadline_at": item.deadline_at or "",
                                    "raw_request_file": str(request_path),
                                    "raw_response_file": str(response_path),
                                    "page_number": 1,
                                }
                            )
                            continue

                        accepted_key = (item.procedure_number, item.lot_number)
                        if accepted_key in accepted_keys:
                            continue
                        accepted_keys.add(accepted_key)
                        accepted_rows_in_period += 1
                        accepted_rows.append(
                            tektorg.search_item_to_dict(item)
                            | {
                                "entity_key": scope.entity_id,
                                "query_used": query_value,
                                "query_field": query_field,
                                "matched_role": role,
                                "matched_name": candidate_name,
                                "matched_inn": accepted_match[0],
                                "matched_field": accepted_match[1].matched_field,
                                "acceptance_reason": "accepted_by_exact_soap_filter",
                                "raw_request_file": str(request_path),
                                "raw_response_file": str(response_path),
                                "page_number": 1,
                                "records_total_for_query": response.total_procedures,
                                "duplicate_in_core": False,
                                "core_source_system": "",
                                "decision": "",
                            }
                        )
                        enrichment_rows.extend(
                            row
                            | {
                                "query_used": query_value,
                                "query_field": query_field,
                                "raw_response_file": str(response_path),
                            }
                            for row in entity_resolution.propose_identity_enrichment(
                                scope,
                                source_system="tektorg",
                                candidate_name=candidate_name,
                                evidence=(
                                    f"query_field={query_field}; inn={query_value}; "
                                    f"procedure={item.procedure_number}; lot={item.lot_number}; "
                                    f"candidate_name={candidate_name}; candidate_inn={accepted_match[0]}"
                                ),
                            )
                        )
                        continue

                    if review_match:
                        review_rows.append(
                            {
                                "stage": "search_item",
                                "entity_key": scope.entity_id,
                                "entity_name": scope.entity_name,
                                "query": query_value,
                                "query_field": query_field,
                                "procedure_number": item.procedure_number,
                                "lot_number": item.lot_number,
                                "subject": item.subject,
                                "candidate_role": role,
                                "candidate_name": candidate_name,
                                "candidate_inn": review_match[0],
                                "decision": review_match[1].decision,
                                "reason": review_match[1].reason,
                                "confidence": review_match[1].confidence,
                                "matched_field": review_match[1].matched_field,
                                "published_at": item.published_at or "",
                                "application_deadline": item.application_deadline or "",
                                "deadline_at": item.deadline_at or "",
                                "raw_request_file": str(request_path),
                                "raw_response_file": str(response_path),
                                "page_number": 1,
                            }
                        )
                        continue

                    rejected_rows.append(
                        {
                            "stage": "search_item",
                            "entity_key": scope.entity_id,
                            "entity_name": scope.entity_name,
                            "query": query_value,
                            "query_field": query_field,
                            "procedure_number": item.procedure_number,
                            "lot_number": item.lot_number,
                            "subject": item.subject,
                            "candidate_role": role,
                            "candidate_name": candidate_name,
                            "candidate_inn": query_value,
                            "decision": "reject",
                            "reason": "no_exact_identity",
                            "confidence": "high",
                            "matched_field": "",
                            "fault_text": "",
                            "published_at": item.published_at or "",
                            "application_deadline": item.application_deadline or "",
                            "deadline_at": item.deadline_at or "",
                            "raw_request_file": str(request_path),
                            "raw_response_file": str(response_path),
                            "page_number": 1,
                        }
                    )

            if accepted_rows_in_period:
                exact_match_entities += 1

            if accepted_rows_in_period:
                status = "accepted_rows_need_dedup"
            elif exact_match_rows_total:
                status = "exact_rows_out_of_period"
            else:
                status = "exact_probe_zero"

            summary_rows.append(
                {
                    "entity_key": scope.entity_id,
                    "entity_name": scope.entity_name,
                    "inn": scope.inn,
                    "queries_tried": " | ".join(queries_tried),
                    "customer_fault": customer_fault,
                    "organizer_fault": organizer_fault,
                    "customer_total_rows": customer_total_rows,
                    "organizer_total_rows": organizer_total_rows,
                    "raw_rows_total": raw_rows_total,
                    "exact_match_rows_total": exact_match_rows_total,
                    "accepted_rows_in_period": accepted_rows_in_period,
                    "status": status,
                }
            )
        except Exception as exc:  # pragma: no cover - source diagnostics
            errors.append({"entity_name": scope.entity_name, "error": repr(exc)})
            summary_rows.append(
                {
                    "entity_key": scope.entity_id,
                    "entity_name": scope.entity_name,
                    "inn": scope.inn,
                    "queries_tried": " | ".join(queries_tried),
                    "customer_fault": customer_fault,
                    "organizer_fault": organizer_fault,
                    "customer_total_rows": customer_total_rows,
                    "organizer_total_rows": organizer_total_rows,
                    "raw_rows_total": raw_rows_total,
                    "exact_match_rows_total": exact_match_rows_total,
                    "accepted_rows_in_period": accepted_rows_in_period,
                    "status": f"error:{exc.__class__.__name__}",
                }
            )

    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    accepted_df = pd.DataFrame(accepted_rows, columns=ACCEPTED_COLUMNS)
    review_df = pd.DataFrame(review_rows, columns=REVIEW_COLUMNS)
    rejected_df = pd.DataFrame(rejected_rows, columns=REJECTED_COLUMNS)
    enrichment_df = pd.DataFrame(enrichment_rows, columns=ENRICHMENT_COLUMNS)

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
        conclusion = "exact_probe_zero"

    summary_payload = {
        "source_system": "tektorg",
        "batch_name": args.batch_name,
        "scope_entities": len(scope_rows),
        "date_from": DATE_FROM.date().isoformat(),
        "date_to": DATE_TO.date().isoformat(),
        "checks": probe_checks,
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
        "errors": len(errors),
        "raw_files_saved": sorted(set(raw_files_written)),
        "conclusion": conclusion,
        "out_dir": str(out_dir),
        "raw_dir": str(raw_dir),
    }

    report_text = build_response_report(
        summary_payload=summary_payload,
        summary_df=summary_df,
        rejected_df=rejected_df,
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
