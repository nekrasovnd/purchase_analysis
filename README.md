# Purchase Analysis: закупки группы Сбер

Проект собирает и нормализует открытые данные о закупках Сбербанка и дочерних юрлиц за 2024-2025 годы. Текущая версия очищена до воспроизводимого source sprint pipeline, строгого entity matching и clean batch-набора без старых probe/diag артефактов.

## Текущий чистый результат

Актуальный merge берёт только batch-и из `configs/source_sprints_allowlist.csv`.

- Sberbank-AST: `ast-full-2024-2025-finalcheck`, 2761 уникальный лот.
- B2B-Center: `b2b_center_prompt2_full_scope_2026-06-18`, 400 строк до cross-source dedupe.
- EIS: `eis-prompt2-full-scope-2026-06-22`, 3 контрольные строки.
- Итого AST + B2B + EIS: 3164 строк до cross-source dedupe, 3 дубля удаляются, 3161 уникальная закупка.

Проверить:

```powershell
python scripts\merge_sprints.py --dry-run
```

## Быстрый вход

1. Прочитать `AGENTS.md`.
2. Прочитать `docs/RUNBOOK.md`.
3. Проверить `configs/entity_scope.csv` и `configs/source_sprints_allowlist.csv`.
4. Не запускать merge по всем директориям `output/source_sprints`.

## Основные директории

- `configs/` - scope юрлиц, allowlist актуальных source sprint batch-ов и полный batch manifest.
- `src/purchase_analysis/` - общий Python package.
- `src/purchase_analysis/source_sprint.py` - единые даты 2024-2025, output schema и dedupe.
- `src/purchase_analysis/entity_resolution.py` - строгий match заказчика/организатора/покупателя.
- `src/purchase_analysis/clients/` - клиенты источников.
- `scripts/*_prompt2_source_sprint_v2.py` - текущие source sprint скрипты.
- `scripts/*_prompt2_source_sprint_v2.py` - поддерживаемые source sprint скрипты.
- `output/source_sprints/` - только три clean batch-а из allowlist.
- `data/raw/` - только raw evidence для этих же clean batch-ов.
- `db/` и `notebooks/` - PostgreSQL schema/query слой и аналитический notebook.

## Документация

- `docs/PROJECT_MAP.md` - карта репозитория.
- `docs/ENTITY_SCOPE.md` - политика юрлиц, ИНН, aliases, search terms.
- `docs/SOURCES.md` - матрица источников.
- `docs/RUNBOOK.md` - команды запуска.
- `docs/DEDUPLICATION.md` - правила dedupe и статистики.
- `docs/CLEANUP_NOTES.md` - что было удалено и что осталось в чистом дереве.

## Установка и тесты

```powershell
python -m pip install -e .
python -m pytest tests/test_entity_resolution.py tests/test_source_sprint.py tests/test_merge_sprints.py tests/test_merge_aliases.py tests/test_sberbank_ast.py tests/test_b2b_center.py tests/test_lot_online.py tests/test_zakazrf.py tests/test_tender_pro.py tests/test_tektorg.py tests/test_roseltorg_parsing.py tests/test_eis_payload.py -q
```

## Важные правила

- `configs/entity_scope.csv` содержит 32 entity; `aliases` строго JSON-массив.
- Закупкой Сбера считается только совпадение по безопасным ролям customer/buyer/organizer.
- Сбербанк-АСТ как оператор/площадка не является закупкой Сбера.
- `scripts/merge_aliases.py` - review helper, dry-run по умолчанию, запись только с `--apply`.
- Старые/probe/diag batch-и физически удалены из рабочего дерева; новые batch-и добавляются в allowlist только после audit.
