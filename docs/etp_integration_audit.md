# ETP Integration Audit

Date: `2026-06-13`

This note documents the two additional public ETP integrations that were taken from research into reproducible code:

- `ZakazRF`
- `Lot-Online`

The goal of these adapters is not to inflate the core mart with weak matches, but to prove the exact transport and keep the evidence in a separate probe layer.

## Artifacts

- Probe summary CSV: `data/curated/etp_integration_probe.csv`
- ZakazRF raw responses: `data/raw/zakazrf/`
- Lot-Online raw responses: `data/raw/lot_online/`

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

## Bottom Line

Both integrations are now implemented as working, reproducible adapters.

- `ZakazRF`: technically works, exact customer matches exist, but public result sets for the target scope are empty
- `Lot-Online`: technically works, hidden API is verified, but exact INN probes are empty and title search is too noisy for the core mart
