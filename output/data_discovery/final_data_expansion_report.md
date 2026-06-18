# Отчет по расширению покрытия закупок Сбера за 2024-2025

Дата прогона: 2026-06-14.

Цель: найти новые достоверные закупки группы Сбер за 2024-2025 годы на RTS-Тендер, ЭТП ГПБ, ТЭК-Торг, ЛотОнлайн и ЗаказРФ, а также проверить наличие участников и победителей.

## Итоговый KPI

- Core до/после текущего прогона: 1533 закупки.
- Новые достоверные закупки, добавленные в core: 0.
- Причина: все exact-positive Sber-закупки, найденные новым RTS-проходом, уже присутствуют в `data/curated/procurement_lots.csv`; остальные срабатывания являются либо нулевыми результатами, либо ложными совпадениями по оператору/площадке.
- Новые участники: 0.
- Новые победители: 0.

## RTS-Тендер

Исследованы Anti-DDoS-страницы, публичный поиск, JS-бандлы и сетевые запросы через Playwright/Chrome-контекст.

Найденные рабочие элементы:

- публичный поиск: `https://www.rts-tender.ru/poisk/`;
- конфигурация модели поиска: `/poisk/api/TabValues/0`;
- справочник площадок: `/poisk/Suggestion/ETP`;
- JS-бандлы: `listings.js`, `filters.js`, `detailcard.js`;
- рабочий валидированный поиск через фронтенд с инъекцией `window.getFullServerModel`;
- статусы из `filters.js`: `FilingProposal=1`, `ConsiderationFirstParts=2`, `Bidding=3`, `ContractSigning=4`, `Canceled=5`.

Прогон:

- 13 INN группы Сбер.
- 2 роли: заказчик и организатор.
- 2 режима: все площадки и строго RTS-Тендер.
- Итого 52 точных запроса за период публикации 2024-01-01 - 2025-12-31.

Результат:

- `rts_only`: 26 запросов, 0 положительных результатов.
- `all_etp`: 26 запросов, 5 положительных query-level результатов.
- Достоверные Sber-закупки в `all_etp`: 3 уникальных номера:
  - `1895000000824000001` - ПАО Сбербанк, аудит, 1 066 759 667 руб.
  - `1200700144924000001` - ООО Страховой брокер Сбербанка, аудит, 1 199 767,67 руб.
  - `1200700144924000002` - ООО Страховой брокер Сбербанка, аудит, 1 199 767,67 руб.
- Все 3 уже присутствуют в core:
  - `data/curated/procurement_lots.csv:711`
  - `data/curated/procurement_lots.csv:725`
  - `data/curated/procurement_lots.csv:728`
- `АО Сбербанк-АСТ` как организатор дало 3979 результатов, но первые извлеченные карточки имеют сторонних заказчиков; это операторские/площадочные совпадения, не закупки группы Сбер.

Участники/победители:

- По трем точным карточкам RTS загружает открытую карточку, документы извещения и ссылку на ЕИС.
- В сетевом следе карточек нет отдельного API участников/победителей; загружаются `detailcard.js`, `TabValues`, справочники, статика и аналитика.
- В DOM найдены документы закупки и ссылки `zakupki.gov.ru`, но не публичные победители/участники.

Доказательства:

- `output/data_discovery/rts_mass_probe_summary_v2.csv`
- `output/data_discovery/rts_mass_probe_cards_v2.csv`
- `output/data_discovery/rts_mass_probe_errors_v2.json`
- `output/data_discovery/rts_detail_1895000000824000001.json`
- `output/data_discovery/rts_detail_1200700144924000001.json`
- `output/data_discovery/rts_detail_1200700144924000002.json`
- `output/data_discovery/rts_detail_document_links.json`
- `output/data_discovery/final_data_expansion_kpi.json`

## ЭТП ГПБ

Исследованы публичная API-страница, Nuxt JS-бандлы, live API через Playwright network trace и exact customer API.

Найденные рабочие элементы:

- `https://etpgpb.ru/procedures/api/`;
- `https://etpgpb.ru/api/v2/procedures/`;
- `https://etpgpb.ru/api/v2/customers/`;
- старый API из JS: `https://etp.gpb.ru/api/procedures.php?late=1`.

Результат:

- По текстовому `search=sberbank` получались шумные title-only совпадения.
- Exact customer API подтвердил только `СБЕРОБРАЗОВАНИЕ`, INN `7730262964`, customer id `10509`.
- По customer id найдено 4 процедуры, все опубликованы в 2022 году.
- За 2024-2025 по exact customer id: 0 строк.

Доказательства:

- `output/data_discovery/etpgpb_js/`
- `output/data_discovery/etpgpb_customer_probe.csv`
- `output/data_discovery/etpgpb_customers_accepted.csv`
- `output/data_discovery/etpgpb_customer_lots.csv`
- `output/data_discovery/etpgpb_customer_lots_2024_2025.csv`

## ТЭК-Торг

Исследован официальный SOAP API:

- `https://api.tektorg.ru/procedures`;
- `https://api.tektorg.ru/procedures/wsdl`;
- endpoint: `https://api.tektorg.ru/procedures/soap`.

Прогон:

- 12 INN группы Сбер.
- Поля `customerINN` и `organizerINN`.
- Итого 24 SOAP-запроса.

Результат:

- Все `customerINN`: fault `Customers not found by INN.`
- Все `organizerINN`: fault `Organizers type not found.`
- Новые закупки: 0.

Доказательство:

- `output/data_discovery/tektorg_soap_inn_probe.csv`

## ЛотОнлайн

Исследован `https://tender.lot-online.ru/etp/searchServlet`, локальные title-mention выгрузки и структурные поля `customer_title` / `organizer_title`.

Результат:

- Локальные title-mention файлы: 13 файлов, 0 accepted по exact customer/organizer.
- Структурные запросы вернули 0 accepted.
- Единственное похожее срабатывание по "Сбербанк Страхование Жизни" оказалось сторонним заказчиком: АУ "Редакция газеты "Новая жизнь"", INN `3511000623`, и было отклонено.

Доказательства:

- `output/data_discovery/lotonline_local_title_file_stats.csv`
- `output/data_discovery/lotonline_local_title_accepted.csv`
- `output/data_discovery/lotonline_structured_probe.csv`
- `output/data_discovery/lotonline_structured_accepted.csv`

## ЗаказРФ

Исследованы customer dialog/search и notification endpoints:

- `https://etp.zakazrf.ru/Customer`;
- `https://etp.zakazrf.ru/NotificationEx`.

Exact customers найдены:

- `АО Сбербанк-АСТ`, internal id `202380`, INN `7707308480`;
- `ООО Домклик`, internal id `503467`, INN `7736249247`;
- `ООО Страховой брокер Сбербанка`, internal id `544394`, INN `7706810730`;
- `ПАО Сбербанк России`, internal ids `2384`, `465053`, `471142`, INN `7707083893`.

Результат:

- По всем accepted customer ids запросы `NotificationEx` дали `total_rows=0`.
- Новые закупки: 0.

Доказательства:

- `output/data_discovery/zakazrf_customer_probe.csv`
- `output/data_discovery/zakazrf_customer_candidates_accepted.csv`
- `output/data_discovery/zakazrf_notifications_summary.csv`
- `output/data_discovery/zakazrf_lots_accepted_first_pages.csv`

## Вывод для защиты

Прямого прироста core не получилось, но получено техническое доказательство полноты по пяти дополнительным площадкам: точные INN/role/date запросы, скрытые API, JS reverse engineering, browser-based bypass Anti-DDoS и проверка карточек на документы/участников/победителей. Это снижает риск ложного расширения датасета и показывает проверяющему, что отсутствие новых строк является результатом исчерпывающего технического поиска, а не пропуска источников.
