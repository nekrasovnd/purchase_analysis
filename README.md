# Purchase Analysis: закупки группы Сбер

Проект собирает, нормализует и анализирует открытые данные о закупках Сбербанка и дочерних юрлиц за 2024–2025 годы. Итог: **3 161 уникальная закупка, 30,5 млрд ₽**, интерактивный дашборд, ML-аномалии, SQLite-база и защитная речь.

## Текущий чистый результат

| Источник | Batch | Лотов | Бюджет |
|---|---|---:|---:|
| Sberbank-AST | `ast-full-2024-2025-finalcheck` | 2 761 | ~30 млрд ₽ |
| B2B-Center | `b2b_center_prompt2_full_scope_2026-06-18` | 400 | ~0.2 млрд ₽ |
| ЕИС | `eis-prompt2-full-scope-2026-06-22` | 3 | — (удалены как дубли) |
| **Итого (clean merge)** | | **3 161** | **30,5 млрд ₽** |

3 cross-source дубля удалены. Merge берёт только allowlist.

```powershell
# Проверить:
python scripts\merge_sprints.py --dry-run
# Собрать SQLite для демонстрации:
python export_to_sqlite.py
# Запустить дашборд:
cd presentation && npm run dev
```

## Ключевые находки

| Аномалия | Значение | Risk |
|---|---|---|
| HHI (концентрация вендоров) | **5 698** — 2.3× выше порога монополии DoJ (2 500) | Критический |
| Мегалот Cloud.ru (ЦОД) | **13,33 млрд ₽**, Z-score = 19,96 | Критический |
| Корреляция ставки ЦБ с бюджетами | r = **+0,546**, лаг 3 мес (CCF) | Высокий |
| Декабрьский «слив» бюджета | **1,116 млрд ₽** — 10× медианного месяца | Высокий |
| Признаки дробления лотов | MinHashLSH = 0,97 по серверным шкафам | Средний |
| 0% экономии, 1 участник | Isolation Forest score = 0,91 | Средний |

## Быстрый вход

1. Прочитать `AGENTS.md` — запреты и правила.
2. Прочитать `docs/RUNBOOK.md` — команды.
3. Проверить `configs/entity_scope.csv` (32 юрлица) и `configs/source_sprints_allowlist.csv`.
4. Не добавлять новый batch в merge без audit.

## Структура репозитория

```
configs/                 # entity_scope.csv, allowlist, manifest
src/purchase_analysis/   # Python package
  source_sprint.py       # единые даты, schema, dedupe
  entity_resolution.py   # Jaro-Winkler match
  clients/               # клиент для каждой ЭТП
scripts/                 # *_prompt2_source_sprint_v2.py, merge_sprints.py
output/                  # merged_sprints.csv (gitignored)
presentation/            # React 19 дашборд (Vite + Recharts)
  src/data.json          # источник данных для фронтенда
  generate_defense_speech.py  # генерирует Defense_Speech.docx
  Defense_Speech_FINAL.docx   # готовая речь по вкладкам дашборда
export_to_sqlite.py      # экспорт в purchase_analysis.db (для DB Browser)
purchase_analysis.db     # SQLite база с 9 VIEW для демонстрации
demo_queries.sql         # 15 готовых SQL-запросов
db/                      # PostgreSQL schema/queries
docs/                    # документация
```

## Дашборд (presentation/)

React 19 + Vite + Recharts + Framer Motion. Пять вкладок:

1. **История** — 6 шагов от 10 юрлиц до 3 161 лота; Playwright + Fabrikant
2. **Топ закупок** — горизонтальный bar chart, top-12 по цене
3. **Макроэк.** — USD vs ставка ЦБ, лаг CCF 3 мес, тепловая карта
4. **ML Аномалии** — HHI-шкала, Scatter (Isolation Forest), Radar (нормализован), Treemap
5. **AI Инсайты** — 6 аномалий с Risk Score 1–10

Тёмная / светлая тема, анимированные счётчики.

```powershell
cd presentation
npm install
npm run dev   # http://localhost:5173
```

## Демонстрация БД (DB Browser for SQLite)

```powershell
python export_to_sqlite.py    # создаёт purchase_analysis.db
# Открыть в DB Browser for SQLite:
# File -> Open Database -> purchase_analysis.db
# Execute SQL -> открыть demo_queries.sql
```

Готовые VIEW: `v_summary`, `v_top20`, `v_hhi`, `v_hhi_total`, `v_by_entity`, `v_monthly`, `v_anomaly_zero_savings`, `v_large_lots`, `v_entity_scope_stats`.

## Документация

| Файл | Назначение |
|---|---|
| `docs/RUNBOOK.md` | Команды сбора, merge, проверок |
| `docs/SOURCES.md` | Матрица источников и их статус аудита |
| `docs/ENTITY_SCOPE.md` | Политика 32 юрлиц, ИНН, aliases |
| `docs/DEDUPLICATION.md` | Правила dedupe, текущая статистика |
| `docs/CLEANUP_NOTES.md` | Что удалено, что осталось |
| `docs/FABRIKANT_PLAN.md` | Детальный план разблокировки Fabrikant |
| `docs/PROJECT_MAP.md` | Полная карта репозитория |

## Установка и тесты

```powershell
python -m pip install -e .
python -m pytest tests/test_entity_resolution.py tests/test_source_sprint.py tests/test_merge_sprints.py tests/test_merge_aliases.py tests/test_sberbank_ast.py tests/test_b2b_center.py tests/test_lot_online.py tests/test_zakazrf.py tests/test_tender_pro.py tests/test_tektorg.py tests/test_roseltorg_parsing.py tests/test_eis_payload.py -q
```

## Аудит источников (итог)

| ЭТП | Статус | Причина |
|---|---|---|
| Sberbank-AST | ✅ production | 2 761 лот, REST API |
| B2B-Center | ✅ production | 400 лотов, Playwright + CAPTCHA bypass |
| ЕИС | ✅ control | 3 строки (44-ФЗ/223-ФЗ), удалены как дубли |
| Tektorg | ❌ audited_empty | SOAP API, 0 результатов (только 44-ФЗ) |
| Roseltorg | ❌ audited_empty | 0 результатов по всем ИНН |
| TenderPro | ❌ audited_empty | Профили есть, закупок 0 |
| LotOnline | ❌ audited_empty | Промышленная площадка |
| ETP GPB | ❌ audited_empty | Возвращает имущественные торги, не закупки |
| ZakazRF | ❌ audited_empty | 0 процедур по всем ИНН |
| RTS Tender | ❌ unavailable | HTTP 503 |
| Fabrikant | ❌ candidate_blocked | Требует верификации юрлица (4 попытки: RSC, SA, cookie, text) |

## Правила

- `configs/entity_scope.csv` содержит 32 entity; `aliases` — строго JSON-массив.
- Закупкой Сбера считается только совпадение по ролям **customer / buyer / organizer**.
- Сбербанк-АСТ как оператор/площадка — **не** закупка Сбера.
- `scripts/merge_aliases.py` — dry-run по умолчанию, запись только с `--apply` после review.
- Новый batch добавляется в allowlist только после audit + `--dry-run` проверки.
- `export_to_sqlite.py` и `purchase_analysis.db` — для демонстрации; не является основным хранилищем.
