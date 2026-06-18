-- Последние документы и extracted text coverage.
select
    entity_name,
    source_system,
    procedure_number,
    lot_number,
    document_name,
    text_chars,
    extraction_method,
    is_available,
    document_url,
    local_path
from mart.v_document_links
order by discovered_at desc, source_system, procedure_number, lot_number
limit 200;
