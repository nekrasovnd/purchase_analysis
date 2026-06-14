create schema if not exists raw;
create schema if not exists staging;
create schema if not exists core;
create schema if not exists mart;

create table if not exists core.entity_scope (
    entity_id bigserial primary key,
    entity_key text unique,
    group_name text not null,
    entity_name text not null unique,
    entity_type text not null,
    inn text,
    ogrn text,
    kpp_list text,
    official_name text,
    short_name text,
    brand_aliases text,
    search_terms text,
    identity_source text,
    identity_confidence text,
    identity_notes text,
    is_priority_focus boolean not null default false,
    eis_search_term text,
    roseltorg_customer_query text,
    resolved_inn text,
    eis_entity_code text,
    eis_entity_name text,
    eis_resolved_inn text,
    eis_resolved_kpp text,
    eis_resolved_ogrn text,
    eis_fz94id text,
    eis_fz223id text,
    eis_223_open_count integer not null default 0,
    eis_results_url text,
    roseltorg_lot_count integer not null default 0,
    sberbank_ast_candidate_count integer not null default 0,
    sberbank_ast_lot_count integer not null default 0,
    zakazrf_candidate_count integer not null default 0,
    zakazrf_lot_count integer not null default 0,
    lot_online_lot_count integer not null default 0,
    lot_online_title_mention_count integer not null default 0,
    loaded_at timestamptz not null default now()
);

create table if not exists core.entity_identity_enrichment (
    enrichment_id bigserial primary key,
    entity_key text,
    entity_name text not null,
    inn text,
    source_system text not null,
    field_name text not null,
    proposed_value text not null,
    evidence text,
    confidence text not null,
    decision text not null default 'review',
    checked_at timestamptz,
    loaded_at timestamptz not null default now()
);

create table if not exists core.entity_source_link (
    entity_source_link_id bigserial primary key,
    entity_name text not null,
    source_system text not null,
    external_customer_key text not null,
    external_customer_name text,
    external_inn text,
    external_kpp text,
    query_used text,
    resolution_method text,
    records_total integer not null default 0,
    candidate_rank integer not null default 1,
    loaded_at timestamptz not null default now(),
    unique (entity_name, source_system, external_customer_key)
);

create table if not exists core.source_assessment (
    source_system text primary key,
    platform_name text not null,
    platform_url text not null,
    operational_status text not null,
    inclusion_status text not null,
    access_mode text not null,
    rationale text not null,
    coverage_note text,
    checked_at timestamptz not null default now()
);

create table if not exists core.integration_probe (
    integration_probe_id bigserial primary key,
    source_system text not null,
    entity_name text not null,
    probe_mode text not null,
    query_used text,
    matched_external_id text,
    matched_external_name text,
    matched_external_inn text,
    matched_external_role text,
    records_total integer not null default 0,
    candidate_rank integer not null default 1,
    included_in_core boolean not null default false,
    note text,
    checked_at timestamptz not null default now()
);

create table if not exists core.procurement_lot (
    lot_id bigserial primary key,
    entity_id bigint references core.entity_scope(entity_id),
    source_system text not null,
    platform_section text,
    procedure_number text not null,
    lot_number text not null,
    subject text not null,
    customer_name text,
    region text,
    status text,
    tender_type text,
    price_rub numeric(18, 2),
    currency text,
    published_at timestamp,
    deadline_at timestamp,
    application_deadline timestamp,
    method_name text,
    detail_url text,
    tags text,
    delivery_place text,
    focus_category text,
    sberb2b_need_id text,
    sberb2b_condition_id text,
    sberb2b_status text,
    sberb2b_state text,
    sberb2b_public_request_status text,
    search_url text,
    duplicate_group_size integer not null default 1,
    unique (source_system, procedure_number, lot_number)
);

create table if not exists core.procurement_item (
    item_id bigserial primary key,
    lot_id bigint not null references core.procurement_lot(lot_id),
    line_no integer not null default 1,
    item_name text not null,
    okpd_code text,
    okpd_name text,
    quantity numeric(18, 4),
    unit text,
    okei_code text,
    item_description text,
    item_id_external text,
    unit_price_rub numeric(18, 2),
    line_total_rub numeric(18, 2),
    unit_price_source text,
    sberb2b_need_id text,
    sberb2b_condition_id text,
    focus_category text,
    price_rub numeric(18, 2)
);

create table if not exists core.document_link (
    document_id bigserial primary key,
    lot_id bigint not null references core.procurement_lot(lot_id),
    document_name text,
    document_url text,
    document_storage_name text,
    document_mime_type text,
    document_size_bytes bigint,
    document_hash text,
    local_path text,
    extraction_method text,
    text_chars integer,
    ocr_required boolean not null default false,
    pii_findings_count integer not null default 0,
    is_available boolean not null default true,
    pii_masked boolean not null default true,
    discovered_at timestamptz not null default now()
);

create table if not exists core.document_text (
    document_text_id bigserial primary key,
    document_id bigint references core.document_link(document_id),
    lot_id bigint references core.procurement_lot(lot_id),
    document_name text,
    local_path text,
    extraction_method text,
    text_chars integer not null default 0,
    ocr_required boolean not null default false,
    pii_findings_count integer not null default 0,
    text_preview text,
    extracted_at timestamptz not null default now()
);

create table if not exists core.procurement_participant (
    participant_id bigserial primary key,
    lot_id bigint references core.procurement_lot(lot_id),
    source_system text not null,
    procedure_number text not null,
    lot_number text not null,
    participant_role text not null,
    participant_name text,
    participant_inn text,
    participant_external_id text,
    offer_price_rub numeric(18, 2),
    is_winner boolean not null default false,
    evidence_source text,
    loaded_at timestamptz not null default now()
);

create table if not exists core.external_factor_daily (
    factor_date date primary key,
    usd_rub numeric(18, 6),
    nominal numeric(18, 6),
    key_rate numeric(8, 4),
    inflation_yoy_pct numeric(8, 4),
    inflation_target_pct numeric(8, 4),
    key_rate_month_end numeric(8, 4),
    loaded_at timestamptz not null default now()
);
