# AGENTS.md

Рабочая памятка для ИИ-агентов и человека, которые входят в проект анализа закупок Сбера.

## Читать первым

1. `README.md` - короткий обзор задачи, текущая чистая статистика и быстрые команды.
2. `docs/RUNBOOK.md` - как запускать source sprint, merge и проверки.
3. `docs/ENTITY_SCOPE.md` - правила `configs/entity_scope.csv`.
4. `docs/DEDUPLICATION.md` - как считать уникальные закупки и почему нельзя запускать старый merge вслепую.
5. `docs/CLEANUP_NOTES.md` - что было удалено и какие clean batch-и остались.

## Главные запреты

- Не добавляй новый source sprint в clean merge без audit и обновления allowlist/manifest.
- Не возвращай `scratch`, `scripts/legacy`, probe/diag batch-и, pycache, browser profiles или generated snapshots в рабочее дерево.
- Не делай `git reset`, `git checkout --` и не откатывай чужие изменения.
- Не stage/commit без отдельной команды.
- Не записывай в `configs/entity_scope.csv` из enrichment-скриптов. `scripts/merge_aliases.py` по умолчанию dry-run и не использует `candidate_name`; запись только через `--apply` после review.
- Не считай закупкой Сбера совпадение, где Сбербанк-АСТ является только оператором/площадкой. В core идут только безопасные роли заказчика/организатора/покупателя.

## Текущий чистый набор

Allowlist лежит в `configs/source_sprints_allowlist.csv`; полная карта batch-ов лежит в `configs/source_sprints_manifest.csv`.

По состоянию после аудита:

- Sberbank-AST: `ast-full-2024-2025-finalcheck`, 2761 уникальный лот.
- B2B-Center: `b2b_center_prompt2_full_scope_2026-06-18`, 400 строк до cross-source dedupe.
- EIS: `eis-prompt2-full-scope-2026-06-22`, 3 контрольные строки.
- Merge AST + B2B + EIS: 3164 строк до cross-source dedupe, 3 дубля удаляются, итог 3161 уникальная закупка.

Команда проверки:

```powershell
python scripts\merge_sprints.py --dry-run
```

## Рабочий код

- Общие правила source sprint: `src/purchase_analysis/source_sprint.py`.
- Entity resolution и scope loader: `src/purchase_analysis/entity_resolution.py`.
- Клиенты источников: `src/purchase_analysis/clients/`.
- Актуальные source sprint скрипты: `scripts/*_prompt2_source_sprint_v2.py`.
- Локальные probe/diag/scratch/legacy артефакты физически удалены; если нужен эксперимент, используй временный каталог и не добавляй его в репозиторий.

## Проверки перед финалом

Минимальный быстрый набор:

```powershell
python -m pytest tests/test_entity_resolution.py tests/test_source_sprint.py tests/test_merge_sprints.py tests/test_merge_aliases.py tests/test_sberbank_ast.py tests/test_b2b_center.py tests/test_lot_online.py tests/test_zakazrf.py tests/test_tender_pro.py tests/test_tektorg.py tests/test_roseltorg_parsing.py tests/test_eis_payload.py -q
```

Если меняешь PostgreSQL loader, pipeline или notebook builder, добавь соответствующие тесты из `tests/`.
