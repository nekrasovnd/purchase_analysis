-- Сводка по заполнению core-таблиц.
select 'core.entity_scope' as table_name, count(*) as row_count from core.entity_scope
union all
select 'core.entity_identity_enrichment', count(*) from core.entity_identity_enrichment
union all
select 'core.entity_source_link', count(*) from core.entity_source_link
union all
select 'core.source_assessment', count(*) from core.source_assessment
union all
select 'core.integration_probe', count(*) from core.integration_probe
union all
select 'core.procurement_lot', count(*) from core.procurement_lot
union all
select 'core.procurement_item', count(*) from core.procurement_item
union all
select 'core.document_link', count(*) from core.document_link
union all
select 'core.document_text', count(*) from core.document_text
union all
select 'core.procurement_participant', count(*) from core.procurement_participant
union all
select 'core.external_factor_daily', count(*) from core.external_factor_daily
union all
select 'core.load_audit', count(*) from core.load_audit
order by table_name;

-- Проверка ссылочной целостности после загрузки.
select 'items_without_lot' as check_name, count(*) as issue_count
from core.procurement_item i
left join core.procurement_lot l on l.lot_id = i.lot_id
where l.lot_id is null
union all
select 'documents_without_lot', count(*)
from core.document_link d
left join core.procurement_lot l on l.lot_id = d.lot_id
where l.lot_id is null
union all
select 'document_texts_without_document', count(*)
from core.document_text dt
left join core.document_link dl on dl.document_id = dt.document_id
where dt.document_id is not null and dl.document_id is null
union all
select 'participants_without_lot', count(*)
from core.procurement_participant p
left join core.procurement_lot l on l.lot_id = p.lot_id
where p.lot_id is not null and l.lot_id is null
order by check_name;

-- Короткий health-cut по источникам.
select
    source_system,
    count(*) as total_lots,
    count(*) filter (where price_rub is not null) as priced_lots,
    round(
        100.0 * count(*) filter (where price_rub is not null) / nullif(count(*), 0),
        2
    ) as priced_lot_share_pct,
    sum(items_count) as total_item_rows,
    sum(documents_count) as total_document_rows,
    sum(participants_count) as total_participant_rows
from mart.v_procurement_lots
group by source_system
order by total_lots desc;
