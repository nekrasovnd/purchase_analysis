-- Последние лоты без дублирования по item-строкам.
select
    entity_name,
    source_system,
    procedure_number,
    lot_number,
    subject,
    price_rub,
    published_at,
    detail_url
from mart.v_procurement_lots
order by published_at desc nulls last, source_system, procedure_number, lot_number
limit 100;

-- Крупнейшие лоты с раскрытой ценой.
select
    entity_name,
    source_system,
    procedure_number,
    lot_number,
    subject,
    price_rub,
    focus_category,
    published_at,
    detail_url
from mart.v_procurement_lots
where price_rub is not null
order by price_rub desc
limit 100;

-- Быстрый срез по юрлицам и покрытию.
select
    entity_name,
    loaded_lot_count,
    sberbank_ast_lot_count,
    roseltorg_lot_count,
    zakazrf_lot_count,
    lot_online_lot_count,
    first_seen_publication_at,
    last_seen_publication_at
from mart.v_entity_coverage
order by loaded_lot_count desc, entity_name;

-- Последние загрузки curated snapshot в PostgreSQL.
select
    load_audit_id,
    database_name,
    procurement_lot_rows,
    procurement_item_rows,
    document_link_rows,
    document_text_rows,
    procurement_participant_rows,
    external_factor_daily_rows,
    load_duration,
    loaded_at
from mart.v_load_audit
order by load_audit_id desc
limit 20;
