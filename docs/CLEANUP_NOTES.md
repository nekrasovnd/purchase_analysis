# Cleanup Notes

Статус после финальной уборки: рабочее дерево очищено от локального мусора, probe/diag batch-ов, scratch-директорий, legacy-скриптов, package/node кэша, pycache и старых generated snapshots.

## Что осталось в рабочем пути

`output/source_sprints/` содержит только clean batch-и:

| Batch | Источник | Строк |
|---|---|---:|
| `ast-full-2024-2025-finalcheck` | Sberbank-AST | 2 761 |
| `b2b_center_prompt2_full_scope_2026-06-18` | B2B-Center | 400 |
| `eis-prompt2-full-scope-2026-06-22` | EIS | 3 |

`data/raw/` содержит только raw evidence для этих же batch-ов:

```text
data/raw/sberbank_ast/ast-full-2024-2025-finalcheck
data/raw/b2b_center/b2b_center_prompt2_full_scope_2026-06-18
data/raw/eis/eis-prompt2-full-scope-2026-06-22
```

`configs/source_sprints_allowlist.csv` и `configs/source_sprints_manifest.csv` содержат только эти три batch-а.

**Демонстрационные артефакты** (добавлены 2026-06-26):

| Файл | Что |
|---|---|
| `purchase_analysis.db` | SQLite база, генерируется из `export_to_sqlite.py` |
| `demo_queries.sql` | 15 SQL-запросов для DB Browser |
| `export_to_sqlite.py` | Скрипт экспорта CSV → SQLite |
| `presentation/Defense_Speech_FINAL.docx` | Готовая защитная речь |
| `presentation/generate_defense_speech.py` | Скрипт генерации речи |

## Что удалено из рабочего дерева

- `scratch/`
- `.agents/`
- `.local/`, `.playwright-cli/`, `.pytest_cache/`
- `scripts/legacy/`
- `scripts/__pycache__/`, `src/purchase_analysis.egg-info/`
- старые root debug/probe файлы (`iframe_debug_*.html`, `rts_tender_scout*.py`, `etpgpb_test.py`, `output.log`, временные картинки/pdf/html)
- старые docs archive/hand-off файлы
- stale `data/curated`, `data/reports`, `data/interim`, `data/quality`
- все non-clean `output/source_sprints/*`
- все non-clean `data/raw/*/*`

## Как не вернуть мусор

- Не запускай `merge_sprints.py --all` для финальной статистики.
- Новый source sprint сначала запускай с отдельным batch name, проверяй, затем добавляй в allowlist/manifest только после audit.
- Browser profiles и temporary scraping state не хранить в репозитории.
- Если нужен эксперимент, используй внешний временный каталог или сразу удали после проверки.
- `purchase_analysis.db` — регенерируется командой `python export_to_sqlite.py`. Не редактировать вручную.

## Артефакты сессии 2026-06-24 (не в allowlist)

В ходе аудита источников и переаудита B2B-Center появились временные артефакты:

| Путь | Статус | Что делать |
|---|---|---|
| `output/source_sprints/b2b-center-both-2026-06-24/` | Подтверждающий прогон (400 строк = старый batch) | Можно удалить; в allowlist не добавлять |
| `data/raw/b2b_center/b2b-center-both-2026-06-24/` | Raw HTML для того же прогона | Можно удалить вместе с output |
| `.local/b2b_profile/` | Playwright браузерный профиль для B2B-Center | Хранить локально; **не коммитить**; переиспользовать при следующем B2B-Center прогоне |

Каноническая чистая статистика: **3 161 уникальный лот** (AST 2761 + B2B 400, минус 3 cross-source дубля), бюджет **30,5 млрд ₽**.
