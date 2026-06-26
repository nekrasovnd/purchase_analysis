# Runbook

Практические команды для сбора данных, merge, демонстрации и проверок.

## Установка

```powershell
python -m pip install -e .
```

Если запускаешь тесты/скрипты из свежей shell:

```powershell
$env:PYTHONPATH = "src"
```

---

## Демонстрация результатов

### Интерактивный дашборд

```powershell
cd presentation
npm install   # только при первом запуске
npm run dev   # http://localhost:5173
```

Дашборд: 5 вкладок (История → Топ → Макроэк. → ML Аномалии → AI Инсайты), тёмная/светлая тема.

### SQLite база для DB Browser

```powershell
# Собрать базу из merged_sprints.csv:
python export_to_sqlite.py
# -> создаёт purchase_analysis.db

# Открыть в DB Browser for SQLite:
# File -> Open Database -> purchase_analysis.db
# Execute SQL -> открыть demo_queries.sql
```

Готовые VIEW: `v_summary`, `v_top20`, `v_hhi`, `v_hhi_total`, `v_by_entity`, `v_monthly`, `v_anomaly_zero_savings`, `v_large_lots`, `v_entity_scope_stats`.

### Защитная речь

```powershell
cd presentation
python generate_defense_speech.py
# -> Defense_Speech.docx (закрой его в Word перед запуском)
```

`Defense_Speech_FINAL.docx` — готовая копия, если оригинал заблокирован Word.

---

## Проверить scope

```powershell
python -m pytest tests/test_entity_resolution.py -q
```

Ожидаем:
- 32 entity;
- уникальные ИНН;
- `aliases` — валидные JSON-массивы;
- unsafe роли не проходят в core.

---

## Запуск source sprint

Общий паттерн:

```powershell
python scripts\<source>_prompt2_source_sprint_v2.py --batch-name <source>-manual-YYYY-MM-DD --inns 7707083893
```

Перед full-scope запуском сначала делай small positive probe на 1–2 ИНН. Full-scope batch не добавляется в `configs/source_sprints_allowlist.csv`, пока не пройдёт audit. После audit обнови `configs/source_sprints_manifest.csv`.

Примеры:

```powershell
python scripts\sberbank_ast_prompt2_source_sprint_v2.py --batch-name ast-probe-paosber-2024-2025 --inns 7707083893
python scripts\b2b_center_prompt2_source_sprint_v2.py --batch-name b2b-center-probe-sber-service --inn 7736663049 --show all
python scripts\eis_prompt2_source_sprint_v2.py --batch-name eis-probe-paosber --inns 7707083893
```

---

## Merge clean dataset

Default merge использует только `configs/source_sprints_allowlist.csv`.

Dry-run:

```powershell
python scripts\merge_sprints.py --dry-run
```

Ожидаемый результат:

```
rows_before_cross_source_dedupe : 3164
cross_source_duplicates_dropped : 3
rows_after_cross_source_dedupe  : 3161
```

Запись файлов:

```powershell
python scripts\merge_sprints.py
```

Выходы:
- `output/merged_sprints.csv`
- `output/merged_sprints_duplicates.csv`
- `output/merged_sprints_summary.json`

`output/` gitignored. Не используй эти файлы как единственный источник правды без сохранения manifest/summary.

### Merge конкретных batch-ов

```powershell
python scripts\merge_sprints.py --source-sprint ast-full-2024-2025-finalcheck --source-sprint b2b_center_prompt2_full_scope_2026-06-18 --dry-run
```

Batch-и с `probe`, `diag`, `scratch`, `test` в имени блокируются merge-защитой.

---

## Aliases review

Dry-run:

```powershell
python scripts\merge_aliases.py
```

Обычный dry-run должен давать `Alias additions proposed: 0`. Запись только после ручного review:

```powershell
python scripts\merge_aliases.py --apply
```

---

## Тесты

Быстрый набор:

```powershell
python -m pytest tests/test_entity_resolution.py tests/test_source_sprint.py tests/test_merge_sprints.py tests/test_merge_aliases.py tests/test_sberbank_ast.py tests/test_b2b_center.py tests/test_lot_online.py tests/test_zakazrf.py tests/test_tender_pro.py tests/test_tektorg.py tests/test_roseltorg_parsing.py tests/test_eis_payload.py -q
```

Полный набор:

```powershell
python -m pytest -q
```

---

## PostgreSQL и notebook

```powershell
python -m purchase_analysis.cli sync-postgres --dsn "postgresql://postgres:<password>@localhost:5432/purchase_analysis"
python scripts\build_notebook.py
```

Перед `sync-postgres` сначала сформируй актуальный curated snapshot в `output/curated`. Notebook строится от clean source sprint merge в `output/merged_sprints.csv`.

> Для быстрой демонстрации используй SQLite (`purchase_analysis.db`) вместо PostgreSQL — не требует сервера.
