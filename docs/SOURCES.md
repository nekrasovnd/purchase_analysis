# Sources

Матрица всех проверенных источников данных о закупках. Текущий рабочий набор физически очищен: в `output/source_sprints` и `data/raw` оставлены только batch-и из allowlist.

## Clean Dataset

| Источник | Batch | Строк | Роль |
|---|---|---:|---|
| Sberbank-AST | `ast-full-2024-2025-finalcheck` | 2 761 | Основной источник коммерческих закупочных процедур. |
| B2B-Center | `b2b_center_prompt2_full_scope_2026-06-18` | 400 | Дополнительный источник; Playwright + CAPTCHA bypass. |
| EIS | `eis-prompt2-full-scope-2026-06-22` | 3 | Контрольный источник 44-ФЗ/223-ФЗ; удаляются как cross-source duplicates. |

Итог clean merge:

```text
rows_before_cross_source_dedupe = 3164
cross_source_duplicates_dropped = 3
rows_after_cross_source_dedupe  = 3161
```

## Аудит всех источников

| ЭТП | Статус | Метод | Результат |
|---|---|---|---|
| **Sberbank-AST** | ✅ production | REST API `/api/v2/lots` | 2 761 лот, full-scope |
| **B2B-Center** | ✅ production | Playwright + XHR interception | 400 лотов; CAPTCHA bypass работает |
| **ЕИС** | ✅ control | REST API | 3 строки (все дубли AST) |
| **Tektorg** | ❌ audited_empty | SOAP API | 0 результатов — только 44-ФЗ госзакупки, Сбера нет |
| **Roseltorg** | ❌ audited_empty | REST API | 0 результатов по всем 32 ИНН |
| **TenderPro** | ❌ audited_empty | REST API | 8 профилей ПАО Сбербанк найдено, закупочных процедур 0 |
| **LotOnline** | ❌ audited_empty | JSON API | 0 результатов; промышленная площадка |
| **ETP GPB** | ❌ audited_empty | REST `/api/v2/lots` | INN-фильтр возвращает имущественные торги, не закупки |
| **ZakazRF** | ❌ audited_empty | ASP.NET HTML-парсинг | 0 процедур; 3 сущности найдено в реестре, закупок нет |
| **RTS Tender** | ❌ unavailable | HTTP | 503 на всех эндпоинтах; повторить при восстановлении |
| **Fabrikant** | ❌ candidate_blocked | Next.js RSC / Server Action | 4 попытки (RSC get, `fetchOrganizationBySearch`, cookie, text) — требует верификации юрлица |

### Fabrikant — детали блокировки

- **RSC GET**: параметр `?inn=` игнорируется сервером.
- **Server Action `fetchOrganizationBySearch`**: 403 без авторизованной сессии.
- **Cookie forgery**: 403 Forbidden.
- **Текстовый поиск**: возвращает первые 10 из 102 результатов без пагинации API.

Разблокировка требует верификации юрлица на площадке. Детали: `docs/FABRIKANT_PLAN.md`.

## Source Scripts

Актуальные source sprint скрипты лежат в `scripts/*_prompt2_source_sprint_v2.py`.

| Скрипт | Статус | Примечания |
|---|---|---|
| `sberbank_ast_prompt2_source_sprint_v2.py` | production | Clean AST batch в allowlist. |
| `b2b_center_prompt2_source_sprint_v2.py` | production | show=both, role_mode fix, incremental flush, --resume, browser-profile. |
| `eis_prompt2_source_sprint_v2.py` | production/control | 44-ФЗ/223-ФЗ control coverage. |
| `tektorg_prompt2_source_sprint_v2.py` | audited_empty | SOAP API работает, 0 лотов Сбера. |
| `roseltorg_prompt2_source_sprint_v2.py` | audited_empty | API работает, 0 результатов. |
| `tender_pro_prompt2_source_sprint_v2.py` | audited_empty | Профили есть, закупок 0. |
| `lot_online_prompt2_source_sprint_v2.py` | audited_empty | 0 результатов; промышленная площадка. |
| `etpgpb_prompt2_source_sprint_v2.py` | audited_empty | INN-фильтр возвращает имущественные торги. |
| `zakazrf_prompt2_source_sprint_v2.py` | audited_empty | 0 процедур по всем ИНН. |
| `rts_tender_prompt2_source_sprint_v2.py` | unavailable | HTTP 503; повторить при восстановлении. |

## Inclusion Policy

Новый источник попадает в clean dataset только после:

1. Positive probe на 1–2 entity.
2. Full run с отдельным batch name.
3. Проверки `items.csv` на стандартные поля и dedupe.
4. Проверки строгого match по заказчику/организатору/покупателю.
5. Обновления `configs/source_sprints_allowlist.csv` и `configs/source_sprints_manifest.csv`.
6. `python scripts\merge_sprints.py --dry-run` с ожидаемым duplicate report.

## Role Policy

В clean dataset принимаются только закупки, где Сбер/дочка выступает в безопасной роли:

- customer / заказчик
- buyer / покупатель
- organizer / организатор

Совпадение по оператору площадки, поставщику, продавцу, заголовку или свободному тексту **не является** закупкой Сбера.
