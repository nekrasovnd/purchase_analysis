create index if not exists idx_procurement_lot_entity_id
    on core.procurement_lot (entity_id);

create index if not exists idx_procurement_lot_published_at
    on core.procurement_lot (published_at);

create index if not exists idx_procurement_lot_focus_category
    on core.procurement_lot (focus_category);

create index if not exists idx_procurement_item_lot_id
    on core.procurement_item (lot_id);

create index if not exists idx_document_link_lot_id
    on core.document_link (lot_id);

create index if not exists idx_document_text_lot_id
    on core.document_text (lot_id);

create index if not exists idx_procurement_participant_lot_id
    on core.procurement_participant (lot_id);

create index if not exists idx_procurement_participant_proc_key
    on core.procurement_participant (source_system, procedure_number, lot_number);

create index if not exists idx_entity_source_link_entity_source
    on core.entity_source_link (entity_name, source_system);

create index if not exists idx_integration_probe_entity_source
    on core.integration_probe (entity_name, source_system);
