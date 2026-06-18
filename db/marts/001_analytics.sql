create or replace view mart.v_yearly_summary as
select
    extract(year from published_at)::int as publication_year,
    count(*) as lots_count,
    sum(price_rub) as total_price_rub,
    percentile_cont(0.5) within group (order by price_rub) as median_price_rub,
    count(distinct region) as unique_regions,
    count(distinct focus_category) as unique_categories,
    count(distinct source_system) as unique_sources
from core.procurement_lot
where published_at is not null
group by 1
order by 1;

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

create or replace view mart.v_category_mix as
with base as (
    select
        extract(year from published_at)::int as publication_year,
        focus_category,
        count(*) as lots_count,
        sum(price_rub) as total_price_rub
    from core.procurement_lot
    where published_at is not null
    group by 1, 2
)
select
    publication_year,
    focus_category,
    lots_count,
    total_price_rub,
    total_price_rub / nullif(sum(total_price_rub) over (partition by publication_year), 0) as share_of_year_value
from base
order by publication_year, total_price_rub desc nulls last;

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

create or replace view mart.v_duplicate_stats as
select
    l.source_system,
    e.entity_name,
    count(*) filter (where l.duplicate_group_size > 1) as duplicate_groups,
    sum(greatest(l.duplicate_group_size - 1, 0)) as duplicate_rows_removed
from core.procurement_lot l
left join core.entity_scope e
    on e.entity_id = l.entity_id
where l.duplicate_group_size > 1
group by l.source_system, e.entity_name
order by duplicate_rows_removed desc, duplicate_groups desc;

create or replace view mart.v_unit_price_benchmarks as
with base as (
    select
        l.source_system,
        e.entity_name,
        l.procedure_number,
        l.lot_number,
        i.line_no,
        i.item_name,
        i.okpd_code,
        i.okpd_name,
        i.quantity,
        i.unit,
        i.unit_price_rub,
        i.line_total_rub,
        concat(
            left(coalesce(i.okpd_code, ''), 8),
            '|',
            lower(coalesce(i.unit, '')),
            '|',
            left(
                trim(
                    regexp_replace(
                        translate(lower(coalesce(i.item_name, '')), 'ё', 'е'),
                        '[^0-9a-zа-я]+',
                        ' ',
                        'g'
                    )
                ),
                120
            )
        ) as benchmark_key
    from core.procurement_item i
    join core.procurement_lot l
        on l.lot_id = i.lot_id
    left join core.entity_scope e
        on e.entity_id = l.entity_id
    where i.unit_price_rub is not null
        and i.unit_price_rub > 0
),
stats as (
    select
        benchmark_key,
        count(*) as observations,
        percentile_cont(0.5) within group (order by unit_price_rub) as median_unit_price_rub,
        percentile_cont(0.75) within group (order by unit_price_rub) as p75_unit_price_rub
    from base
    group by 1
)
select
    b.source_system,
    b.entity_name,
    b.procedure_number,
    b.lot_number,
    b.line_no,
    b.item_name,
    b.okpd_code,
    b.okpd_name,
    b.quantity,
    b.unit,
    b.unit_price_rub,
    b.line_total_rub,
    b.benchmark_key,
    s.observations,
    s.median_unit_price_rub,
    s.p75_unit_price_rub,
    b.unit_price_rub / nullif(s.median_unit_price_rub, 0) as ratio_to_median_unit_price,
    s.observations >= 2
        and b.unit_price_rub / nullif(s.median_unit_price_rub, 0) >= 1.8 as unit_price_anomaly_flag
from base b
join stats s
    on s.benchmark_key = b.benchmark_key
order by unit_price_anomaly_flag desc, ratio_to_median_unit_price desc nulls last, unit_price_rub desc;

create or replace view mart.v_monthly_macro_join as
with lot_month as (
    select
        to_char(date_trunc('month', published_at), 'YYYY-MM') as publication_month,
        count(*) as lots_count,
        sum(price_rub) as total_price_rub,
        avg(price_rub) as avg_price_rub
    from core.procurement_lot
    where published_at is not null
    group by 1
),
macro_month as (
    select
        to_char(date_trunc('month', factor_date), 'YYYY-MM') as publication_month,
        avg(usd_rub) as avg_usd_rub,
        avg(key_rate) as avg_key_rate,
        avg(inflation_yoy_pct) as inflation_yoy_pct,
        avg(inflation_target_pct) as inflation_target_pct
    from core.external_factor_daily
    group by 1
),
joined as (
    select
        l.publication_month,
        l.lots_count,
        l.total_price_rub,
        l.avg_price_rub,
        m.avg_usd_rub,
        m.avg_key_rate,
        m.inflation_yoy_pct,
        m.inflation_target_pct
    from lot_month l
    left join macro_month m
        on m.publication_month = l.publication_month
),
correlations as (
    select
        corr(total_price_rub, avg_usd_rub) as corr_total_vs_usd,
        corr(total_price_rub, avg_key_rate) as corr_total_vs_key_rate,
        corr(total_price_rub, inflation_yoy_pct) as corr_total_vs_inflation,
        corr(lots_count, avg_usd_rub) as corr_lots_vs_usd,
        corr(lots_count, avg_key_rate) as corr_lots_vs_key_rate,
        corr(lots_count, inflation_yoy_pct) as corr_lots_vs_inflation
    from joined
)
select
    joined.publication_month,
    joined.lots_count,
    joined.total_price_rub,
    joined.avg_price_rub,
    joined.avg_usd_rub,
    joined.avg_key_rate,
    joined.inflation_yoy_pct,
    joined.inflation_target_pct,
    correlations.corr_total_vs_usd,
    correlations.corr_total_vs_key_rate,
    correlations.corr_total_vs_inflation,
    correlations.corr_lots_vs_usd,
    correlations.corr_lots_vs_key_rate,
    correlations.corr_lots_vs_inflation
from joined
cross join correlations
order by joined.publication_month;

create or replace view mart.v_macro_correlation_base as
select
    publication_month,
    lots_count,
    total_price_rub,
    avg_usd_rub,
    avg_key_rate,
    inflation_yoy_pct,
    inflation_target_pct
from mart.v_monthly_macro_join;

create or replace view mart.v_macro_diagnostics as
with pairs as (
    select
        'total_price_rub'::text as metric,
        'avg_usd_rub'::text as factor,
        count(*) filter (where total_price_rub is not null and avg_usd_rub is not null) as observations,
        corr(total_price_rub, avg_usd_rub) as pearson_r
    from mart.v_monthly_macro_join
    union all
    select
        'total_price_rub',
        'avg_key_rate',
        count(*) filter (where total_price_rub is not null and avg_key_rate is not null),
        corr(total_price_rub, avg_key_rate)
    from mart.v_monthly_macro_join
    union all
    select
        'total_price_rub',
        'inflation_yoy_pct',
        count(*) filter (where total_price_rub is not null and inflation_yoy_pct is not null),
        corr(total_price_rub, inflation_yoy_pct)
    from mart.v_monthly_macro_join
    union all
    select
        'lots_count',
        'avg_usd_rub',
        count(*) filter (where lots_count is not null and avg_usd_rub is not null),
        corr(lots_count, avg_usd_rub)
    from mart.v_monthly_macro_join
    union all
    select
        'lots_count',
        'avg_key_rate',
        count(*) filter (where lots_count is not null and avg_key_rate is not null),
        corr(lots_count, avg_key_rate)
    from mart.v_monthly_macro_join
    union all
    select
        'lots_count',
        'inflation_yoy_pct',
        count(*) filter (where lots_count is not null and inflation_yoy_pct is not null),
        corr(lots_count, inflation_yoy_pct)
    from mart.v_monthly_macro_join
)
select
    metric,
    factor,
    observations,
    pearson_r,
    case
        when pearson_r is null or observations < 4 or abs(pearson_r) >= 1
            then null
        else erfc(abs(atanh(pearson_r)) * sqrt(observations - 3) / sqrt(2.0))
    end as approx_p_value_fisher_z,
    case
        when observations < 24 then 'directional_only_small_sample'
        else 'interpret_with_procurement_coverage_limits'
    end as statistical_note
from pairs;

create or replace view mart.v_anomalies as
with lots as (
    select
        l.lot_id,
        e.entity_name,
        l.procedure_number,
        l.lot_number,
        l.subject,
        l.focus_category,
        l.price_rub,
        l.detail_url,
        l.published_at,
        to_char(date_trunc('month', l.published_at), 'YYYY-MM') as publication_month
    from core.procurement_lot l
    left join core.entity_scope e
        on e.entity_id = l.entity_id
),
price_threshold as (
    select
        percentile_cont(0.85) within group (order by price_rub) as threshold_value
    from lots
    where price_rub is not null
),
category_medians as (
    select
        focus_category,
        percentile_cont(0.5) within group (order by price_rub) as category_median_price
    from lots
    where price_rub is not null
    group by focus_category
),
price_anomalies as (
    select
        l.entity_name,
        l.procedure_number,
        l.lot_number,
        l.subject,
        l.focus_category,
        l.price_rub,
        m.category_median_price,
        l.price_rub / nullif(m.category_median_price, 0) as value_ratio_to_category_median,
        'price_outlier'::text as anomaly_type,
        case
            when l.price_rub / nullif(m.category_median_price, 0) >= 2
                then 'price >= 2x category median'
            else 'top 15% by price'
        end as anomaly_reason,
        l.detail_url
    from lots l
    join category_medians m
        on m.focus_category = l.focus_category
    cross join price_threshold t
    where l.price_rub is not null
        and (
            l.price_rub / nullif(m.category_median_price, 0) >= 2
            or l.price_rub >= t.threshold_value
        )
),
subject_stats as (
    select
        entity_name,
        lower(trim(regexp_replace(coalesce(subject, ''), '\s+', ' ', 'g'))) as subject_key,
        min(price_rub) as price_min,
        max(price_rub) as price_max,
        count(*) as observations
    from lots
    where price_rub is not null
        and published_at is not null
    group by 1, 2
),
volatile_subjects as (
    select
        entity_name,
        subject_key,
        price_min,
        price_max
    from subject_stats
    where observations >= 2
        and price_min > 0
        and price_max / nullif(price_min, 0) >= 2
),
repeated_subject_price_shift as (
    select
        l.entity_name,
        l.procedure_number,
        l.lot_number,
        l.subject,
        l.focus_category,
        l.price_rub,
        null::numeric as category_median_price,
        v.price_max / nullif(v.price_min, 0) as value_ratio_to_category_median,
        'repeated_subject_price_shift'::text as anomaly_type,
        'same subject price spread '
            || round((v.price_max / nullif(v.price_min, 0))::numeric, 2)
            || 'x' as anomaly_reason,
        l.detail_url
    from lots l
    join volatile_subjects v
        on v.entity_name = l.entity_name
        and v.subject_key = lower(trim(regexp_replace(coalesce(l.subject, ''), '\s+', ' ', 'g')))
),
monthly_counts as (
    select
        entity_name,
        publication_month,
        count(*) as lots_count
    from lots
    where published_at is not null
    group by 1, 2
),
entity_baselines as (
    select
        entity_name,
        percentile_cont(0.5) within group (order by lots_count) as baseline
    from monthly_counts
    group by entity_name
),
burst_rows as (
    select
        m.entity_name,
        m.publication_month,
        m.lots_count,
        b.baseline
    from monthly_counts m
    join entity_baselines b
        on b.entity_name = m.entity_name
    where m.lots_count >= 3
        and b.baseline > 0
        and m.lots_count >= b.baseline * 2
),
publication_burst as (
    select
        l.entity_name,
        l.procedure_number,
        l.lot_number,
        l.subject,
        l.focus_category,
        l.price_rub,
        null::numeric as category_median_price,
        null::numeric as value_ratio_to_category_median,
        'publication_burst'::text as anomaly_type,
        'month '
            || b.publication_month
            || ' has '
            || b.lots_count
            || ' lots vs baseline '
            || round(b.baseline::numeric, 1) as anomaly_reason,
        l.detail_url
    from lots l
    join burst_rows b
        on b.entity_name = l.entity_name
        and b.publication_month = l.publication_month
),
unioned as (
    select * from price_anomalies
    union all
    select * from repeated_subject_price_shift
    union all
    select * from publication_burst
)
select distinct
    entity_name,
    procedure_number,
    lot_number,
    subject,
    focus_category,
    price_rub,
    category_median_price,
    value_ratio_to_category_median,
    anomaly_type,
    anomaly_reason,
    detail_url
from unioned
order by anomaly_type, price_rub desc nulls last;

create or replace view mart.v_price_anomalies as
select
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
where anomaly_type = 'price_outlier'
order by price_rub desc nulls last;
