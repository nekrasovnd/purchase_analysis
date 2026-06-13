-- Годовая сводка: сравниваем объём и количество лотов между 2024 и 2025 годами.
create or replace view mart.v_yearly_summary as
select
    extract(year from published_at)::int as publication_year,
    count(*) as lots_count,
    sum(price_rub) as total_price_rub,
    percentile_cont(0.5) within group (order by price_rub) as median_price_rub,
    count(distinct region) as unique_regions,
    count(distinct source_system) as unique_sources
from core.procurement_lot
where published_at is not null
group by 1
order by 1;

-- Помесячная активность: помогает увидеть сезонность и всплески публикаций.
create or replace view mart.v_monthly_activity as
select
    to_char(date_trunc('month', published_at), 'YYYY-MM') as publication_month,
    focus_category,
    count(*) as lots_count,
    sum(price_rub) as total_price_rub,
    avg(price_rub) as avg_price_rub
from core.procurement_lot
where published_at is not null
group by 1, 2
order by 1, 2;

-- Микс категорий: показывает, какие направления закупок доминируют по стоимости.
create or replace view mart.v_category_mix as
select
    extract(year from published_at)::int as publication_year,
    focus_category,
    count(*) as lots_count,
    sum(price_rub) as total_price_rub,
    sum(price_rub) / nullif(sum(sum(price_rub)) over (partition by extract(year from published_at)), 0)
        as share_of_year_value
from core.procurement_lot
where published_at is not null
group by 1, 2
order by 1, total_price_rub desc;

-- YoY по направлениям: показывает рост/падение категорий между 2024 и 2025 годами.
create or replace view mart.v_category_yoy as
with base as (
    select
        extract(year from published_at)::int as publication_year,
        focus_category,
        count(*) as lots_count,
        sum(price_rub) as total_price_rub
    from core.procurement_lot
    where published_at is not null
    group by 1, 2
),
enriched as (
    select
        publication_year,
        focus_category,
        lots_count,
        total_price_rub,
        lag(lots_count) over (partition by focus_category order by publication_year) as prev_year_lots_count,
        lag(total_price_rub) over (partition by focus_category order by publication_year) as prev_year_total_price_rub
    from base
)
select
    publication_year,
    focus_category,
    lots_count,
    total_price_rub,
    prev_year_lots_count,
    prev_year_total_price_rub,
    lots_count - prev_year_lots_count as lots_count_delta,
    lots_count::numeric / nullif(prev_year_lots_count, 0) as lots_count_growth_ratio,
    total_price_rub - prev_year_total_price_rub as total_price_delta_rub,
    total_price_rub / nullif(prev_year_total_price_rub, 0) as total_price_growth_ratio
from enriched
order by focus_category, publication_year;

-- Поиск аномалий по цене: полезно для первичного контроля завышенных или выбивающихся лотов.
create or replace view mart.v_price_anomalies as
with base as (
    select
        lot_id,
        subject,
        focus_category,
        price_rub,
        percentile_cont(0.5) within group (order by price_rub)
            over (partition by focus_category) as category_median_price
    from core.procurement_lot
    where price_rub is not null
)
select
    lot_id,
    subject,
    focus_category,
    price_rub,
    category_median_price,
    price_rub / nullif(category_median_price, 0) as ratio_to_category_median
from base
where price_rub >= category_median_price * 2
order by price_rub desc;

-- Дубли: сколько строк было схлопнуто при очистке итогового слоя.
create or replace view mart.v_duplicate_stats as
select
    source_system,
    entity_id,
    count(*) filter (where duplicate_group_size > 1) as duplicate_groups,
    sum(greatest(duplicate_group_size - 1, 0)) as duplicate_rows_removed
from core.procurement_lot
group by 1, 2
order by duplicate_rows_removed desc, duplicate_groups desc;

-- База для корреляции: присоединяем месячный объём закупок к среднему USD и ключевой ставке.
create or replace view mart.v_macro_correlation_base as
with lot_month as (
    select
        date_trunc('month', published_at)::date as month_date,
        count(*) as lots_count,
        sum(price_rub) as total_price_rub
    from core.procurement_lot
    where published_at is not null
    group by 1
),
macro_month as (
    select
        date_trunc('month', factor_date)::date as month_date,
        avg(usd_rub) as avg_usd_rub,
        avg(key_rate) as avg_key_rate
    from core.external_factor_daily
    group by 1
)
select
    l.month_date,
    l.lots_count,
    l.total_price_rub,
    m.avg_usd_rub,
    m.avg_key_rate
from lot_month l
left join macro_month m
    on m.month_date = l.month_date
order by l.month_date;
