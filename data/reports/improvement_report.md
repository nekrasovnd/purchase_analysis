# Отчет об инженерной доработке проекта

Дата финального прогона: `2026-06-14`.

Этот отчет фиксирует не аудит, а фактическое усиление проекта как незавершенного исследования закупок группы Сбер. Главный результат итерации - не механический рост количества строк, а рост количества достоверных закупок, расширение периметра источников, извлечение товаров/документов/участников и документирование технических пределов открытого контура.

## Краткий итог

Финальные метрики из `data/reports/quality_summary.json`:

| Метрика | Значение |
|---|---:|
| Юрлиц в scope | 24 |
| Юрлиц с фактическими lot-строками | 13 |
| Core-лотов после дедупликации | 1533 |
| Удалено дублей | 65 |
| Sberbank-AST core | 940 |
| Roseltorg core | 593 |
| Лотов с раскрытой ценой | 382 |
| Товарных строк | 3308 |
| Товарных строк с unit price | 2310 |
| Ссылок на документы | 3982 |
| Документов с извлеченным текстом | 250 |
| Символов текста документов | 4328100 |
| Строк участников/продавцов | 593 |
| Подтвержденных победителей | 0 |
| Unit-price benchmark rows | 709 |
| Unit-price anomaly flags | 7 |
| Макродней ЦБ | 613 |

По сравнению со старым README-состоянием проекта:

- scope вырос с 9 до 24 юрлиц;
- core-витрина выросла с 927 до 1533 лотов, то есть на 606 строк и примерно на 65.4%;
- появились участники, документы, тексты документов, unit-price строки, hidden API probes, macro diagnostics и LLM-ready пакет;
- данные стали строже: из Sberbank-AST исключены процедуры продажи/утилизации имущества, которые раньше попадали в закупочный слой.

Дополнительный data-expansion проход `2026-06-14` был сфокусирован только на новых источниках и покрытии. Проверены RTS-Тендер, ЭТП ГПБ, ТЭК-Торг, ЛотОнлайн и ЗаказРФ. KPI прохода: `0` новых core-лотов после exact-INN/role/date проверок и дедупликации. Это зафиксировано как техническое доказательство: RTS дал 3 точных Sber-процедуры в all-ETP режиме, но все они уже были в core; strict `rts_only` дал 0 строк; остальные площадки дали 0 accepted 2024-2025 строк.

## Что удалось получить дополнительно

1. Расширенный периметр группы Сбер

`configs/entity_scope.csv` содержит 24 сущности и бренда экосистемы. Для части компаний подтверждены ИНН и внешние ключи через ЕИС/Sberbank-AST, для части сохранен честный candidate-expanded статус без искусственного присвоения ИНН.

2. Достоверный core-слой закупок

Итоговый `procurement_lots.csv` содержит 1533 строки:

- 940 из Sberbank-AST;
- 593 из Roseltorg.

Sberbank-AST как единый реестр включает не только закупки, но и продажи имущества. В предыдущем расширенном прогоне было 2933 AST-строки, но значительная часть относилась к формулировкам вроде "простая продажа", "процедура продажи б.у. оборудования", "реализация/утилизация имущества". Новый фильтр исключает эти процедуры, но сохраняет реальные закупки с потенциально опасными словами, например "измельчитель отходов", "реализация тура", "предпродажная подготовка".

3. Товары и unit price из скрытого SberB2B API

Найден и встроен endpoint:

```text
/request/api/{condition_id}/get-from-description-goods-items/customer
```

Он дает OKPD2, наименование, количество, единицу измерения, цену за единицу и сумму строки. Это переводит анализ с уровня заголовков лотов на уровень конкретных товаров и услуг.

Финальный результат:

- 3308 товарных строк;
- 2310 строк с unit price;
- 709 benchmark rows;
- 7 unit-price anomaly flags.

4. Документы и текст документов

Собраны:

- 3982 ссылки на документы;
- 250 скачанных и разобранных документов;
- 4.33 млн символов извлеченного текста.

DOCX разбирается через Word XML, PDF - через текстовый слой при наличии `pypdf`. В preview маскируются email, телефоны, паспортные и похожие идентификаторы. Unsupported/scan-only файлы сохраняются с диагностикой, а не теряются.

5. Участники/продавцы

Из Roseltorg detail JSON-LD извлечено 593 строки `seller_from_public_schema`. Они вынесены в `procurement_participants.csv` с evidence source.

Важно: эти seller-строки не подменяют победителей. Победитель фиксируется только при наличии подтвержденного public winner source. Поэтому `winners_total=0` является честным результатом исследования, а не недоработкой в учете.

6. Внешние факторы

Через данные Банка России добавлены:

- USD/RUB;
- ключевая ставка;
- ИПЦ год-к-году;
- monthly macro join;
- macro diagnostics с Pearson r и приближенным p-value.

На текущем покрытии заметный исследовательский сигнал: `lots_count vs avg_usd_rub`, `r = -0.5025`, `p ~= 0.0113`. Интерпретация ограничена открытым покрытием и не является причинным выводом.

## Какие источники были исследованы

| Источник | Статус | Решение |
|---|---|---|
| ЕИС | operational | Используется для entity resolution и контрольного 223-ФЗ покрытия |
| Roseltorg | operational | Используется в core: 593 лота, документы, seller JSON-LD |
| Sberbank-AST | operational | Используется в core: 940 закупочных процедур после фильтра out-of-scope |
| SberB2B public cards | operational enrichment | Товары, unit price, документы, текст документов, API probes |
| ZakazRF | operational probe-only | Hidden form submit воспроизведен, exact-INN уведомления дают 0 строк |
| Lot-Online | operational probe-only | `searchServlet` воспроизведен, exact customer/organizer probes дают 0 строк |
| RTS-Tender | operational probe-only | Anti-DDoS пройден через Chrome/Playwright; strict RTS-only exact probes дали 0, all-ETP нашел только 3 уже учтенных AST-дубля |
| Tektorg | research_only exact-probe-zero | Официальный SOAP API/WSDL проверен по `customerINN` и `organizerINN`; accepted строк 0 |
| ETP GPB | research_only exact-probe-zero | Через Nuxt/Playwright найдены `api/v2/procedures` и `api/v2/customers`; exact 2024-2025 строк 0 |
| Банк России | operational | Макрофакторы для аналитики |

## Что проверено reverse engineering

SberB2B:

- открытая карточка `request/supplier/preview/<uuid>` редиректит на `needs/<need_id>`;
- public HTML содержит embedded `need-for-public-page`;
- goods API по `condition_id` возвращает JSON HTTP 200;
- browser inspection завершенной карточки не показал `window.Routing`;
- public page не делает offer/supplier XHR при загрузке;
- JS bundle содержит route names вроде `need_offer_list`, `need_selected_supplier_list`, `commerce_need_procedure_results_offers_list_api`, `competitive_analysis_list_api`, но public FOS route export не раскрыт;
- candidate offer/supplier endpoints по `condition_id`, `need_id` и номеру дали 404/403/login redirects;
- поэтому winner/offer данные не извлекаются без закрытого доступа.

ZakazRF:

- воспроизведены `_orm_PageID`, hidden dialog state и customer selector;
- exact-INN customer lookup работает;
- `NotificationEx?Customer=<id>` дает 0 публичных уведомлений для найденных customer ids.

Lot-Online:

- найден скрытый `https://tender.lot-online.ru/etp/searchServlet`;
- воспроизведены exact customer, organizer и title search payloads;
- exact INN probes дают 0 строк;
- title search дает много упоминаний, но они слишком шумные для core attribution.

RTS-Tender:

- Anti-DDoS пройден в persistent Chrome/Playwright context;
- найдены `/poisk/api/TabValues/0`, `/poisk/Suggestion/ETP`, JS-бандлы `listings.js`, `filters.js`, `detailcard.js`;
- прямой API-запрос без frontend token возвращал 400, поэтому поиск воспроизведен через frontend-validated flow;
- выполнено 52 exact запроса: 13 INN, роли customer/organizer, режимы all-ETP и strict RTS-only, публикация 2024-2025;
- strict RTS-only дал 0 строк;
- all-ETP дал 3 точные Sber-процедуры, все уже есть в `procurement_lots.csv`;
- срабатывания по `АО Сбербанк-АСТ` как организатору отвергнуты как операторские процедуры сторонних заказчиков.

ETP GPB:

- исследованы Nuxt-бандлы и browser network trace;
- найдены `https://etpgpb.ru/api/v2/procedures/` и `https://etpgpb.ru/api/v2/customers/`;
- exact customer API подтвердил только `СберОбразование`, но найденные процедуры относятся к 2022 году;
- за 2024-2025 exact строк не найдено.

Tektorg:

- воспроизведен официальный SOAP endpoint `https://api.tektorg.ru/procedures/soap`;
- WSDL `https://api.tektorg.ru/procedures/wsdl` содержит фильтры `customerINN` и `organizerINN`;
- 24 exact запроса по Sber-INN дали нулевые SOAP faults, поэтому безопасных строк для core нет.

Playwright/браузер:

- CLI Playwright проверен через `npx.cmd`, так как `npx.ps1` блокируется PowerShell execution policy;
- встроенный браузер использован для проверки SberB2B public page, ресурсов и отсутствия публичного route map.

## Какие гипотезы добавлены

1. Asset-sale contamination в Sberbank-AST

Гипотеза подтвердилась. Единый AST-реестр смешивает закупки и продажи имущества. Без фильтра продажи б.у. оборудования и доходной утилизации искажают price coverage, anomalies и category mix.

2. SberB2B goods API как главный источник типовых товаров

Гипотеза подтвердилась. Hidden API дает unit price и OKPD2, что позволяет строить benchmark не по заголовкам, а по строкам товаров.

3. Победители скрыты за авторизованным контуром

Гипотеза частично подтвердилась технически: JS route names есть, но public route map/XHR/endpoints не раскрываются. Открытые данные дают sellers/participants, но не надежный winner status.

4. Title search на альтернативных ЭТП слишком шумный

Подтверждено для Lot-Online: title_mentions дают строки, но exact customer/organizer probes пустые. В core оставлены только источники с точной атрибуцией.

5. Unit-price outliers лучше защищать как shortlist

Подтверждено: 7 флагов дают практичный список для ручной проверки, но не юридический вывод о завышении.

6. Макрофакторы полезны как exploratory layer

Добавлены USD/RUB, ставка ЦБ и ИПЦ. Сигналы есть, но требуют осторожной интерпретации из-за неполного открытого покрытия.

## Примеры unit-price flags

| Компания | Предмет | Unit price | Медиана | Ratio |
|---|---|---:|---:|---:|
| АО Сбербанк Лизинг | Бытовая техника для ДВРФ | 200000 | 75000 | 2.67 |
| ООО Домклик | Бумага офисная А3 | 724.26 | 362.10 | 2.00 |
| ПАО Сбербанк России | Стол монтажный | 140000 | 70095 | 2.00 |
| ПАО Сбербанк России | Лоток навесной на экран | 55600 | 28925 | 1.92 |
| ПАО Сбербанк России | Комплект блинов Barbel | 22128.07 | 11861.52 | 1.87 |
| ПАО Сбербанк России | Крючок навесной на экран | 2250 | 1220 | 1.84 |
| ООО СберТех | Визитные карточки | 14930 | 8215 | 1.82 |

## Насколько выросло покрытие данных

Относительно старого README-состояния:

- scope: 9 -> 24 юрлица;
- lots: 927 -> 1533;
- duplicates removed: 2 -> 65;
- documents: из metadata-only подхода до 3982 ссылок и 250 текстов;
- participants: с отсутствующего слоя до 593 строк;
- unit-price: с отсутствующего слоя до 2310 строк;
- macro: USD/RUB + key rate дополнены ИПЦ и diagnostics;
- источники: от 3 рабочих источников до 3 core/enrichment источников плюс 2 reproducible probe adapters и 3 исследованных ограничения.

Относительно промежуточного "много строк" прогона:

- AST core: 2933 -> 940;
- уменьшение является улучшением качества, потому что исключены out-of-scope продажи/утилизации имущества;
- Roseltorg, SberB2B goods, документы, тексты, participants и macro layers сохранены.

## Какие новые баллы это может дать на защите

- Data collection: больше источников, больше юрлиц, больше raw evidence, reproducible probes.
- Data engineering: устойчивый ETL, retry/backoff, graceful handling нестабильного ЕИС, UTF-8 BOM CSV, PostgreSQL DDL/views/marts.
- OSINT/reverse engineering: hidden APIs ZakazRF, Lot-Online, SberB2B, анализ JS bundle и browser network.
- Data quality: строгий entity resolution, exact-INN контроль, фильтр AST asset-sale, дедупликация, price sanity.
- Procurement analytics: category mix, YoY, monthly activity, anomalies, unit-price benchmarks.
- Document intelligence: скачивание документов, DOCX/PDF extraction, PII masking, OCR-required diagnostics.
- Participants/winners: участники извлечены, победители не сфабрикованы; техническое доказательство ограничения сохранено.
- Macro analytics: USD/RUB, ставка ЦБ, ИПЦ, correlation diagnostics.
- LLM readiness: `llm_prompt_pack.md` дает компактный контекст для аналитической записки без ручной сборки таблиц.
- Защитная позиция: проект честно показывает, где открытые данные закончились и где нужны закрытые доступы.

## Оставшиеся ограничения

- Полные winner/offer данные SberB2B, вероятно, требуют авторизованного доступа.
- RTS-Tender больше не считается непройденным Anti-DDoS-блокером: публичный поиск воспроизведен через Playwright, но strict RTS-only exact probes дали 0 новых строк.
- Tektorg и ETP GPB исследованы через официальный SOAP/API и browser-side discovery соответственно; ограничение теперь не в доступе к поиску, а в отсутствии exact Sber 2024-2025 строк в открытом контуре.
- OCR для scan-only PDF не развернут на весь корпус, потому что это даст заметные вычислительные затраты и риск PII без отдельного контура.
- Market-price comparison пока построен на внутренних unit-price медианах, а не на закрытых каталогах или коммерческих прайсах.

## Проверка

Выполнено:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

Результат: `21 tests OK`.

Финальный полный прогон:

```powershell
$env:PYTHONPATH='src'; python -m purchase_analysis.cli run-all
```

Результат сохранен в `data/reports/quality_summary.json`, `data/curated/*.csv`, `notebooks/purchase_analysis.ipynb`.
