-- Ценовые и поведенческие аномалии.
select
    anomaly_type,
    entity_name,
    procedure_number,
    lot_number,
    subject,
    focus_category,
    price_rub,
    category_median_price,
    value_ratio_to_category_median,
    anomaly_reason,
    detail_url
from mart.v_anomalies
order by
    anomaly_type,
    value_ratio_to_category_median desc nulls last,
    price_rub desc nulls last
limit 200;
