-- Шаблон для быстрого среза по одному юрлицу.
-- Просто поменяй значение в ILIKE на нужную компанию.
select
    entity_name,
    source_system,
    procedure_number,
    lot_number,
    subject,
    focus_category,
    customer_name,
    price_rub,
    published_at,
    items_count,
    documents_count,
    participants_count,
    detail_url
from mart.v_procurement_lots
where entity_name ilike '%СберТех%'
order by published_at desc nulls last, source_system, procedure_number, lot_number
limit 200;
