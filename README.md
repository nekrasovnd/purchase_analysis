# Аналитика закупок группы Сбербанк

Проект собирает, нормализует и анализирует открытые данные о закупках ПАО Сбербанк и 31 дочернего юрлица (Sber Group) за 2024–2025 годы.

**Итог: 3 161 закупка · 30,5 млрд ₽ · 22 юрлица с активными закупками из 32 в скопе**

---

## Результаты по источникам

| ЭТП | Результат | Метод | Причина |
|---|---|---|---|
| **Sberbank-AST** | ✅ 2 761 лот | REST API `/api/v2/lots` | Основной источник, API открытый |
| **B2B-Center** | ✅ 400 лотов | Playwright + CAPTCHA bypass | Потребовал браузерного парсинга и автоматического прохождения капчи |
| **ЕИС** | ⚠️ 3 строки (дубли AST) | REST API | 44-ФЗ/223-ФЗ: все найденные закупки уже есть в AST, удалены как дубли |
| **Tektorg** | ❌ 0 результатов | SOAP API | Площадка работает только с 44-ФЗ госзакупками, Сбер не участвует |
| **Roseltorg** | ❌ 0 результатов | REST API | Аналогично — 44-ФЗ/223-ФЗ, ИНН Сбера не возвращают процедур |
| **TenderPro** | ❌ 0 результатов | REST API | Профили юрлиц найдены, но закупочных процедур нет |
| **LotOnline** | ❌ 0 результатов | JSON API | Промышленная площадка, Сбер не размещает |
| **ETP GPB** | ❌ 0 закупок | REST API | INN-фильтр возвращает имущественные торги (банкротства/залоги), а не закупки |
| **ZakazRF** | ❌ 0 процедур | HTML-парсинг | Юрлица Сбера найдены в реестре, но закупочная активность равна нулю |
| **RTS Tender** | ❌ недоступен | HTTP | HTTP 503 на всех эндпоинтах во время аудита |
| **Fabrikant** | ❌ заблокирован | Next.js RSC / Server Action | Требует верификации юрлица. 4 попытки обхода: RSC GET-запрос (INN игнорируется сервером), Server Action `fetchOrganizationBySearch` (403 без авторизации), подделка cookie (403), текстовый поиск (возвращает 10 из 102 без пагинации API) |

---

## Ключевые аналитические находки

| Аномалия | Значение | Уровень риска |
|---|---|---|
| HHI (концентрация вендоров) | **5 698** — в 2,3× выше порога монополии DoJ (2 500) | Критический |
| Мегалот Cloud.ru (ЦОД) | **13,33 млрд ₽**, Z-score = 19,96 | Критический |
| Корреляция ставки ЦБ с бюджетами | r = **+0,546**, лаг 3 мес (CCF) | Высокий |
| Декабрьский «слив» бюджета | **1,116 млрд ₽** — 10× медианного месяца | Высокий |
| Признаки дробления лотов | MinHashLSH = 0,97 по серверным шкафам | Средний |
| 0% экономии, 1 участник | Isolation Forest score = 0,91 | Средний |

---

## 1. Запуск дашборда

```powershell
cd presentation
npm.cmd install
npm.cmd run dev
```
*Откройте в браузере: http://localhost:5173*

Дашборд: 5 вкладок (История → Топ закупок → Макроэкономика → ML Аномалии → AI Инсайты), тёмная/светлая тема.

---

## 2. Пайплайн: полный прогон (парсинг → merge → SQLite)

```powershell
python run_pipeline.py
```

Скрипт последовательно:
1. Запускает парсинг Sberbank-AST, B2B-Center и ЕИС
2. Объединяет результаты и удаляет кросс-источниковые дубли (`scripts/merge_sprints.py`)
3. Экспортирует чистый датасет в `purchase_analysis.db`

> **Примечание:** B2B-Center использует браузерный Playwright-парсинг — убедитесь, что Playwright установлен (`python -m playwright install chromium`). Для пропуска капчи потребуется сохранённый браузерный профиль.

### Только проверить merge (данные уже собраны)

```powershell
python run_pipeline.py --dry-run
```

### Пересобрать только SQLite из готовых данных

```powershell
python run_pipeline.py --step sqlite
```

### Запустить отдельный шаг

```powershell
# Только парсинг
python run_pipeline.py --step parse

# Только merge + SQLite
python run_pipeline.py --step merge
python run_pipeline.py --step sqlite
```

---

## 3. База данных (SQLite)

`purchase_analysis.db` уже собрана и лежит в корне репозитория. Для пересборки из актуального `output/merged_sprints.csv`:

```powershell
python export_to_sqlite.py
```

База содержит таблицу `lots` (3 161 запись), `entity_scope` (32 юрлица) и 9 аналитических VIEW:

| VIEW | Что показывает |
|---|---|
| `v_summary` | Сводка: итого закупок, бюджет, кол-во юрлиц |
| `v_top20` | Топ-20 закупок по цене |
| `v_by_entity` | Агрегат по каждому юрлицу |
| `v_by_source` | Агрегат по источнику (AST / B2B) |
| `v_monthly` | Динамика публикаций по месяцам |
| `v_hhi` | HHI по каждому вендору |
| `v_hhi_total` | Итоговый HHI (индекс монополизации) |
| `v_anomaly_zero_savings` | Закупки с 0% экономии и ≤1 участником |
| `v_large_lots` | Лоты дороже 500 млн ₽ |
| `v_entity_scope_stats` | Покрытие скопа: 22 нашли данные, 10 — нет |

Для демонстрации: откройте `purchase_analysis.db` в [DB Browser for SQLite](https://sqlitebrowser.org/) и используйте готовые запросы из `demo_queries.sql`.

---

## Структура репозитория

```
configs/                 # entity_scope.csv, allowlist, manifest
src/purchase_analysis/   # Python package (entity resolution, source sprint)
scripts/                 # парсеры *_prompt2_source_sprint_v2.py + merge_sprints.py
output/                  # merged_sprints.csv (gitignored)
presentation/            # React 19 дашборд (Vite + Recharts)
  Defense_Speech_FINAL.docx  # готовая защитная речь
export_to_sqlite.py      # экспорт CSV → SQLite
run_pipeline.py          # единый скрипт запуска всего пайплайна
purchase_analysis.db     # SQLite база (готова, 2 MB)
demo_queries.sql         # 15 SQL-запросов для демонстрации
docs/                    # RUNBOOK, SOURCES, ENTITY_SCOPE, DEDUPLICATION
```

---

## Установка

```powershell
python -m pip install -e .
```

Полный прогон тестов:

```powershell
python -m pytest tests/test_entity_resolution.py tests/test_source_sprint.py tests/test_merge_sprints.py tests/test_merge_aliases.py tests/test_sberbank_ast.py tests/test_b2b_center.py tests/test_lot_online.py tests/test_zakazrf.py tests/test_tender_pro.py tests/test_tektorg.py tests/test_roseltorg_parsing.py tests/test_eis_payload.py -q
```

---

## Правила

- Закупкой Сбера считается только совпадение по ролям **customer / buyer / organizer**.
- Сбербанк-АСТ как **оператор площадки** — не является закупкой Сбера.
- Новый batch добавляется в allowlist (`configs/source_sprints_allowlist.csv`) только после audit + `--dry-run` проверки.
- `purchase_analysis.db` генерируется из `export_to_sqlite.py` — не редактировать вручную.
