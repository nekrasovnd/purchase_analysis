create or replace view mart.v_entity_coverage as
select
    e.entity_id,
    e.entity_key,
    e.group_name,
    e.entity_name,
    e.entity_type,
    e.inn,
    e.ogrn,
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
group by
    e.entity_id,
    e.entity_key,
    e.group_name,
    e.entity_name,
    e.entity_type,
    e.inn,
    e.ogrn,
    e.eis_223_open_count,
    e.roseltorg_lot_count,
    e.sberbank_ast_lot_count,
    e.zakazrf_lot_count,
    e.lot_online_lot_count,
    e.lot_online_title_mention_count;

create or replace view mart.v_procurement_lots as
select
    l.lot_id,
    e.entity_id,
    e.entity_key,
    e.entity_name,
    e.inn as entity_inn,
    l.source_system,
    l.platform_section,
    l.procedure_number,
    l.lot_number,
    l.subject,
    l.customer_name,
    l.customer_inn,
    l.region,
    l.status,
    l.tender_type,
    l.price_rub,
    l.currency,
    l.published_at,
    l.deadline_at,
    l.application_deadline,
    l.method_name,
    l.detail_url,
    l.tags,
    l.delivery_place,
    l.focus_category,
    l.sberb2b_need_id,
    l.sberb2b_condition_id,
    l.sberb2b_status,
    l.sberb2b_state,
    l.sberb2b_public_request_status,
    l.search_url,
    l.duplicate_group_size,
    coalesce(items.items_count, 0) as items_count,
    coalesce(docs.documents_count, 0) as documents_count,
    coalesce(parts.participants_count, 0) as participants_count
from core.procurement_lot l
left join core.entity_scope e
    on e.entity_id = l.entity_id
left join (
    select
        lot_id,
        count(*) as items_count
    from core.procurement_item
    group by lot_id
) items
    on items.lot_id = l.lot_id
left join (
    select
        lot_id,
        count(*) as documents_count
    from core.document_link
    group by lot_id
) docs
    on docs.lot_id = l.lot_id
left join (
    select
        lot_id,
        count(*) as participants_count
    from core.procurement_participant
    group by lot_id
) parts
    on parts.lot_id = l.lot_id;

create or replace view mart.v_procurement_lot_enriched as
select
    l.lot_id,
    e.entity_key,
    e.entity_name,
    e.inn as entity_inn,
    l.source_system,
    l.platform_section,
    l.procedure_number,
    l.lot_number,
    l.subject,
    l.customer_name,
    l.customer_inn,
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
    i.line_no,
    i.item_name,
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
    p.participant_id,
    p.lot_id,
    p.source_system,
    p.procedure_number,
    p.lot_number,
    e.entity_key,
    e.entity_name,
    p.participant_role,
    p.participant_name,
    p.participant_inn,
    p.participant_external_id,
    p.offer_price_rub,
    p.is_winner,
    p.evidence_source
from core.procurement_participant p
left join core.procurement_lot l
    on l.lot_id = p.lot_id
left join core.entity_scope e
    on e.entity_id = l.entity_id;

create or replace view mart.v_document_links as
select
    d.document_id,
    d.lot_id,
    l.source_system,
    l.procedure_number,
    l.lot_number,
    e.entity_key,
    e.entity_name,
    d.document_name,
    d.document_url,
    d.document_storage_name,
    d.document_mime_type,
    d.document_size_bytes,
    d.document_hash,
    d.local_path,
    d.extraction_method,
    d.text_chars,
    d.ocr_required,
    d.pii_findings_count,
    d.is_available,
    d.pii_masked,
    d.discovered_at
from core.document_link d
left join core.procurement_lot l
    on l.lot_id = d.lot_id
left join core.entity_scope e
    on e.entity_id = l.entity_id;

create or replace view mart.v_document_texts as
select
    d.document_text_id,
    d.document_id,
    d.lot_id,
    l.source_system,
    l.procedure_number,
    l.lot_number,
    e.entity_key,
    e.entity_name,
    d.document_name,
    dl.document_url,
    d.local_path,
    d.extraction_method,
    d.text_chars,
    d.ocr_required,
    d.pii_findings_count,
    d.text_preview,
    d.extracted_at
from core.document_text d
left join core.procurement_lot l
    on l.lot_id = d.lot_id
left join core.entity_scope e
    on e.entity_id = l.entity_id
left join core.document_link dl
    on dl.document_id = d.document_id;

create or replace view mart.v_load_audit as
select
    load_audit_id,
    database_name,
    scope_path,
    curated_dir,
    source_sprints_dir,
    include_enrichment,
    entity_scope_rows,
    entity_identity_enrichment_rows,
    entity_source_link_rows,
    source_assessment_rows,
    integration_probe_rows,
    procurement_lot_rows,
    procurement_item_rows,
    document_link_rows,
    document_text_rows,
    procurement_participant_rows,
    external_factor_daily_rows,
    started_at,
    finished_at,
    loaded_at,
    finished_at - started_at as load_duration
from core.load_audit;
