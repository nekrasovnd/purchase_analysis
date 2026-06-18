# Инструкция по работе с PostgreSQL

Этот документ описывает, как поднять локальную базу, загрузить в неё curated snapshot, смотреть лоты через `psql` и `DBeaver`, а также как проверять, что загрузка прошла корректно.

## Что именно хранится в БД

База `purchase_analysis` не заменяет исходный пайплайн парсинга. Она является рабочим аналитическим слоем поверх уже собранного snapshot из:

- `configs/entity_scope.csv`
- `data/curated/*.csv`
- `output/source_sprints/*/identity_enrichment_candidates.csv`

Схемы:

- `raw` — зарезервирована под сырой слой
- `staging` — зарезервирована под промежуточный слой
- `core` — нормализованные таблицы
- `mart` — удобные view и аналитические витрины

Основные таблицы в `core`:

- `entity_scope`
- `entity_identity_enrichment`
- `entity_source_link`
- `source_assessment`
- `integration_probe`
- `procurement_lot`
- `procurement_item`
- `document_link`
- `document_text`
- `procurement_participant`
- `external_factor_daily`
- `load_audit`

Главные view в `mart`:

- `v_procurement_lots` — главный view для просмотра лотов, один ряд на один лот
- `v_procurement_lot_enriched` — лоты вместе с item-строками
- `v_document_links`
- `v_document_texts`
- `v_procurement_participants`
- `v_entity_coverage`
- `v_yearly_summary`
- `v_monthly_activity`
- `v_anomalies`
- `v_unit_price_benchmarks`
- `v_load_audit`

## Быстрый запуск с нуля

Полная локальная настройка:

```powershell
cmd /c scripts\bootstrap_local_db.cmd
```

Эта команда:

- скачивает portable `PostgreSQL` в `.local\pgsql16`, если он ещё не установлен
- инициализирует кластер в `.local\pgdata`, если его ещё нет
- поднимает локальный сервер на `127.0.0.1:55432`
- создаёт БД `purchase_analysis`, если её ещё нет
- загружает curated snapshot через `sync-postgres`
- скачивает portable `DBeaver` в `.local\apps\dbeaver`
- докачивает JDBC-драйверы для `DBeaver`

Если нужно сразу открыть GUI после bootstrap:

```powershell
cmd /c scripts\bootstrap_local_db.cmd -OpenDBeaver
```

## Отдельные команды

Установка только portable PostgreSQL:

```powershell
cmd /c scripts\install_local_postgres.cmd
```

Старт локального сервера:

```powershell
cmd /c scripts\start_local_postgres.cmd
```

Остановка локального сервера:

```powershell
cmd /c scripts\stop_local_postgres.cmd
```

Повторная загрузка текущего snapshot в БД:

```powershell
cmd /c scripts\sync_local_postgres.cmd
```

Открыть `psql`:

```powershell
cmd /c scripts\open_local_psql.cmd
```

Выполнить одну SQL-команду через `psql`:

```powershell
cmd /c scripts\open_local_psql.cmd -Command "select count(*) from mart.v_procurement_lots;"
```

Открыть `DBeaver` сразу с готовым подключением:

```powershell
cmd /c scripts\open_dbeaver_purchase_analysis.cmd
```

## Где именно лежит локальная установка

Portable PostgreSQL:

- бинарники: `.local\pgsql16`
- data directory: `.local\pgdata`
- лог: `.local\pg.log`

Portable DBeaver:

- приложение: `.local\apps\dbeaver`
- workspace: `.local\dbeaver-workspace`

Кэш DBeaver-драйверов:

- `%APPDATA%\DBeaverData\drivers`

## Параметры подключения

Локальная база по умолчанию:

- host: `127.0.0.1`
- port: `55432`
- database: `purchase_analysis`
- user: `postgres`

В текущем portable-контуре пароль не требуется, потому что кластер инициализирован с `trust` для локальной разработки.

## Как загружается snapshot

Команда `sync-postgres`:

- применяет все SQL-файлы из `db/ddl`, `db/views`, `db/marts`
- очищает `core`-таблицы
- загружает scope из `configs/entity_scope.csv`
- накладывает coverage/counters из `data/curated/entity_coverage.csv`
- загружает `data/curated/*.csv` в нормализованный `core`
- подтягивает `identity_enrichment_candidates.csv` из `output/source_sprints`
- записывает аудит загрузки в `core.load_audit`

CLI-вариант без wrapper-скрипта:

```powershell
$env:PYTHONPATH = "src"
python -m purchase_analysis.cli sync-postgres --dsn "postgresql://postgres@127.0.0.1:55432/purchase_analysis"
```

## Что смотреть в первую очередь

Все лоты:

```sql
select *
from mart.v_procurement_lots
order by published_at desc nulls last
limit 100;
```

Только лоты с ценой:

```sql
select *
from mart.v_procurement_lots
where price_rub is not null
order by price_rub desc
limit 100;
```

Срез по одной компании:

```sql
select *
from mart.v_procurement_lots
where entity_name ilike '%СберТех%'
order by published_at desc nulls last
limit 100;
```

Item-строки:

```sql
select *
from mart.v_procurement_lot_enriched
where entity_name ilike '%СберТех%'
order by published_at desc nulls last, procedure_number, lot_number, line_no
limit 200;
```

Документы:

```sql
select *
from mart.v_document_links
order by discovered_at desc
limit 100;
```

Аномалии:

```sql
select *
from mart.v_anomalies
order by anomaly_type, value_ratio_to_category_median desc nulls last
limit 100;
```

## Готовые SQL-файлы

В `db/queries` уже лежат готовые вкладки для `DBeaver`:

- `001_explore.sql` — базовый набор запросов
- `002_health_checks.sql` — контроль целостности и наполнения
- `003_recent_lots.sql` — последние лоты
- `004_priced_lots.sql` — лоты с раскрытой ценой
- `005_entity_focus_template.sql` — шаблон под одну компанию
- `006_anomalies.sql` — аномалии
- `007_documents.sql` — документы и text coverage

## Проверка, что загрузка прошла успешно

Сначала можно посмотреть историю загрузок:

```sql
select
    load_audit_id,
    procurement_lot_rows,
    procurement_item_rows,
    document_link_rows,
    document_text_rows,
    procurement_participant_rows,
    load_duration,
    loaded_at
from mart.v_load_audit
order by load_audit_id desc
limit 20;
```

Полный health-check:

```powershell
cmd /c scripts\open_local_psql.cmd -Command "\i 'D:/Nikita/Work/purchase_analysis/db/queries/002_health_checks.sql'"
```

Что именно проверяет `002_health_checks.sql`:

- row counts по всем `core`-таблицам
- orphan-проверки по `lot_id` и `document_id`
- краткую статистику по источникам

Нормальный результат:

- таблицы не пустые
- `items_without_lot = 0`
- `documents_without_lot = 0`
- `document_texts_without_document = 0`
- `participants_without_lot = 0`

## Как работать через DBeaver

Запуск:

```powershell
cmd /c scripts\open_dbeaver_purchase_analysis.cmd
```

Launcher:

- гарантирует, что PostgreSQL поднят
- открывает сохранённое подключение `purchase_analysis`
- открывает набор SQL-вкладок под типовые задачи

Удобный базовый маршрут внутри `DBeaver`:

1. Открыть вкладку `003_recent_lots.sql`, чтобы посмотреть свежие лоты.
2. Открыть `004_priced_lots.sql`, если нужен только денежный контур.
3. Открыть `005_entity_focus_template.sql` и поменять `ILIKE` под нужное юрлицо.
4. Открыть `006_anomalies.sql`, если нужен быстрый обзор выбросов.
5. Открыть `007_documents.sql`, если нужен слой документов.

## Что важно понимать про данные

- `mart.v_procurement_lots` содержит все core-лоты, а не только priced lots.
- Лоты без цены тоже сохраняются, просто у них `price_rub is null`.
- `mart.v_procurement_lot_enriched` может размножать лот по item-строкам — это нормально.
- `load_audit` хранит факт каждой повторной загрузки snapshot в БД.
- БД отражает текущий curated snapshot, а не автоматически “живой интернет”.

## Частые сценарии

Полностью пересобрать локальную БД после обновления `data/curated`:

```powershell
cmd /c scripts\sync_local_postgres.cmd
```

Поднять всё на новой машине:

```powershell
python -m pip install -e .
cmd /c scripts\bootstrap_local_db.cmd
```

Быстро проверить, что база жива:

```powershell
cmd /c scripts\open_local_psql.cmd -Command "select count(*) as total_lots from mart.v_procurement_lots;"
```

Открыть GUI и сразу кликать данные:

```powershell
cmd /c scripts\open_dbeaver_purchase_analysis.cmd
```

## Troubleshooting

Если PowerShell ругается на execution policy:

- используй `.cmd`-обёртки из `scripts`, а не прямой запуск `.ps1`

Если `DBeaver` открывается без драйвера:

- повторно выполни `cmd /c scripts\install_dbeaver.cmd`

Если база не стартует:

- проверь лог `.local\pg.log`
- проверь, не занят ли порт `55432`

Если нужно полностью пересоздать local cluster:

- останови сервер
- удали `.local\pgdata`
- снова запусти `cmd /c scripts\install_local_postgres.cmd`

Если нужно полностью пересобрать DBeaver portable:

- удали `.local\apps\dbeaver`
- снова запусти `cmd /c scripts\install_dbeaver.cmd`
