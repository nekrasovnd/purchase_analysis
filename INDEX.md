# INDEX.md

Короткий вход в проект.

## Читать в начале

- `README.md` - обзор и текущая чистая статистика.
- `AGENTS.md` - правила работы для следующих ИИ-агентов.
- `Тестовое задание.txt` - исходная постановка.
- `docs/INDEX.md` - полный индекс документации.

## Главные рабочие документы

- `docs/PROJECT_MAP.md` - структура проекта.
- `docs/ENTITY_SCOPE.md` - политика юрлиц и aliases.
- `docs/SOURCES.md` - источники и их статус.
- `docs/RUNBOOK.md` - команды запуска.
- `docs/DEDUPLICATION.md` - правила dedupe и статистики.
- `docs/CLEANUP_NOTES.md` - что удалено и какие clean batch-и остались.

## Быстрая проверка

```powershell
python scripts\merge_sprints.py --dry-run
python -m pytest tests/test_entity_resolution.py tests/test_source_sprint.py tests/test_merge_sprints.py tests/test_merge_aliases.py -q
```
