# Project Map

Карта репозитория для быстрых входов в проект.

## Корень

- `README.md` - обзор проекта, текущая чистая статистика, быстрые команды.
- `INDEX.md` - короткий входной индекс в корне.
- `AGENTS.md` - operational-памятка для следующих ИИ-агентов.
- `Тестовое задание.txt` - исходная постановка: сбор, очистка, PostgreSQL, аналитика, визуализация.
- `pyproject.toml` - Python package `purchase-analysis`, зависимости и entry point `purchase-analysis`.
- `.gitignore` - runtime/cache/output исключения.

## Код

- `src/purchase_analysis/entity_resolution.py` - загрузка `entity_scope.csv`, нормализация названий/ИНН/ОГРН/КПП, строгий match decision.
- `src/purchase_analysis/source_sprint.py` - единые даты 2024-2025, стандартные поля `items.csv`, dedupe, allowlist source sprint batch-ов.
- `src/purchase_analysis/clients/` - низкоуровневые клиенты и парсеры HTML/XML/JSON для источников.
- `src/purchase_analysis/pipeline.py` - ETL pipeline для curated/postgres сценариев.
- `src/purchase_analysis/postgres_loader.py` - загрузка curated CSV в PostgreSQL.
- `src/purchase_analysis/documents.py` - извлечение текста из документов.

## Скрипты

- `scripts/*_prompt2_source_sprint_v2.py` - текущие source sprint скрипты.
- `scripts/merge_sprints.py` - безопасный merge только allowlisted batch-ов, с cross-source dedupe.
- `scripts/merge_aliases.py` - review helper для JSON `aliases`; dry-run по умолчанию, не default pipeline.
- Legacy/scratch/probe скрипты удалены из рабочего дерева.

## Конфиги

- `configs/entity_scope.csv` - 32 юрлица группы Сбер/дочки; `aliases` должен быть JSON-массивом.
- `configs/source_sprints_allowlist.csv` - единственный default allowlist batch-ов для чистого merge.
- `configs/source_sprints_manifest.csv` - карта clean batch-ов: статус, rows, raw-связка, include flag.

## Данные

- `output/source_sprints/` - только clean batch-и AST/B2B/EIS из allowlist.
- `output/merged_sprints*.csv|json` - текущий clean merge и duplicate report.
- `output/curated/` - generated curated CSV snapshots, если запускается полный ETL pipeline.
- `output/reports/` - generated quality/LLM reports полного ETL pipeline.
- `data/raw/` - только raw evidence для clean batch-ов AST/B2B/EIS.
- `notebooks/` - Jupyter notebook для аналитического отчёта.

## База и аналитика

- `db/ddl/` - схема PostgreSQL.
- `db/views/` - core views.
- `db/marts/` - аналитические mart views.
- `db/queries/` - ручные SQL-запросы для исследования.

## Тесты

- `tests/test_entity_resolution.py` - scope, aliases, match rules.
- `tests/test_source_sprint.py` - output schema и локальный dedupe.
- `tests/test_merge_sprints.py` - allowlist и cross-source dedupe.
- `tests/test_merge_aliases.py` - безопасное обновление aliases.
- `tests/test_*source*.py` и `tests/test_*client*.py` - парсинг ключевых источников.
