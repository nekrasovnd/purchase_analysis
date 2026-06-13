# Отчет об инженерной доработке проекта

Дата финального прогона: 2026-06-14.

## Краткий итог

Проект доработан из базового сбора закупок до воспроизводимого open-data pipeline с несколькими источниками, проверкой качества, enriched SberB2B-данными, участниками, документами, unit-price benchmark и макрофакторами.

Финальные метрики из `data/reports/quality_summary.json`:

- Юрлиц в scope: 24.
- Юрлиц с наблюдаемыми лотами: 14.
- Лотов после дедупликации: 3549.
- Источники core-лотов: Sberbank-AST - 2933, Roseltorg - 616.
- Лотов с раскрытой ценой: 2375, покрытие ценой 66.92%.
- Товарных строк: 5305.
- Строк с unit price из SberB2B goods API: 2232.
- Ссылок на документы: 4108.
- Документов с извлеченным текстом: 150.
- Извлечено текста: 4002092 символа.
- Строк участников/продавцов: 616.
- Подтвержденных победителей: 0, потому что публичный winner/offer endpoint не раскрыт без закрытого доступа.
- Unit-price benchmark rows: 686.
- Unit-price anomaly flags: 7.
- Макродней ЦБ: 613.
- ИПЦ добавлен и используется в macro diagnostics.

## Что было улучшено

1. Расширен список компаний группы Сбер

Scope расширен до 24 юридических лиц и брендов/компаний экосистемы. Для части компаний ИНН подтверждается через ЕИС/AST, для части scope оставлен как candidate-expanded без жесткого присвоения ИНН. Это честнее, чем вручную подставлять непроверенные идентификаторы.

2. Увеличено покрытие источников

Core-слой строится из Sberbank-AST и Roseltorg. ЕИС используется как контрольный слой entity resolution и покрытия 223-ФЗ. ZakazRF и LotOnline оставлены как exact-probe/research-only источники: их запросы воспроизводятся, но ненадежные или пустые результаты не попадают в core.

3. Исправлена критическая ошибка качества ZakazRF

До исправления ZakazRF при пустом ИНН возвращал общий справочник клиентов, и чужие закупки могли попадать в core. Теперь кандидаты фильтруются строго по exact-INN. Результат: `zakazrf_core = 0`, а все ZakazRF проверки остаются в `etp_integration_probe.csv`.

4. Исправлена критическая ошибка качества Roseltorg price parsing

Одна Roseltorg-карточка давала цену порядка `2e24` из-за склейки дублированных числовых фрагментов в HTML. Добавлен money-parser для первого money-like значения и приоритет detail JSON-LD price. Финально max Roseltorg price: 2125525 RUB.

5. Добавлен SberB2B public-card enrichment

Для AST-строк с `sberb2b.ru` реализован разбор публичных карточек `need-for-public-page`, извлечение embedded JSON, condition id, customer data, deadline, total price, документов и товарных строк.

6. Найден и использован скрытый SberB2B goods API

Используется endpoint:

`/request/api/{condition_id}/get-from-description-goods-items/customer`

Он дает OKPD2, наименование, количество, единицу измерения, цену за единицу и сумму строки. Это самый ценный прирост проекта, потому что позволяет анализировать типовые товары, а не только заголовки лотов.

7. Добавлен retry/backoff для SberB2B

SberB2B иногда отдавал transient `502 Bad Gateway`. После ручной проверки URL повторно открывались. В клиент добавлен retry по 429/500/502/503/504. Это вернуло unit-price coverage до 2232 строк и снизило SberB2B enrichment errors до одного реального 404.

8. Добавлены документы, извлечение текста и обезличивание

Скачивается ограниченный набор документов SberB2B. DOCX разбирается напрямую через Word XML, PDF через текстовый слой при наличии `pypdf`. Email, телефоны и похожие идентификаторы маскируются до записи preview в витрину. Один PDF помечен `ocr_required=True`.

9. Добавлены участники/продавцы

Из Roseltorg detail JSON-LD извлекается `offers.seller`. Данные записываются в `procurement_participants.csv` с `evidence_source`. Победители не подменяются продавцами: `winners_total=0`, потому что публичного подтвержденного winner source нет.

10. Добавлен unit-price benchmark и поиск завышенных цен

Построена витрина `mart_unit_price_benchmarks.csv`: benchmark key по OKPD2, единице и нормализованному наименованию, медиана, p75, ratio к медиане, anomaly flag при ratio >= 1.8 и достаточном числе наблюдений.

Финальные флаги включают:

- бытовая техника для АО Сбербанк Лизинг: 200000 RUB против медианы 75000 RUB;
- бумага офисная А3 для ООО Домклик: 724.26 RUB против медианы 362.10 RUB;
- стол монтажный для ПАО Сбербанк России: 140000 RUB против медианы 70095 RUB;
- навесные элементы и спортинвентарь для ПАО Сбербанк России;
- визитные карточки для ООО СберТех.

Это shortlist для ручной проверки, а не автоматическое обвинение.

11. Добавлены макрофакторы

К курсу USD/RUB и ключевой ставке ЦБ добавлен ИПЦ год-к-году. Построена `mart_macro_diagnostics.csv` с Pearson r и приближенным p-value через Fisher z.

Наиболее заметный сигнал: `lots_count vs avg_usd_rub` имеет `r = -0.5665`, `p ~= 0.0032`. Интерпретация ограничена покрытием открытых источников.

12. Обновлены SQL DDL/views/marts

Добавлены поля и представления для:

- SberB2B identifiers;
- unit price;
- document text;
- procurement participants;
- macro inflation;
- unit-price benchmarks.

13. Обновлен notebook

`notebooks/purchase_analysis.ipynb` пересобран через `scripts/build_notebook.py`. В notebook добавлены разделы по документам, участникам, unit-price benchmarks, macro diagnostics и LLM automation.

14. Добавлены тесты

Финальный прогон:

`PYTHONPATH=src python -m unittest discover -s tests`

Результат: 19 tests OK.

## За какие дополнительные баллы это работает

- Больше данных: 3549 core-лотов, 5305 item rows, 4108 документов.
- Несколько источников: AST, Roseltorg, ЕИС, SberB2B, ZakazRF probe, LotOnline probe.
- Глубина reverse engineering: SberB2B embedded Vue JSON и hidden goods API; LotOnline searchServlet probes; ZakazRF hidden form dialog.
- Качество данных: strict ZakazRF exact-INN, Roseltorg price sanity, дедупликация, source assessment.
- Entity resolution: scope расширен до 24, фиксация resolved_inn и coverage per source.
- Участники: 616 seller rows с evidence source.
- Документы: 150 extracted documents, PII masking, OCR-required flag.
- Аналитика типовых товаров: unit-price benchmark и 7 anomaly flags.
- Макроанализ: USD, ключевая ставка, ИПЦ, корреляции и p-value.
- LLM-ready контур: `llm_prompt_pack.md` содержит quality summary, source assessment, anomalies, unit-price flags и document extracts.

## Ограничения, которые нужно честно проговорить на защите

- `winners_total=0`: публичные SberB2B карточки и Roseltorg JSON-LD не дают надежного winner source без авторизации.
- Roseltorg `seller` не равен победителю, поэтому он вынесен как `seller_from_public_schema`.
- Некоторые компании expanded scope не имеют подтвержденного ИНН в открытом резолвинге. Они остаются в coverage/audit, но не форсируются в core.
- LotOnline title search дает возможные упоминания, но слишком шумен для core.
- ZakazRF технически воспроизведен, но в core не включен из-за строгого exact-INN контроля.
- Unit-price anomaly flag является shortlist для эксперта, а не юридическим выводом о завышении.
