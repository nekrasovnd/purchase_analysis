-- Лоты с раскрытой ценой, от самых дорогих к более дешёвым.
select
    entity_name,
    source_system,
    procedure_number,
    lot_number,
    subject,
    focus_category,
    price_rub,
    published_at,
    detail_url
from mart.v_procurement_lots
where price_rub is not null
order by price_rub desc, published_at desc nulls last
limit 200;
