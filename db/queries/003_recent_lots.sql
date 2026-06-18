-- Последние лоты без размножения по item-строкам.
select
    entity_name,
    source_system,
    procedure_number,
    lot_number,
    subject,
    status,
    price_rub,
    published_at,
    deadline_at,
    detail_url
from mart.v_procurement_lots
order by published_at desc nulls last, source_system, procedure_number, lot_number
limit 200;
