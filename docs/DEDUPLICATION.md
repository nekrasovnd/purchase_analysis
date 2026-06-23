# Deduplication Rules

Документ фиксирует, как считать уникальные закупки и почему текущая статистика не равна сумме всех `items.csv`.

## Уровни dedupe

1. Внутри source sprint batch:
   - основной ключ: `procedure_number + lot_number`;
   - если `lot_number` пустой, нормализуется в `1`;
   - если нет `procedure_number`, fallback только на `detail_url`;
   - реализация: `source_sprint.dedupe_items_frame`.

2. Между source sprint batch-ами:
   - основной ключ: `procedure_number + lot_number`, без `source_system`;
   - первый batch в allowlist получает приоритет;
   - все группы дублей пишутся в duplicate report;
   - реализация: `scripts/merge_sprints.py`.

3. В аналитических curated таблицах:
   - старый PostgreSQL loader использует `source_system + procedure_number + lot_number` для lot lookup;
   - это не отменяет cross-source dedupe для чистой source sprint статистики.

## Текущая чистая статистика

Allowlist берётся из `configs/source_sprints_allowlist.csv`; полный manifest известных batch-ов лежит в `configs/source_sprints_manifest.csv`.

- `ast-full-2024-2025-finalcheck`: 2761;
- `b2b_center_prompt2_full_scope_2026-06-18`: 400;
- `eis-prompt2-full-scope-2026-06-22`: 3.

Dry-run merge:

```text
rows_before_cross_source_dedupe = 3164
within_batch_duplicates = 0
cross_source_duplicates_dropped = 3
rows_after_cross_source_dedupe = 3161
```

Это и есть актуальная чистая оценка по AST + B2B + EIS.

## Почему всё равно нужен allowlist

После финальной уборки в `output/source_sprints` оставлены только clean batch-и. Allowlist всё равно остаётся обязательным контрактом: новый экспериментальный batch не должен попасть в статистику просто потому, что появился в директории.

Старый подход `merge all directories` был удалён из рабочего процесса. `scripts/merge_sprints.py` по умолчанию читает только `configs/source_sprints_allowlist.csv`; `--all` оставлен только для диагностики.

## Output schema

`items.csv` должен иметь стандартные поля в начале:

```text
source_system, platform_section, entity_name, customer_query,
procedure_number, lot_number, subject, customer_name, customer_inn,
region, status, tender_type, price_rub, deadline_at, detail_url,
tags, published_at, application_deadline, method_name, currency,
organizer_name, organizer_inn
```

Дополнительные source-specific поля разрешены после стандартных колонок.

## Проверка

```powershell
python -m pytest tests/test_source_sprint.py tests/test_merge_sprints.py -q
python scripts\merge_sprints.py --dry-run
```
