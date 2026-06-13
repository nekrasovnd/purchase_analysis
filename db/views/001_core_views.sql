create or replace view mart.v_entity_coverage as
select
    e.entity_id,
    e.entity_name,
    e.entity_type,
    e.eis_223_open_count,
    e.roseltorg_lot_count,
    e.sberbank_ast_lot_count,
    e.zakazrf_lot_count,
    e.lot_online_lot_count,
    e.lot_online_title_mention_count,
    count(l.lot_id) as loaded_lot_count,
    min(l.published_at) as first_seen_publication_at,
    max(l.published_at) as last_seen_publication_at
from core.entity_scope e
left join core.procurement_lot l
    on l.entity_id = e.entity_id
group by 1, 2, 3, 4, 5, 6, 7, 8, 9;

create or replace view mart.v_procurement_lot_enriched as
select
    l.lot_id,
    e.entity_name,
    l.source_system,
    l.platform_section,
    l.procedure_number,
    l.lot_number,
    l.subject,
    l.customer_name,
    l.region,
    l.status,
    l.tender_type,
    l.price_rub,
    l.currency,
    l.published_at,
    l.deadline_at,
    l.application_deadline,
    l.method_name,
    l.focus_category,
    i.okpd_code,
    i.okpd_name,
    i.quantity,
    i.unit,
    i.unit_price_rub,
    i.line_total_rub,
    i.unit_price_source,
    l.detail_url,
    l.sberb2b_need_id,
    l.sberb2b_condition_id,
    l.duplicate_group_size
from core.procurement_lot l
left join core.entity_scope e
    on e.entity_id = l.entity_id
left join core.procurement_item i
    on i.lot_id = l.lot_id;

create or replace view mart.v_entity_source_links as
select
    entity_name,
    source_system,
    external_customer_key,
    external_customer_name,
    external_inn,
    external_kpp,
    query_used,
    resolution_method,
    records_total,
    candidate_rank
from core.entity_source_link;

create or replace view mart.v_source_assessment as
select
    source_system,
    platform_name,
    platform_url,
    operational_status,
    inclusion_status,
    access_mode,
    rationale,
    coverage_note,
    checked_at
from core.source_assessment;

create or replace view mart.v_integration_probe as
select
    source_system,
    entity_name,
    probe_mode,
    query_used,
    matched_external_id,
    matched_external_name,
    matched_external_inn,
    matched_external_role,
    records_total,
    candidate_rank,
    included_in_core,
    note,
    checked_at
from core.integration_probe;

create or replace view mart.v_procurement_participants as
select
    p.source_system,
    p.procedure_number,
    p.lot_number,
    e.entity_name,
    p.participant_role,
    p.participant_name,
    p.participant_inn,
    p.offer_price_rub,
    p.is_winner,
    p.evidence_source
from core.procurement_participant p
left join core.procurement_lot l
    on l.source_system = p.source_system
    and l.procedure_number = p.procedure_number
    and l.lot_number = p.lot_number
left join core.entity_scope e
    on e.entity_id = l.entity_id;

create or replace view mart.v_document_texts as
select
    l.source_system,
    l.procedure_number,
    l.lot_number,
    d.document_name,
    d.local_path,
    d.extraction_method,
    d.text_chars,
    d.ocr_required,
    d.pii_findings_count,
    d.text_preview
from core.document_text d
left join core.procurement_lot l
    on l.lot_id = d.lot_id;
