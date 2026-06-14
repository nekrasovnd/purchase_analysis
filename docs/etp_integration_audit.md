# ETP Integration Audit

Date: `2026-06-14`

This note documents the additional public ETP integrations and reverse-engineering checks that were taken from research into reproducible code:

- `ZakazRF`
- `Lot-Online`
- `SberB2B public need cards`

The goal of these adapters is not to inflate the core mart with weak matches, but to prove the exact transport and keep the evidence in a separate probe layer.

## Artifacts

- Probe summary CSV: `data/curated/etp_integration_probe.csv`
- ZakazRF raw responses: `data/raw/zakazrf/`
- Lot-Online raw responses: `data/raw/lot_online/`
- SberB2B raw cards/goods/documents: `data/raw/sberb2b/`
- SberB2B frontend JS snapshots: `data/raw/sberb2b/js/`

## ZakazRF

Verified public entrypoint:

- `https://etp.zakazrf.ru/NotificationEx`

Verified exact selector transport:

- `GET /Customer?IsPartialView=1&_orm_DialogMode=select...`
- `POST /Customer?...&IsTableContentOnlyRequest=1&orm_update_request=`

What is implemented:

- main page fetch
- `_orm_PageID` extraction
- customer dialog fetch
- hidden dialog-state extraction
- exact customer lookup by INN
- internal customer-id extraction
- exact notification filter `NotificationEx?Customer=<id>`
- result count parsing
- first-page notification row parsing

Observed outcome for the Sber scope:

- exact customer matches were reproduced for:
  - `PАО Сбербанк России`
  - `АО Сбербанк-АСТ`
  - `ООО Страховой брокер Сбербанка`
- all matched customer ids returned `0` public notifications

Pipeline decision:

- adapter is operational
- exact matches are stored in `entity_source_links.csv` and `etp_integration_probe.csv`
- no ZakazRF lots are added to `procurement_lots.csv` in the current run because exact public result sets are empty

## Lot-Online

Verified public page:

- `https://tender.lot-online.ru/etp/app/SearchLots/`

Verified hidden public transport:

- `GET https://tender.lot-online.ru/etp/searchServlet`

Verified exact query shapes:

- title search:
  - `{"title":"...","types":["BUYING","RFI","SMALL_PURCHASE"]}`
- exact customer search:
  - `{"customer":{"title":"<INN>"},"types":[...]}`
- exact organizer search:
  - `{"organizer":{"title":"<INN>"},"types":[...]}`

What is implemented:

- hidden `searchServlet` adapter
- exact customer and organizer INN probes
- title-mention probe
- pagination by `limit.min` / `limit.max`
- normalized lot parsing
- raw JSON payload capture

Observed outcome for the Sber scope:

- exact customer INN probes return `0` observed rows
- exact organizer INN probes return `0` observed rows
- title search returns many mention-based hits, but they are noisy and often belong to other organizations

Pipeline decision:

- adapter is operational
- exact probes are stored in `etp_integration_probe.csv`
- title mentions are intentionally excluded from the core mart because they are not precise enough for entity-level procurement attribution

## SberB2B Public Cards

Verified public card pattern:

- `https://sberb2b.ru/request/supplier/preview/<uuid>` redirects to `https://sberb2b.ru/needs/<need_id>`

Verified public data layers:

- server-rendered public card HTML contains `need-for-public-page`
- embedded JSON exposes need id, condition id, customer fields, deadlines, documents and public need attributes
- hidden goods endpoint is public for known `condition_id`:
  - `/request/api/{condition_id}/get-from-description-goods-items/customer?page=1&limit=20`
  - `/request/api/{condition_id}/get-from-description-goods-items/supplier?page=1&limit=20`

What is implemented:

- public card parser
- goods API client
- retry/backoff for transient 429/500/502/503/504
- document link extraction
- bounded document download
- DOCX/PDF text extraction with PII masking
- evidence rows in `etp_integration_probe.csv`

Observed outcome for the Sber scope:

- `2310` item rows with unit price
- `4147` document links
- `250` document texts
- `25` customer-side goods probes returned HTTP 200 JSON
- `25` supplier-side goods probes returned HTTP 200 JSON

Winner/participant endpoint research:

- Browser inspection of a completed public need card showed no `window.Routing` route map on the public page.
- The public page did not trigger offer/supplier XHR resources during load.
- Frontend JS bundle inspection found route names such as `need_offer_list`, `need_selected_supplier_list`, `commerce_need_procedure_results_offers_list_api`, `competitive_analysis_list_api`, and `request_api_get_supplier_list`, but the FOS route export endpoints were not public.
- Candidate unauthenticated HTTP probes for offers/suppliers by `condition_id`, `need_id`, and public number returned 404/403/login redirects, while the goods endpoint returned 200.

Pipeline decision:

- SberB2B is used as enrichment for items, unit prices, documents and document text.
- Failed public offer/winner probes are retained as technical evidence.
- `winners_total=0` is intentional: sellers/offers are not promoted to winners without a confirmed public winner source.

## Bottom Line

Both integrations are now implemented as working, reproducible adapters.

- `ZakazRF`: technically works, exact customer matches exist, but public result sets for the target scope are empty
- `Lot-Online`: technically works, hidden API is verified, but exact INN probes are empty and title search is too noisy for the core mart
- `SberB2B`: public enrichment works for goods/documents; public winner/offer endpoints are not exposed without authorization
