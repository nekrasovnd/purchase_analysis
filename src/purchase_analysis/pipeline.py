from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd

from purchase_analysis.analysis import (
    build_anomalies_mart,
    build_category_yoy_mart,
    build_category_mix_mart,
    build_document_links_frame,
    build_duplicate_stats_frame,
    build_entity_source_links_frame,
    build_entities_frame,
    build_external_factors_frame,
    build_integration_probe_frame,
    build_llm_prompt_context,
    build_monthly_activity_mart,
    build_monthly_macro_join_mart,
    build_procurement_items_frame,
    build_procurements_frame,
    build_quality_summary,
    build_source_assessment_frame,
    build_yearly_summary_mart,
)
from purchase_analysis.clients import cbr, eis, lot_online, roseltorg, sberbank_ast, zakazrf
from purchase_analysis.config import CURATED_DIR, RAW_DIR, REPORTS_DIR, RunConfig
from purchase_analysis.llm import maybe_write_llm_summary
from purchase_analysis.utils.io import ensure_dir, write_json, write_text
from purchase_analysis.utils.text import safe_slug


@dataclass(slots=True)
class ScopeEntity:
    group_name: str
    entity_name: str
    entity_type: str
    inn: str
    eis_search_term: str
    roseltorg_customer_query: str
    is_priority_focus: bool


def _read_scope(path: Path) -> list[ScopeEntity]:
    rows: list[ScopeEntity] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rows.append(
                ScopeEntity(
                    group_name=row["group_name"],
                    entity_name=row["entity_name"],
                    entity_type=row["entity_type"],
                    inn=row["inn"],
                    eis_search_term=row["eis_search_term"],
                    roseltorg_customer_query=row["roseltorg_customer_query"],
                    is_priority_focus=row["is_priority_focus"] == "1",
                )
            )
    return rows


def _candidate_queries(scope: ScopeEntity, resolved_inn: str | None) -> list[str]:
    values = [
        normalize
        for normalize in [
            resolved_inn or "",
            scope.inn,
            scope.eis_search_term,
            scope.entity_name,
            scope.roseltorg_customer_query,
        ]
        if normalize
    ]
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _source_assessment_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_system": "eis",
            "platform_name": "ЕИС",
            "platform_url": "https://zakupki.gov.ru",
            "operational_status": "operational",
            "inclusion_status": "used_in_pipeline",
            "access_mode": "public_html",
            "rationale": "Official source for entity resolution and 223-FZ coverage control.",
            "coverage_note": "Used as authoritative customer registry and count-control layer.",
        },
        {
            "source_system": "roseltorg",
            "platform_name": "Росэлторг",
            "platform_url": "https://www.roseltorg.ru",
            "operational_status": "operational",
            "inclusion_status": "used_in_pipeline",
            "access_mode": "public_html",
            "rationale": "Public search and detail cards expose lot-level metadata and document links.",
            "coverage_note": "Used for directly observed lot cards and enrichment.",
        },
        {
            "source_system": "sberbank_ast",
            "platform_name": "Сбербанк-АСТ",
            "platform_url": "https://utp.sberbank-ast.ru/Main/List/UnitedPurchaseListNew",
            "operational_status": "operational",
            "inclusion_status": "used_in_pipeline",
            "access_mode": "public_html_plus_public_json",
            "rationale": "Public long dictionary and search endpoint support reproducible customer resolution and paging.",
            "coverage_note": "Used for large 2024-2025 procurement samples on SberB2B / AST public registry.",
        },
        {
            "source_system": "zakazrf",
            "platform_name": "ЗаказРФ",
            "platform_url": "https://etp.zakazrf.ru/NotificationEx",
            "operational_status": "operational",
            "inclusion_status": "used_in_pipeline_probe_only",
            "access_mode": "public_html_plus_hidden_form_post",
            "rationale": "Public customer selector and exact NotificationEx filtering were reproduced with pure HTTP.",
            "coverage_note": (
                "Operational exact-probe adapter implemented; Sber-scope customer matches currently return zero "
                "public notifications, so no ZakazRF rows enter the core lot mart in this run."
            ),
        },
        {
            "source_system": "lot_online",
            "platform_name": "ЛотОнлайн",
            "platform_url": "https://tender.lot-online.ru/etp/app/SearchLots/",
            "operational_status": "operational",
            "inclusion_status": "used_in_pipeline_probe_only",
            "access_mode": "public_hidden_json_endpoint",
            "rationale": "Frontend searchServlet endpoint was reverse-engineered; exact customer/organizer filters are reproducible.",
            "coverage_note": (
                "Operational exact-probe adapter implemented; exact INN filters return zero Sber-scope hits, while "
                "broad title search is retained only in probe artifacts because precision is too weak for the core mart."
            ),
        },
        {
            "source_system": "tektorg",
            "platform_name": "ТЭК-Торг",
            "platform_url": "https://www.tektorg.ru/procedures",
            "operational_status": "research_only",
            "inclusion_status": "researched_not_used",
            "access_mode": "public_html",
            "rationale": "Search endpoint is public, but exact legal-entity precision is too weak for reliable group collection.",
            "coverage_note": "Useful as scout source, not yet robust enough as primary ingest.",
        },
        {
            "source_system": "rts_tender",
            "platform_name": "РТС-Тендер",
            "platform_url": "https://www.rts-tender.ru",
            "operational_status": "blocked",
            "inclusion_status": "researched_not_used",
            "access_mode": "anti_ddos_block",
            "rationale": "Public homepage returns Anti-DDoS protection page from the execution environment.",
            "coverage_note": "External blocker; reproducible adapter was not feasible in this environment.",
        },
        {
            "source_system": "etpgpb",
            "platform_name": "ЭТП ГПБ",
            "platform_url": "https://etpgpb.ru/procedures/",
            "operational_status": "research_only",
            "inclusion_status": "researched_not_used",
            "access_mode": "public_html_with_client_hydration",
            "rationale": "Public procedures page is accessible, but plain HTTP queries do not reproduce filtered result sets.",
            "coverage_note": "Needs browser-side request discovery before safe adapter implementation.",
        },
    ]


class PipelineRunner:
    def __init__(self, config: RunConfig | None = None) -> None:
        self.config = config or RunConfig()
        self.eis_session = eis.create_session(timeout=self.config.request_timeout)
        self.roseltorg_session = roseltorg.create_session(timeout=self.config.request_timeout)
        self.sberbank_ast_session = sberbank_ast.create_session(timeout=self.config.request_timeout)
        self.zakazrf_session = zakazrf.create_session(timeout=self.config.request_timeout)
        self.lot_online_session = lot_online.create_session(timeout=self.config.request_timeout)
        self.cbr_session = cbr.create_session(timeout=self.config.request_timeout)

    def _write_csv(self, name: str, df: pd.DataFrame) -> None:
        ensure_dir(CURATED_DIR)
        df.to_csv(CURATED_DIR / name, index=False, encoding="utf-8-sig")

    def _write_payload(self, path: Path, payload: dict) -> None:
        write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))

    def run_all(self) -> dict[str, Any]:
        ensure_dir(RAW_DIR / "eis")
        ensure_dir(RAW_DIR / "roseltorg" / "search")
        ensure_dir(RAW_DIR / "roseltorg" / "detail")
        ensure_dir(RAW_DIR / "sberbank_ast" / "search")
        ensure_dir(RAW_DIR / "zakazrf")
        ensure_dir(RAW_DIR / "lot_online")
        ensure_dir(RAW_DIR / "cbr")
        ensure_dir(CURATED_DIR)
        ensure_dir(REPORTS_DIR)

        scope_entities = _read_scope(self.config.entity_scope_path)
        source_assessment_rows = _source_assessment_rows()
        registry_html = sberbank_ast.fetch_registry_page(
            session=self.sberbank_ast_session,
            timeout=self.config.request_timeout,
        )
        write_text(RAW_DIR / "sberbank_ast" / "registry.html", registry_html)
        zakazrf_registry_html = zakazrf.fetch_registry_page(
            session=self.zakazrf_session,
            timeout=self.config.request_timeout,
        )
        write_text(RAW_DIR / "zakazrf" / "registry.html", zakazrf_registry_html)
        zakazrf_main_page_id = zakazrf.parse_main_page_id(zakazrf_registry_html)

        entity_records: list[dict[str, Any]] = []
        entity_source_link_rows: list[dict[str, Any]] = []
        integration_probe_rows: list[dict[str, Any]] = []
        search_rows: list[dict[str, Any]] = []
        detail_rows: list[dict[str, Any]] = []
        document_rows: list[dict[str, Any]] = []

        for scope in scope_entities:
            slug = safe_slug(scope.entity_name)

            chooser_html = eis.fetch_choose_organization_table(
                scope.eis_search_term,
                session=self.eis_session,
                timeout=self.config.request_timeout,
            )
            write_text(RAW_DIR / "eis" / f"{slug}_chooser.html", chooser_html)

            candidates = eis.parse_choose_organization_table(chooser_html, scope.eis_search_term)
            best_candidate = eis.select_best_candidate(
                candidates,
                expected_name=scope.entity_name,
                inn=scope.inn,
            )

            eis_count = 0
            eis_url = ""
            best_payload: dict[str, Any] = {}
            if best_candidate:
                eis_count, results_html, eis_url = eis.count_procurements_223(
                    best_candidate,
                    date_from=self.config.date_from,
                    date_to=self.config.date_to,
                    session=self.eis_session,
                    timeout=self.config.request_timeout,
                )
                write_text(RAW_DIR / "eis" / f"{slug}_results.html", results_html)
                best_payload = asdict(best_candidate)
                entity_source_link_rows.append(
                    {
                        "entity_name": scope.entity_name,
                        "source_system": "eis",
                        "external_customer_key": best_candidate.code,
                        "external_customer_name": best_candidate.name,
                        "external_inn": best_candidate.inn,
                        "external_kpp": best_candidate.kpp,
                        "query_used": scope.eis_search_term,
                        "resolution_method": "eis_choose_organization",
                        "records_total": eis_count,
                        "candidate_rank": 1,
                    }
                )

            lot_count = 0
            for page in range(1, self.config.max_pages + 1):
                search_html, search_url = roseltorg.fetch_search_page(
                    customer_query=scope.roseltorg_customer_query,
                    date_from=self.config.date_from,
                    date_to=self.config.date_to,
                    page=page,
                    session=self.roseltorg_session,
                    timeout=self.config.request_timeout,
                )
                write_text(RAW_DIR / "roseltorg" / "search" / f"{slug}_page_{page}.html", search_html)
                page_items = roseltorg.parse_search_items(
                    search_html,
                    entity_name=scope.entity_name,
                    customer_query=scope.roseltorg_customer_query,
                )
                if not page_items:
                    break
                lot_count += len(page_items)
                for item in page_items:
                    item_payload = roseltorg.search_item_to_dict(item)
                    item_payload["search_url"] = search_url
                    search_rows.append(item_payload)

                    detail_html = roseltorg.fetch_lot_detail(
                        item.detail_url,
                        session=self.roseltorg_session,
                        timeout=self.config.request_timeout,
                    )
                    detail_slug = f"{item.procedure_number}_{item.lot_number}"
                    write_text(RAW_DIR / "roseltorg" / "detail" / f"{detail_slug}.html", detail_html)
                    detail, documents = roseltorg.parse_lot_detail(
                        detail_html,
                        procedure_number=item.procedure_number,
                        lot_number=item.lot_number,
                    )
                    detail_rows.append(roseltorg.detail_to_dict(detail))
                    document_rows.extend(documents)

            resolved_inn = best_payload.get("inn") or scope.inn
            ast_candidates = sberbank_ast.select_best_candidates(
                sberbank_ast.search_customer_candidates(
                    queries=_candidate_queries(scope, resolved_inn),
                    session=self.sberbank_ast_session,
                    timeout=self.config.request_timeout,
                ),
                expected_name=scope.entity_name,
                inn=resolved_inn,
            )
            ast_lot_count = 0
            for candidate_rank, candidate in enumerate(ast_candidates, start=1):
                customer_slug = safe_slug(f"{candidate.bu_inn}_{candidate.bu_kpp}")
                first_page_total = 0
                for page_index in range(self.config.max_pages):
                    offset = page_index * 20
                    search_response = sberbank_ast.fetch_search_results(
                        registry_html=registry_html,
                        customer=candidate,
                        date_from=self.config.date_from,
                        date_to=self.config.date_to,
                        offset=offset,
                        page_size=20,
                        session=self.sberbank_ast_session,
                        timeout=self.config.request_timeout,
                    )
                    if page_index == 0:
                        first_page_total = search_response.total
                        entity_source_link_rows.append(
                            {
                                "entity_name": scope.entity_name,
                                "source_system": "sberbank_ast",
                                "external_customer_key": candidate.bu_inn_kpp,
                                "external_customer_name": candidate.full_name,
                                "external_inn": candidate.bu_inn,
                                "external_kpp": candidate.bu_kpp,
                                "query_used": candidate.query,
                                "resolution_method": "ast_long_dictionary",
                                "records_total": first_page_total,
                                "candidate_rank": candidate_rank,
                            }
                        )
                    write_text(
                        RAW_DIR / "sberbank_ast" / "search" / f"{slug}_{customer_slug}_page_{page_index + 1}.xml",
                        search_response.table_xml,
                    )
                    write_text(
                        RAW_DIR / "sberbank_ast" / "search" / f"{slug}_{customer_slug}_page_{page_index + 1}_request.xml",
                        search_response.request_xml,
                    )
                    raw_page_items = sberbank_ast.parse_search_items(
                        search_response.table_xml,
                        entity_name=scope.entity_name,
                        customer_query=candidate.full_name,
                    )
                    if not raw_page_items:
                        break
                    page_items = [
                        item for item in raw_page_items if sberbank_ast.is_procurement_relevant(item)
                    ]
                    ast_lot_count += len(page_items)
                    for item in page_items:
                        item_payload = sberbank_ast.search_item_to_dict(item)
                        item_payload["search_url"] = search_response.search_url
                        search_rows.append(item_payload)
                    if offset + len(raw_page_items) >= search_response.total:
                        break

            zakazrf_candidates: list[zakazrf.ZakazRfCustomerCandidate] = []
            zakazrf_lot_count = 0
            try:
                zakazrf_dialog_html, zakazrf_dialog_url = zakazrf.fetch_customer_dialog(
                    zakazrf_main_page_id,
                    dialog_id=f"dialog_{slug}",
                    session=self.zakazrf_session,
                    timeout=self.config.request_timeout,
                )
                write_text(RAW_DIR / "zakazrf" / f"{slug}_customer_dialog.html", zakazrf_dialog_html)
                zakazrf_context = zakazrf.parse_customer_dialog_context(
                    zakazrf_dialog_html,
                    main_page_id=zakazrf_main_page_id,
                    dialog_url=zakazrf_dialog_url,
                )
                customer_search_html, _ = zakazrf.search_customer_candidates(
                    zakazrf_context,
                    inn=resolved_inn,
                    full_name="",
                    dialog_id=f"dialog_{slug}",
                    session=self.zakazrf_session,
                    timeout=self.config.request_timeout,
                )
                write_text(RAW_DIR / "zakazrf" / f"{slug}_customer_search.html", customer_search_html)
                zakazrf_candidates = zakazrf.parse_customer_candidates(customer_search_html)
                if not zakazrf_candidates:
                    integration_probe_rows.append(
                        {
                            "source_system": "zakazrf",
                            "entity_name": scope.entity_name,
                            "probe_mode": "customer_lookup",
                            "query_used": resolved_inn,
                            "matched_external_id": "",
                            "matched_external_name": "",
                            "matched_external_inn": resolved_inn,
                            "matched_external_role": "",
                            "records_total": 0,
                            "candidate_rank": 0,
                            "included_in_core": False,
                            "note": "No exact customer registry match by INN in the public selector dialog.",
                        }
                    )
                for candidate_rank, candidate in enumerate(zakazrf_candidates, start=1):
                    notifications_html, notifications_url = zakazrf.fetch_notifications(
                        candidate.internal_id,
                        session=self.zakazrf_session,
                        timeout=self.config.request_timeout,
                    )
                    write_text(
                        RAW_DIR / "zakazrf" / f"{slug}_customer_{candidate.internal_id}_notifications.html",
                        notifications_html,
                    )
                    total_rows = zakazrf.parse_total_rows(notifications_html)
                    exact_items = zakazrf.parse_notification_rows(
                        notifications_html,
                        entity_name=scope.entity_name,
                        customer_query=candidate.full_name,
                    )
                    zakazrf_lot_count += len(exact_items)
                    for item in exact_items:
                        item_payload = zakazrf.search_item_to_dict(item)
                        item_payload["search_url"] = notifications_url
                        search_rows.append(item_payload)
                    entity_source_link_rows.append(
                        {
                            "entity_name": scope.entity_name,
                            "source_system": "zakazrf",
                            "external_customer_key": candidate.internal_id,
                            "external_customer_name": candidate.full_name,
                            "external_inn": candidate.inn,
                            "external_kpp": "",
                            "query_used": resolved_inn,
                            "resolution_method": "zakazrf_customer_dialog",
                            "records_total": total_rows,
                            "candidate_rank": candidate_rank,
                        }
                    )
                    integration_probe_rows.append(
                        {
                            "source_system": "zakazrf",
                            "entity_name": scope.entity_name,
                            "probe_mode": "customer_exact_notifications",
                            "query_used": resolved_inn,
                            "matched_external_id": candidate.internal_id,
                            "matched_external_name": candidate.full_name,
                            "matched_external_inn": candidate.inn,
                            "matched_external_role": candidate.role_name,
                            "records_total": total_rows,
                            "candidate_rank": candidate_rank,
                            "included_in_core": bool(exact_items),
                            "note": (
                                "Exact customer resolved and included into the core mart."
                                if exact_items
                                else "Exact customer resolved, but NotificationEx returned zero public records."
                            ),
                        }
                    )
            except Exception as error:
                integration_probe_rows.append(
                    {
                        "source_system": "zakazrf",
                        "entity_name": scope.entity_name,
                        "probe_mode": "customer_lookup_error",
                        "query_used": resolved_inn,
                        "matched_external_id": "",
                        "matched_external_name": "",
                        "matched_external_inn": resolved_inn,
                        "matched_external_role": "",
                        "records_total": 0,
                        "candidate_rank": 0,
                        "included_in_core": False,
                        "note": f"ZakazRF probe failed: {error}",
                    }
                )

            lot_online_lot_count = 0
            lot_online_title_mention_count = 0
            try:
                exact_queries = [
                    ("customer_exact", lot_online.build_query_payload(customer_title=resolved_inn)),
                    ("organizer_exact", lot_online.build_query_payload(organizer_title=resolved_inn)),
                ]
                for probe_mode, query in exact_queries:
                    pages = lot_online.fetch_all_search_pages(
                        query,
                        max_pages=self.config.max_pages,
                        session=self.lot_online_session,
                        timeout=self.config.request_timeout,
                    )
                    exact_items: list[dict[str, Any]] = []
                    for page_index, (payload, search_url) in enumerate(pages, start=1):
                        self._write_payload(
                            RAW_DIR / "lot_online" / f"{slug}_{probe_mode}_page_{page_index}.json",
                            payload,
                        )
                        page_items = lot_online.parse_search_items(
                            payload,
                            entity_name=scope.entity_name,
                            customer_query=resolved_inn,
                        )
                        for item in page_items:
                            item_payload = lot_online.search_item_to_dict(item)
                            item_payload["search_url"] = search_url
                            exact_items.append(item_payload)
                    lot_online_lot_count += len(exact_items)
                    search_rows.extend(exact_items)
                    integration_probe_rows.append(
                        {
                            "source_system": "lot_online",
                            "entity_name": scope.entity_name,
                            "probe_mode": probe_mode,
                            "query_used": resolved_inn,
                            "matched_external_id": resolved_inn,
                            "matched_external_name": "",
                            "matched_external_inn": resolved_inn,
                            "matched_external_role": probe_mode.replace("_exact", ""),
                            "records_total": len(exact_items),
                            "candidate_rank": 1,
                            "included_in_core": bool(exact_items),
                            "note": (
                                "Exact INN filter produced rows and they were included into the core mart."
                                if exact_items
                                else "Exact INN filter reproduced successfully, but returned zero public rows."
                            ),
                        }
                    )

                title_payload, _ = lot_online.fetch_search_page(
                    lot_online.build_query_payload(title=scope.eis_search_term),
                    session=self.lot_online_session,
                    timeout=self.config.request_timeout,
                )
                self._write_payload(RAW_DIR / "lot_online" / f"{slug}_title_mentions_page_1.json", title_payload)
                lot_online_title_mention_count = lot_online.parse_total(title_payload)
                integration_probe_rows.append(
                    {
                        "source_system": "lot_online",
                        "entity_name": scope.entity_name,
                        "probe_mode": "title_mentions",
                        "query_used": scope.eis_search_term,
                        "matched_external_id": "",
                        "matched_external_name": "",
                        "matched_external_inn": resolved_inn,
                        "matched_external_role": "",
                        "records_total": lot_online_title_mention_count,
                        "candidate_rank": 1,
                        "included_in_core": False,
                        "note": (
                            "Title search is intentionally excluded from the core mart because it captures many "
                            "contextual mentions and false positives."
                        ),
                    }
                )
            except Exception as error:
                integration_probe_rows.append(
                    {
                        "source_system": "lot_online",
                        "entity_name": scope.entity_name,
                        "probe_mode": "search_error",
                        "query_used": resolved_inn,
                        "matched_external_id": "",
                        "matched_external_name": "",
                        "matched_external_inn": resolved_inn,
                        "matched_external_role": "",
                        "records_total": 0,
                        "candidate_rank": 0,
                        "included_in_core": False,
                        "note": f"Lot-Online probe failed: {error}",
                    }
                )

            entity_records.append(
                {
                    "group_name": scope.group_name,
                    "entity_name": scope.entity_name,
                    "entity_type": scope.entity_type,
                    "inn": scope.inn,
                    "is_priority_focus": scope.is_priority_focus,
                    "eis_search_term": scope.eis_search_term,
                    "roseltorg_customer_query": scope.roseltorg_customer_query,
                    "candidate_count": len(candidates),
                    "resolved_inn": best_payload.get("inn", scope.inn),
                    "eis_entity_code": best_payload.get("code", ""),
                    "eis_entity_name": best_payload.get("name", ""),
                    "eis_resolved_inn": best_payload.get("inn", ""),
                    "eis_resolved_kpp": best_payload.get("kpp", ""),
                    "eis_resolved_ogrn": best_payload.get("ogrn", ""),
                    "eis_fz94id": best_payload.get("fz94id", ""),
                    "eis_fz223id": best_payload.get("fz223id", ""),
                    "eis_223_open_count": eis_count,
                    "eis_results_url": eis_url,
                    "roseltorg_lot_count": lot_count,
                    "sberbank_ast_candidate_count": len(ast_candidates),
                    "sberbank_ast_lot_count": ast_lot_count,
                    "zakazrf_candidate_count": len(zakazrf_candidates),
                    "zakazrf_lot_count": zakazrf_lot_count,
                    "lot_online_lot_count": lot_online_lot_count,
                    "lot_online_title_mention_count": lot_online_title_mention_count,
                }
            )

        usd_rows = cbr.fetch_usd_rates(
            self.config.date_from,
            self.config.date_to,
            session=self.cbr_session,
            timeout=self.config.request_timeout,
        )
        key_rate_rows = cbr.fetch_key_rate(
            self.config.date_from,
            self.config.date_to,
            session=self.cbr_session,
            timeout=self.config.request_timeout,
        )

        entities_df = build_entities_frame(entity_records)
        entity_source_links_df = build_entity_source_links_frame(entity_source_link_rows)
        integration_probe_df = build_integration_probe_frame(integration_probe_rows)
        source_assessment_df = build_source_assessment_frame(source_assessment_rows)
        lots_df = build_procurements_frame(search_rows, detail_rows)
        items_df = build_procurement_items_frame(lots_df)
        document_links_df = build_document_links_frame(document_rows)
        duplicate_stats_df = build_duplicate_stats_frame(lots_df)
        external_factors_df = build_external_factors_frame(usd_rows, key_rate_rows)
        monthly_activity_df = build_monthly_activity_mart(lots_df)
        yearly_summary_df = build_yearly_summary_mart(lots_df)
        category_mix_df = build_category_mix_mart(lots_df)
        category_yoy_df = build_category_yoy_mart(lots_df)
        anomalies_df = build_anomalies_mart(lots_df)
        monthly_macro_df = build_monthly_macro_join_mart(lots_df, external_factors_df)

        self._write_csv("entity_coverage.csv", entities_df)
        self._write_csv("entity_source_links.csv", entity_source_links_df)
        self._write_csv("etp_integration_probe.csv", integration_probe_df)
        self._write_csv("source_assessment.csv", source_assessment_df)
        self._write_csv("procurement_lots.csv", lots_df)
        self._write_csv("procurement_items.csv", items_df)
        self._write_csv("document_links.csv", document_links_df)
        self._write_csv("duplicate_stats.csv", duplicate_stats_df)
        self._write_csv("external_factors_daily.csv", external_factors_df)
        self._write_csv("mart_monthly_activity.csv", monthly_activity_df)
        self._write_csv("mart_yearly_summary.csv", yearly_summary_df)
        self._write_csv("mart_category_mix.csv", category_mix_df)
        self._write_csv("mart_category_yoy.csv", category_yoy_df)
        self._write_csv("mart_anomalies.csv", anomalies_df)
        self._write_csv("mart_monthly_macro_join.csv", monthly_macro_df)

        usd_path = RAW_DIR / "cbr" / "usd_rates.csv"
        key_rate_path = RAW_DIR / "cbr" / "key_rate.csv"
        pd.DataFrame(usd_rows).to_csv(usd_path, index=False, encoding="utf-8-sig")
        pd.DataFrame(key_rate_rows).to_csv(key_rate_path, index=False, encoding="utf-8-sig")

        quality = build_quality_summary(
            entities_df=entities_df,
            lots_df=lots_df,
            items_df=items_df,
            document_links_df=document_links_df,
            external_factors_df=external_factors_df,
        )
        write_json(REPORTS_DIR / "quality_summary.json", quality)
        llm_prompt_pack = build_llm_prompt_context(
            quality=quality,
            source_assessment_df=source_assessment_df,
            yearly_summary_df=yearly_summary_df,
            category_yoy_df=category_yoy_df,
            anomalies_df=anomalies_df,
        )
        write_text(
            REPORTS_DIR / "llm_prompt_pack.md",
            llm_prompt_pack,
            utf8_bom=True,
        )
        maybe_write_llm_summary(llm_prompt_pack, REPORTS_DIR / "llm_summary.md")

        return quality
