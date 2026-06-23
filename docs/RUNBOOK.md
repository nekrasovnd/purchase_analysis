# Runbook

Практические команды для сбора, merge и проверок.

## Установка

```powershell
python -m pip install -e .
```

Если запускаешь тесты/скрипты из свежей shell, можно явно задать:

```powershell
$env:PYTHONPATH = "src"
```

## Проверить scope

```powershell
python -m pytest tests/test_entity_resolution.py -q
```

Ожидаем:

- 32 entity;
- уникальные ИНН;
- `aliases` валидные JSON-массивы;
- unsafe роли не проходят в core.

## Запуск source sprint

Общий паттерн:

```powershell
python scripts\<source>_prompt2_source_sprint_v2.py --batch-name <source>-manual-YYYY-MM-DD --inns 7707083893
```

Перед full-scope запуском сначала делай small positive probe на 1-2 ИНН и проверь, что есть реальные лоты и корректный match. Full-scope batch не добавляется в `configs/source_sprints_allowlist.csv`, пока не пройдёт audit. После audit обнови `configs/source_sprints_manifest.csv`: статус, rows, unique lot keys, raw-связку и `include_in_default_merge`.

Примеры:

```powershell
python scripts\sberbank_ast_prompt2_source_sprint_v2.py --batch-name ast-probe-paosber-2024-2025 --inns 7707083893
python scripts\b2b_center_prompt2_source_sprint_v2.py --batch-name b2b-center-probe-sber-service --inn 7736663049 --show all
python scripts\eis_prompt2_source_sprint_v2.py --batch-name eis-probe-paosber --inns 7707083893
```

## Merge clean dataset

Default merge использует только `configs/source_sprints_allowlist.csv`. Полная карта известных batch-ов лежит в `configs/source_sprints_manifest.csv`.

Dry-run:

```powershell
python scripts\merge_sprints.py --dry-run
```

Ожидаемый результат после текущего аудита:

- `rows_before_cross_source_dedupe`: 3164;
- `cross_source_duplicates_dropped`: 3;
- `rows_after_cross_source_dedupe`: 3161.

Запись файлов:

```powershell
python scripts\merge_sprints.py
```

Выходы:

- `output/merged_sprints.csv`;
- `output/merged_sprints_duplicates.csv`;
- `output/merged_sprints_summary.json`.

`output/` gitignored. Не используй эти файлы как единственный источник правды без сохранения manifest/summary.

## Merge конкретных batch-ов

Только явно:

```powershell
python scripts\merge_sprints.py --source-sprint ast-full-2024-2025-finalcheck --source-sprint b2b_center_prompt2_full_scope_2026-06-18 --dry-run
```

Batch-и с `probe`, `diag`, `scratch`, `test` в имени блокируются защитой merge. В чистом рабочем дереве таких batch-ов быть не должно. Если ты временно создал экспериментальный batch для аудита, можно принудительно:

```powershell
python scripts\merge_sprints.py --source-sprint ast-probe-2024-2025-fixed --include-unsafe --dry-run
```

Не используй `--include-unsafe` для финальной статистики и удаляй временный batch после аудита, если он не принят в allowlist.

## Aliases review

Dry-run:

```powershell
python scripts\merge_aliases.py
```

Обычный dry-run должен давать `Alias additions proposed: 0`. Если нужно рассмотреть названия из `candidate_name`, запускай только вручную и только для review:

```powershell
python scripts\merge_aliases.py --include-candidate-name
```

Запись только после ручного review:

```powershell
python scripts\merge_aliases.py --apply
```

Если dry-run предлагает филиалы, отделения, supplier/vendor названия или посторонние организации, не применяй его целиком.

## Тесты

Быстрый набор для текущих контрактов:

```powershell
python -m pytest tests/test_entity_resolution.py tests/test_source_sprint.py tests/test_merge_sprints.py tests/test_merge_aliases.py tests/test_sberbank_ast.py tests/test_b2b_center.py tests/test_lot_online.py tests/test_zakazrf.py tests/test_tender_pro.py tests/test_tektorg.py tests/test_roseltorg_parsing.py tests/test_eis_payload.py -q
```

Полный набор:

```powershell
python -m pytest -q
```

## PostgreSQL и notebook

PostgreSQL schema/query слой и notebook остаются в проекте. Curated CSV snapshots старого прогона удалены из рабочего дерева; новый curated refresh должен быть отдельным воспроизводимым шагом и пишется в `output/curated`. Quality/LLM отчёты полного ETL пишутся в `output/reports`.

```powershell
python -m purchase_analysis.cli sync-postgres --dsn "postgresql://postgres:<password>@localhost:5432/purchase_analysis"
python scripts\build_notebook.py
```

Перед `sync-postgres` сначала сформируй актуальный curated snapshot в `output/curated`. Текущий notebook строится от clean source sprint merge в `output/merged_sprints.csv`.
