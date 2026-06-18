# Phase Prompts

Детальные инструкции по фазам. Агент выполняет **только текущую фазу** из PROGRESS.md.

---

## Phase 1 — Аудит и план

```
Проведи полный аудит purchase_analysis перед перелопачиванием.

1. Прогони tests и изучи CLI flags
2. KPI из data/curated/*.csv и quality_summary.json
3. Для 24 юрлиц: entity_coverage vs procurement_lots
4. Узкие места: RunConfig limits, пустые INN, AST filters, отсутствие EIS lot-fetch
5. Сравни eis_223_open_count с фактическими лотами
6. Backlog 5–10 пунктов с ожидаемым приростом лотов

Формат ответа:
- Таблица gap (источник × юрлицо × потенциал × блокер)
- Топ-3 quick wins
- Топ-3 риска
- Рекомендация для phase 2

Не пиши код до показа плана.
```

**Done when:** backlog есть, KPI baseline зафиксирован, PROGRESS обновлён → phase 2.

---

## Phase 2 — Расширение сбора данных

**Целевые KPI:** lots ≥ 3000 (stretch 5000+), entities ≥ 18/24.

### A. EIS как источник лотов
- Fetch по customerIdOrg для 223-ФЗ и 44-ФЗ, 2024–2025
- Raw в data/raw/eis/, normalize → procurement_lots (source_system=eis)

### B. Лимиты и resume
- Поднять max_pages, max_sberb2b_details; checkpoint/resume

### C. entity_scope
- Дозаполнить INN; расширить периметр если нужно

### D. Sberbank-AST + SberB2B
- Проверить asset-sale filter; раскрыть все B2B details

### E. Roseltorg
- Полная пагинация по всем юрлицам

### F. Прочие ЭТП
- ZakazRF, Lot-Online, RTS, Tektorg, ETP GPB: integrate или доказать 0

**Deliverables:** код, прогон, до/после KPI, gap-отчёт в data/reports/

**Done when:** KPI вырос или блокеры задокументированы → phase 3.

---

## Phase 3 — PostgreSQL и качество

1. Load curated → PostgreSQL (db/ddl)
2. SQL views/marts: coverage, duplicates, cross-source matches
3. Валидация: INN in scope, dates 2024–2025, prices, dedup key
4. Обогатить unit_price; поднять price_coverage

**Deliverables:** load script/instructions, 5+ SQL с комментариями, tests

**Done when:** PG demo-ready, duplicate_stats обновлён → phase 4.

---

## Phase 4 — Аналитика и бонус

### Обязательно
- 2024 vs 2025 YoY по направлениям
- Monthly activity, category mix, top-20 дорогих
- Корреляции: USD/RUB, key rate, ИПЦ
- Аномалии: single bidder, supplier dominance, price spikes, bursts

### Бонус unit-price
- Benchmark median/p25/p75 по времени
- Флаги переплаты
- График цена vs USD/RUB
- Narrative «где переплатили»

### LLM
- Обновить llm_prompt_pack.md; llm_summary если есть API key

### Формат выводов
Наблюдение / Интерпретация / Значимость / Ограничение

**Done when:** notebook + marts обновлены → phase 5.

---

## Phase 5 — Финализация

1. README: гипотезы, источники, KPI, ограничения, запуск
2. Notebook самодостаточен
3. Full pipeline + tests
4. docs/compliance_report.md
5. source_assessment.csv полный
6. Чеклист сдачи

Commit/PR — только по просьбе пользователя.

**Done when:** все DoD пункты закрыты или явно marked blocked.

---

## SOS — блокер парсинга

```
Парсинг [ИСТОЧНИК] заблокирован: [описание].

1. Зафиксировать в data/reports/ с доказательством
2. Альтернативы: другой endpoint, ЕИС по номеру, Playwright, ручной экспорт
3. Параллельно другие источники
4. Не заявлять «0» без exact-probe proof

Спросить пользователя: [конкретный вопрос].
```

Обновить PROGRESS: phase_status=blocked, blockers=[...].
