# Sources

Текущий рабочий набор физически очищен: в `output/source_sprints` и `data/raw` оставлены только batch-и, которые участвуют в чистой статистике.

## Clean Dataset

| Source | Batch | Rows | Role |
|---|---|---:|---|
| Sberbank-AST | `ast-full-2024-2025-finalcheck` | 2761 | Основной источник коммерческих закупочных процедур. |
| B2B-Center | `b2b_center_prompt2_full_scope_2026-06-18` | 400 | Дополнительный источник процедур и detail enrichment. |
| EIS | `eis-prompt2-full-scope-2026-06-22` | 3 | Контрольный источник по 44-ФЗ/223-ФЗ; текущие 3 строки удаляются как cross-source duplicates. |

Итог clean merge:

```text
rows_before_cross_source_dedupe = 3164
cross_source_duplicates_dropped = 3
rows_after_cross_source_dedupe = 3161
```

## Source Scripts

Актуальные source sprint скрипты лежат в `scripts/*_prompt2_source_sprint_v2.py`.

| Script | Status | Notes |
|---|---|---|
| `sberbank_ast_prompt2_source_sprint_v2.py` | production | Clean AST batch уже собран и включён в allowlist. |
| `b2b_center_prompt2_source_sprint_v2.py` | production | Clean B2B batch в allowlist. Скрипт обновлён 2026-06-24: show=both, role_mode fix, incremental flush, --resume, browser-profile. |
| `eis_prompt2_source_sprint_v2.py` | production/control | Используется для 44-ФЗ/223-ФЗ control coverage. |
| `tektorg_prompt2_source_sprint_v2.py` | audited_empty | Аудит 2026-06-24: SOAP API работает, но все 32 entity возвращают FAULT «Customers not found by INN». Источник — только 44-ФЗ госзакупки, Сбера нет. |
| `roseltorg_prompt2_source_sprint_v2.py` | audited_empty | Аудит 2026-06-24: API работает, 0 результатов по всем ИНН. Источник — 44-ФЗ/223-ФЗ. |
| `tender_pro_prompt2_source_sprint_v2.py` | audited_empty | Аудит 2026-06-24: профили найдены (8 для ПАО Сбербанк), но закупочных процедур 0. |
| `lot_online_prompt2_source_sprint_v2.py` | audited_empty | Аудит 2026-06-24: JSON API работает, 0 результатов по customer_title=Сбербанк. Промышленная площадка. |
| `etpgpb_prompt2_source_sprint_v2.py` | available | Код сохранён; batch не включается без exact role/identifier audit. |
| `zakazrf_prompt2_source_sprint_v2.py` | available | Код сохранён; batch не включается без нового audit. |
| `rts_tender_prompt2_source_sprint_v2.py` | available | Код сохранён; batch не включается без нового audit. |
| *(нет скрипта)* `fabrikant` | candidate | Next.js App Router; INN-фильтр не раскопан. См. `docs/FABRIKANT_PLAN.md`. |

## Inclusion Policy

Новый источник попадает в clean dataset только после:

1. Positive probe на 1-2 entity.
2. Full run с отдельным batch name.
3. Проверки `items.csv` на стандартные поля и dedupe.
4. Проверки строгого match по заказчику/организатору/покупателю.
5. Обновления `configs/source_sprints_allowlist.csv` и `configs/source_sprints_manifest.csv`.
6. `python scripts\merge_sprints.py --dry-run` с ожидаемым duplicate report.

## Role Policy

В clean dataset принимаются только закупки, где Сбер/дочка выступает в безопасной роли:

- customer;
- buyer;
- organizer;
- заказчик;
- покупатель;
- организатор.

Совпадение по оператору площадки, поставщику, продавцу, заголовку или свободному тексту не является закупкой Сбера.
