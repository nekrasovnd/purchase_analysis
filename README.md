# Purchase Analysis: закупки группы Сбер

Репозиторий содержит воспроизводимое решение для тестового задания по сбору, очистке и анализу открытых данных о закупках группы Сбер за `2024–2025` годы.

Ключевой принцип решения: разделить `официальный контур идентификации` и `рабочие контуры наблюдения`.

- `ЕИС` используется для резолвинга юридических лиц и контрольной проверки открытого покрытия по `44-ФЗ`/`223-ФЗ`.
- `Росэлторг` используется для публичных карточек лотов, ссылок на документы и seller-данных из JSON-LD.
- `Сбербанк-АСТ` используется как основной масштабируемый источник procurement-релевантных процедур.
- `SberB2B` используется как enrichment-слой для карточек из AST: товары, unit price, документы, текст документов.
- `Банк России` используется как внешний слой макрофакторов для корреляционного анализа.

Важно: `Сбербанк-АСТ` — это единый реестр процедур, где есть не только закупки, но и реализация имущества. Поэтому в итоговый слой попадают только procurement-релевантные записи; процедуры продажи активов и банкротные продажи отфильтровываются как `out of scope`.

## Итог текущего прогона

Финальный прогон выполнен `2026-06-14`.

- Юрлиц в периметре: `24`
- Юрлиц с фактическими строками в `procurement_lots.csv`: `13`
- Лотов после дедупликации: `1533`
- Удалено дублей: `65`
- Источники core-лотов: `Сбербанк-АСТ` - `940`, `Росэлторг` - `593`
- Лотов с раскрытой ценой: `382`, покрытие ценой: `24.55%`
- Товарных строк: `3308`, из них с unit price: `2310`
- Ссылок на документы: `3982`
- Документов с извлечённым текстом: `250`, всего `4.33 млн` символов
- Строк участников/продавцов: `593`
- Подтверждённых победителей: `0`, потому что публичный winner/offer endpoint не раскрыт без авторизации
- Unit-price benchmark rows: `709`, anomaly flags: `7`
- Макродней Банка России: `613`, добавлены `USD/RUB`, ключевая ставка и ИПЦ

Примечание: после этого прогона `configs/entity_scope.csv` был расширен до `26` identity-card строк. Метрики выше относятся к последнему полному curated snapshot и не должны использоваться как актуальная статистика нового scope до согласованного refresh.

Важно: более ранний прогон давал `2933` строки `Сбербанк-АСТ`, но включал около двух тысяч процедур продажи/утилизации имущества. Сейчас эти out-of-scope процедуры исключены из core, поэтому итоговая витрина меньше, зато достовернее как набор именно закупок.

## Что внутри

- `configs/entity_scope.csv` — проверенный identity scope юридических лиц группы Сбер: ИНН, ОГРН/КПП где подтверждено, официальные имена, алиасы и поисковые термины.
- `docs/entity_resolution_protocol.md` — правила расширенного поиска, строгого принятия в core и дозаполнения пустых идентификаторов через review/enrichment.
- `src/purchase_analysis` — ETL-клиенты, пайплайн, аналитические витрины и CLI.
- `db/ddl`, `db/views`, `db/marts` — PostgreSQL-схема и полезные SQL-представления.
- `data/raw` — сырые HTML/XML-снапшоты источников.
- `data/curated` — очищенные таблицы и аналитические витрины.
- `data/reports` — отчёты по качеству и LLM-ready prompt pack.
- `notebooks/purchase_analysis.ipynb` — основной аналитический отчёт.

Все итоговые CSV пишутся в `UTF-8 with BOM (utf-8-sig)`, чтобы корректно открываться в Excel, PowerShell и типичных Windows-инструментах без проблем с кириллицей.

## Повторное исследование ЭТП

Все площадки из ТЗ были повторно исследованы и отражены в `data/curated/source_assessment.csv`.
Дополнительный точечный проход по новым источникам выполнен `2026-06-14`; итоговая доказательная сводка лежит в `output/data_discovery/final_data_expansion_report.md`.

Главный результат этого прохода: `0` новых достоверных закупок добавлено в core после дедупликации. Это не пустой прогон, а результат exact-INN/role/date проверок: найденные RTS Sber-карточки уже присутствовали в `procurement_lots.csv`, а остальные совпадения были нулевыми или ложными операторскими совпадениями.

Статусы:

- `operational / used_in_pipeline`: `ЕИС`, `Росэлторг`, `Сбербанк-АСТ`
- `operational / enrichment`: `SberB2B public need cards`
- `operational / probe-only`: `ЗаказРФ`, `ЛотОнлайн`, `РТС-Тендер`
- `research_only / exact-probe-zero`: `ТЭК-Торг`, `ЭТП ГПБ`

Почему в итоговый пайплайн вошли только три ЭТП:

- `ЕИС` даёт лучший официальный контур идентификации; full-scope exact sprint по `44-ФЗ`/`223-ФЗ` проверил `52` комбинации и нашёл только `3` уже учтённые аудитные процедуры.
- `Росэлторг` даёт удобные публичные карточки лотов и документы.
- `Сбербанк-АСТ` даёт массовое покрытие за 2024–2025 через публичный `LongDictionary` и paged search endpoint.
- `SberB2B` раскрывает embedded JSON карточки `need-for-public-page` и скрытый goods API `/request/api/{condition_id}/get-from-description-goods-items/customer`.

Почему остальные пока не в продовом контуре:

- `ЗаказРФ`: публичный реестр и hidden form submit воспроизведены; exact-INN customer matches дают `0` публичных уведомлений в текущем scope.
- `ЛотОнлайн`: скрытый `searchServlet` воспроизведён; exact customer/organizer INN probes дают `0` строк, title search слишком шумный для core.
- `РТС-Тендер`: Anti-DDoS пройден через Chrome/Playwright; скрытая модель `/poisk/api/TabValues/0`, JS-бандлы и frontend-validated поиск воспроизведены. Строгий `rts_only` по 13 INN, ролям заказчика/организатора и датам публикации 2024–2025 дал `0`; all-ETP режим нашёл 3 точные Sber-процедуры, но все уже были в core из `Сбербанк-АСТ`.
- `ТЭК-Торг`: официальный SOAP API `https://api.tektorg.ru/procedures/wsdl` проверен по `customerINN` и `organizerINN`; exact Sber-INN пробы дали только нулевые SOAP faults.
- `ЭТП ГПБ`: через Nuxt/Playwright network trace найдены `api/v2/procedures` и `api/v2/customers`; exact customer API подтвердил только `СберОбразование`, но его процедуры относятся к 2022 году, не к 2024–2025.

## Архитектура

```text
entity_scope.csv ---------------> verified entity identity layer
EIS -----------------------------> entity resolution / coverage control
Roseltorg -----------------------> observed lots + documents
Sberbank-AST -------------------> observed procurement procedures
SberB2B public cards -----------> items + unit prices + documents + doc text
CBR -----------------------------> USD/RUB + key rate + CPI

raw snapshots -> normalized lots/items/documents/participants ->
CSV marts + PostgreSQL DDL/views + Jupyter notebook + LLM prompt pack
```

Расширенный поиск по источникам строится через `src/purchase_analysis/entity_resolution.py`: можно искать по ИНН, ОГРН, КПП, официальному названию и алиасам, но в core попадают только строки, прошедшие общий фильтр точной идентичности и роли заказчика/организатора. Новые найденные идентификаторы сначала сохраняются как enrichment candidates и только после проверки переносятся в `configs/entity_scope.csv`.

Основное зерно модели — `lot`.

Нормализация делает следующее:

- связывает юрлица между источниками;
- приводит процедуры к единому набору полей;
- удаляет дубли по ключу `source_system + procedure_number + lot_number`;
- исключает asset-sale, bankruptcy и VIP sale/disposal процедуры AST;
- добавляет категорию закупки;
- извлекает unit-price строки из SberB2B;
- маскирует ПДн в document text preview;
- присоединяет внешние макрофакторы на месячном уровне.

## Быстрый старт

1. Установить зависимости:

```bash
python -m pip install -e .
```

2. Запустить полный пайплайн:

```bash
$env:PYTHONPATH = "src"
python -m purchase_analysis.cli run-all
```

3. Пересобрать ноутбук:

```bash
$env:PYTHONPATH = "src"
python scripts/build_notebook.py
```

4. Прогнать тесты:

```bash
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Какие артефакты создаются

Основные таблицы:

- `data/curated/entity_coverage.csv`
- `data/curated/entity_source_links.csv`
- `data/curated/source_assessment.csv`
- `data/curated/procurement_lots.csv`
- `data/curated/procurement_items.csv`
- `data/curated/document_links.csv`
- `data/curated/document_texts.csv`
- `data/curated/procurement_participants.csv`
- `data/curated/etp_integration_probe.csv`
- `data/curated/duplicate_stats.csv`
- `data/curated/external_factors_daily.csv`

Аналитические витрины:

- `data/curated/mart_monthly_activity.csv`
- `data/curated/mart_yearly_summary.csv`
- `data/curated/mart_category_mix.csv`
- `data/curated/mart_category_yoy.csv`
- `data/curated/mart_anomalies.csv`
- `data/curated/mart_monthly_macro_join.csv`
- `data/curated/mart_macro_diagnostics.csv`
- `data/curated/mart_unit_price_benchmarks.csv`

Отчёты:

- `data/reports/quality_summary.json`
- `data/reports/improvement_report.md`
- `data/reports/llm_prompt_pack.md`
- `data/reports/llm_summary.md`
- `output/data_discovery/final_data_expansion_report.md`
- `output/data_discovery/final_data_expansion_kpi.json`

## PostgreSQL-схема

В `db/ddl/001_schema.sql` описаны:

- `core.entity_scope`
- `core.entity_source_link`
- `core.source_assessment`
- `core.procurement_lot`
- `core.procurement_item`
- `core.document_link`
- `core.document_text`
- `core.procurement_participant`
- `core.external_factor_daily`

Полезные SQL-представления и витрины лежат в:

- `db/views/001_core_views.sql`
- `db/marts/001_analytics.sql`

Среди них есть:

- покрытие сущностей;
- связки сущностей между источниками;
- yearly summary;
- monthly activity;
- category mix;
- YoY по направлениям;
- duplicate stats;
- база для макрокорреляции.

## Аналитический фокус

В ноутбуке основной фокус сделан на `Telecom & Devices`.

Почему именно он:

- категория хорошо наблюдается в открытых данных;
- в ней есть и объём, и стоимость;
- предметы закупок легко интерпретировать бизнесово.

Что уже реализовано:

- сравнение `2024 vs 2025`;
- `YoY` по направлениям;
- monthly activity;
- top expensive lots;
- unit-price benchmarks по типовым товарам;
- корреляция с `USD/RUB`, ключевой ставкой и ИПЦ;
- аномалии по ценовым выбросам, unit price и publication bursts.

## Работа с документами и ПДн

Пайплайн собирает ссылки на документы и скачивает ограниченный воспроизводимый набор SberB2B-вложений.

Что реализовано:

- `3982` ссылок на документы;
- `250` документов с извлечённым текстом;
- DOCX разбирается через Word XML;
- PDF разбирается через текстовый слой при наличии `pypdf`;
- unsupported/scan-only документы сохраняются с диагностикой;
- email, телефоны, паспортные и похожие идентификаторы маскируются до записи preview.

Документы не используются как доказательство победителя, если в них нет отдельного подтверждённого источника winner status.

## LLM-автоматизация

Для LLM-слоя генерируется `data/reports/llm_prompt_pack.md`.

Что это даёт:

- быстрый контекст для внешней LLM без ручной сборки таблиц;
- заготовку для narrative-части аналитической записки;
- основу для дальнейшей автоматизации работы с неструктурированными данными и аналитическими выводами.

## Ограничения

- Открытый контур не покрывает всю закупочную активность группы Сбер.
- Часть ЭТП из ТЗ даёт нулевые exact-INN результаты по 2024–2025, либо требует авторизованного browser/network reverse engineering для winner/offer слоя.
- `ЕИС` в текущем периметре полезнее как слой идентификации и контроля покрытия, чем как рабочий источник лотов.
- `winners_total=0`: публичные SberB2B/Roseltorg данные дают участников/продавцов, но не подтверждённых победителей.
- Годовые и макро-витрины используют нормализованную дату публикации; для Roseltorg дата берётся из detail-card fallback, а out-of-range 2026 строки исключаются из core-периметра 2024-2025.
- Макрокорреляции являются исследовательскими и не должны трактоваться как причинные выводы.

## Ключевой инженерный вывод

Сильная сторона решения — не просто рост числа собранных строк, а корректная фильтрация предметного контура:

- повторно исследованы все ЭТП из ТЗ;
- добавлен второй рабочий коммерческий источник;
- исправлен scope юрлиц через entity resolution;
- вычищены дубли;
- отфильтрованы out-of-scope asset-sale процедуры;
- подготовлены PostgreSQL-схема, витрины, ноутбук и LLM-ready отчёт.
