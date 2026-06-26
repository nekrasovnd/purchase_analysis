# INDEX.md

Короткий вход в проект. Начни отсюда.

## Читать в начале

- `README.md` — обзор, текущая статистика, ключевые находки.
- `AGENTS.md` — правила работы для ИИ-агентов и человека.
- `Тестовое задание.txt` — исходная постановка.
- `docs/INDEX.md` — полный индекс документации.

## Главные рабочие документы

| Файл | Что внутри |
|---|---|
| `docs/RUNBOOK.md` | Команды сбора, merge, demo |
| `docs/ENTITY_SCOPE.md` | 32 юрлица: ИНН, aliases, политика |
| `docs/SOURCES.md` | Матрица 11 ЭТП: что работает и почему |
| `docs/DEDUPLICATION.md` | Правила dedupe, 3 161 уникальный лот |
| `docs/CLEANUP_NOTES.md` | Что удалено из репозитория |
| `docs/FABRIKANT_PLAN.md` | Разблокировка Fabrikant (blocked) |

## Демонстрация результатов

```powershell
# Дашборд (http://localhost:5173):
cd presentation && npm run dev

# БД для DB Browser for SQLite:
python export_to_sqlite.py
# -> purchase_analysis.db + demo_queries.sql

# Защитная речь (Defense_Speech_FINAL.docx уже готова):
cd presentation && python generate_defense_speech.py
```

## Быстрая проверка данных

```powershell
python scripts\merge_sprints.py --dry-run
python -m pytest tests/test_entity_resolution.py tests/test_source_sprint.py tests/test_merge_sprints.py tests/test_merge_aliases.py -q
```
