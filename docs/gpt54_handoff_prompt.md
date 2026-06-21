# Handoff Prompt For GPT 5.4

Use this prompt in a fresh chat.

```text
Ты работаешь в репозитории:
D:\Nikita\Work\purchase_analysis

Контекст:
Это проект анализа закупок группы Сбер за 2024-2025 годы. В прошлых чатах автоматический парсинг часто упирался в лимиты/антибот/слишком широкий сбор, поэтому текущий рабочий режим: не запускать массовый run-all для добычи новых данных без прямого разрешения Никиты. Работаем source sprint: один источник -> ограниченный набор юрлиц/ИНН -> raw evidence -> accepted/rejected report.

Главное правило:
Искать можно широко, принимать в core только строго. Нельзя добавлять строки в core по одному бренду/title mention/похожему названию. Нужна точная атрибуция к юрлицу Сбера, безопасная роль заказчика/организатора и период 2024-2025.

Что уже сделано:
1. `configs/entity_scope.csv` переделан из простой таблицы названий/ИНН в identity-card scope на 26 юрлиц:
   - `entity_key`
   - `inn`
   - `ogrn`
   - `kpp_list`
   - `official_name`
   - `short_name`
   - `brand_aliases`
   - `search_terms`
   - `identity_source`
   - `identity_confidence`
   ОГРН/КПП заполнены только там, где было локальное evidence; пустые поля не считать ошибкой.

2. Добавлен общий слой:
   `src/purchase_analysis/entity_resolution.py`
   В нем важные функции:
   - `load_entity_scope(path)`
   - `build_search_terms(entity, source_system=...)`
   - `classify_entity_match(...)`
   - `enrichment_row(...)`

3. Правила:
   - `accept`: точный INN, точный OGRN, либо KPP + точное официальное имя, при безопасной роли.
   - `review`: совпало только имя/бренд без идентификаторов.
   - `reject`: supplier/operator/platform/title_mention/text_mention, неверный период, нет точной идентичности.

4. EIS scripts и pipeline частично переведены на общий resolver:
   - `scripts/eis_prompt2_batch_sprint.py`
   - `scripts/eis_prompt2_source_sprint.py`
   - `src/purchase_analysis/pipeline.py`

5. Документация:
   - `docs/entity_resolution_protocol.md` - протокол identity/search/enrichment.
   - `docs/collaboration_prompts.md` - главный протокол работы, особенно Prompt 2.
   - `docs/entity_scope_audit_2026-06-14.md` - аудит scope.
   - `README.md` обновлен с предупреждением: текущие curated метрики относятся к старому snapshot, а новый scope уже 26 юрлиц.

6. SQL:
   - `db/ddl/001_schema.sql` расширен полями identity и таблицей `core.entity_identity_enrichment`.

7. Тесты:
   - `tests/test_entity_resolution.py` добавлен.
   - Последняя проверка:
     `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`
     Результат: 28 tests OK.

Важное состояние git/worktree:
В рабочем дереве есть много старых измененных `data/raw` и `data/curated` файлов от прежних прогонов. Не надо их автоматически коммитить/откатывать. Для чистого коммита брать только системные изменения: scope, resolver, pipeline/scripts, docs, tests, SQL. Если Никита явно попросит закоммитить data artifacts, сначала показать список и размер.

Что осталось сделать:
1. Продолжать разбор источников по Prompt 2, по одному:
   - ЕИС
   - ЗаказРФ
   - Росэлторг
   - ЛотОнлайн
   - ТекТорг
   - РТС-тендер
   - Сбербанк-АСТ
   - ЕТП ГПБ
2. Для каждого source sprint:
   - использовать `load_entity_scope`;
   - строить queries через `build_search_terms`;
   - сохранять raw evidence;
   - принимать через `classify_entity_match`;
   - писать accepted/duplicates/rejected/review;
   - новые ОГРН/КПП/официальные названия писать в `identity_enrichment_candidates.csv`, не напрямую в core.
3. Следующий практичный шаг: выбрать один источник и адаптировать его sprint под новый resolver. Никита хочет работать вместе и помогать руками, если будет антибот/лимит/сомнение.

Как общаться с Никитой:
- писать коротко;
- если есть ограничение/сомнение/антибот - сразу сказать;
- не делать вид, что источник “не содержит данных”, пока это не проверено;
- не запускать большой парсинг без согласия;
- если нужен ручной шаг, дать конкретную инструкцию: URL, фильтры, что скачать, куда положить.

Начни с короткого status-check:
1. `git status --short`
2. проверить `docs/collaboration_prompts.md`
3. проверить `docs/entity_resolution_protocol.md`
4. спросить Никиту, какой источник берем первым, если он сам не указал.
```

## Database Status Addendum

Include this addendum together with the handoff prompt above so the next chat does not break the local DB setup.

```text
Database / local PostgreSQL status as of 2026-06-18:

- Portable PostgreSQL is already installed in `.local/pgsql16`.
- Local cluster is already initialized in `.local/pgdata`.
- Database name: `purchase_analysis`.
- Host: `127.0.0.1`.
- Port: `55432`.
- User: `postgres`.
- Portable DBeaver Community is already installed in `.local/apps/dbeaver`.
- Full DB usage guide: `docs/database_usage.md`.

Preferred wrappers:
- `scripts/bootstrap_local_db.cmd`
- `scripts/start_local_postgres.cmd`
- `scripts/sync_local_postgres.cmd`
- `scripts/open_local_psql.cmd`
- `scripts/open_dbeaver_purchase_analysis.cmd`
- `scripts/stop_local_postgres.cmd`

Rules:
- Do not delete/reset `.local`.
- Do not recreate the PostgreSQL cluster unless Nikita explicitly asks or the DB is actually broken.
- Do not reinstall DBeaver/PostgreSQL from scratch if the wrappers already work.
- For DB work, prefer `sync-postgres` or the wrapper scripts and keep `docs/database_usage.md`, README, and SQL schema/docs in sync.
```

## Source Status Addendum: Tender.Pro

Include this addendum too so the next chat does not re-discover the same public source from scratch.

```text
Tender.Pro / public company-purchases sprint status as of 2026-06-18:

- New public source tested: `https://www.tender.pro/api/companies/list`
- Working transport:
  - company search by `inn`
  - company search by exact `title`
  - then public company page `https://www.tender.pro/api/company/<id>/view?active_tab=purchases`
- Important limitation:
  - there is no separate public `ogrn` field in the search form; OGRN can only be tried as a title fallback and usually returns 0
- Public exact company matching works:
  - `parse_company_candidates(...)` -> company cards from the catalog search
  - `parse_company_profile(...)` -> public company profile with `ИНН/КПП`, often `ОГРН`, official name, short name
  - `classify_entity_match(...)` then safely accepts/rejects the company before any lots are used
- Current implementation:
  - client: `src/purchase_analysis/clients/tender_pro.py`
  - tests: `tests/test_tender_pro.py`
  - source sprint: `scripts/tender_pro_prompt2_source_sprint.py`
- Latest full-scope batch:
  - `output/source_sprints/tender_pro_prompt2_full_scope_2026-06-18_v2/summary.json`
- Latest full-scope outcome:
  - scope entities: `26`
  - exact company matches: `20`
  - accepted new 2024-2025 rows: `1`
  - accepted entity: `ООО Инстамарт Сервис (Купер)`
  - many other entities resolved to exact Tender.Pro company pages, but their public purchase tabs had either 0 rows or only rows outside the 2024-2025 window
- Useful enrichment evidence was found for some entities:
  - extra KPPs for `ПАО Сбербанк России` and `АО Сбербанк Лизинг`
  - OGRN for `ООО СберЛогистика`, `ООО Инстамарт Сервис (Купер)`, `ООО Инновационная медицина (СберЗдоровье)`
- Raw evidence:
  - `data/raw/tender_pro/tender_pro_prompt2_full_scope_2026-06-18_v2/`
- Rule:
  - do not promote Tender.Pro title-only matches to core; only lots from exact matched company pages are safe
```

## Source Status Addendum: B2B-Center

Include this addendum too so the next chat does not waste time re-opening the same B2B paths.

```text
B2B-Center sprint status as of 2026-06-18:

- Current implementation:
  - client: `src/purchase_analysis/clients/b2b_center.py`
  - tests: `tests/test_b2b_center.py`
  - source sprint: `scripts/b2b_center_prompt2_source_sprint.py`
  - offline detail re-enrichment: `scripts/b2b_center_reenrich_saved_details.py`
- Exact organization lookup works via public endpoint:
  - `https://www.b2b-center.ru/api/search/organizations/`
  - search strategy already tries `ИНН`, then `ОГРН/КПП`, then exact names through `build_search_terms(...)`
  - exact candidate acceptance still goes only through `classify_entity_match(...)`
- Important parsing breakthrough:
  - `market-next` detail pages are now parsed from inline `var __pinia=...` state via `js2py`
  - this extracts at least:
    - subject
    - organizer name/profile
    - publication date
    - application deadline
    - positions count
    - delivery address
    - status bucket
    - total price when `trade_result_money` is public
- Anti-bot state:
  - B2B search/list pages (`/market/?...firm_id=...` or `customer_id=...`) are currently unstable and often fall into anti-bot pages
  - two observed public block modes:
    - captcha/rate-limit page with text about `превышен максимальный лимит скорости просмотра страниц`
    - plain `403 Forbidden` page with `If you are not a bot, please copy the report...`
  - code now detects both:
    - `is_rate_limited_page(...)`
    - `is_forbidden_page(...)`
  - detail parser raises explicit anti-bot error instead of silently returning empty fields
- Best saved probe so far:
  - batch: `b2b_center_probe_7736663049`
  - raw detail HTML: `data/raw/b2b_center/b2b_center_probe_7736663049/`
  - offline reenriched items: `output/source_sprints/b2b_center_probe_7736663049/items_reenriched.csv`
  - local reenrichment outcome from saved HTML only:
    - parsed detail cards: `6`
    - priced rows recovered: `2`
    - blocked detail cards: `2`
    - priced procedures recovered:
      - `3688284` -> `10331548 RUB без НДС`
      - `3695172` -> `852905 RUB без НДС`
- Current live blocker evidence:
  - one-entity blocked batch: `output/source_sprints/b2b_center_probe_7736663049_forbidden/`
  - in that batch exact candidate resolution still works, but list retrieval over 2024-2025 ends in overflow windows / anti-bot instead of rows
- Rules for the next chat:
  - do not conclude that B2B has `0` data just because a live run returns `0` rows
  - the current limitation is transport / anti-bot, not lack of exact entity matches
  - if new raw detail HTML or manual exports appear under local folders, run `b2b_center_reenrich_saved_details.py` before trying fresh network scraping again
  - if live transport is retried, keep batches small and expect the blocker to be external
```

## Mini Prompt: Source Sprint

```text
Берем один источник ЭТП как source sprint.

Источник: <название + URL>

Правила:
- не запускать run-all;
- загрузить юрлица через `load_entity_scope`;
- построить queries через `build_search_terms`;
- искать по INN/OGRN/KPP/official_name/aliases, если источник это позволяет;
- core acceptance только через `classify_entity_match`;
- title/brand/name-only -> review, не core;
- supplier/operator/platform -> reject/probe evidence;
- новые идентификаторы -> `identity_enrichment_candidates.csv`;
- raw evidence -> `data/raw/<source>/`;
- итог -> `output/source_sprints/<source>_<date>/`.

Выход:
- accepted_new_rows;
- duplicates;
- rejected_count_by_reason;
- review_count;
- enrichment_candidates;
- raw files saved;
- next manual step if blocked.
```
