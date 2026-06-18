---
name: purchase-analysis-playbook
description: >-
  Orchestrates the Sber procurement analysis test project (purchase_analysis):
  multi-phase audit, ETP/EIS data collection, PostgreSQL, analytics, and delivery.
  Use when the user says дальше, продолжай, next, continue, старт, начни,
  or works on purchase_analysis / закупки Сбер / тестовое задание закупок.
---

# Purchase Analysis Playbook

Пошаговый playbook для перелопачивания `purchase_analysis`. Пользователь управляет одним словом: **«дальше»**, **«продолжай»**, **«старт»**.

## Файлы playbook

| Файл | Назначение |
|------|------------|
| [PROGRESS.md](PROGRESS.md) | Текущая фаза, KPI, blockers, session log |
| [context.md](context.md) | Мастер-контекст, DoD, архитектура |
| [prompts.md](prompts.md) | Детальные инструкции по фазам 1–5 и SOS |

**Первое действие в каждой сессии:** прочитать `PROGRESS.md`, затем `prompts.md` для текущей фазы.

---

## Команды пользователя

| Команда | Действие агента |
|---------|-----------------|
| **старт** / **начни** / **go** | `current_phase=1`, выполнить Phase 1 |
| **дальше** / **продолжай** / **next** / **continue** | Прочитать PROGRESS → выполнить текущую фазу; если `completed` → перейти на следующую |
| **фаза N** / **phase N** | Установить `current_phase=N`, выполнить |
| **блокер** / **SOS** | Phase SOS из prompts.md; `phase_status=blocked` |
| **статус** | KPI + текущая фаза + blockers, без кода |
| **сброс** | Только по явной просьбе: phase 1, очистить blockers |

Не проси пользователя копировать промпты — playbook уже здесь.

---

## Workflow каждой сессии

```
1. Read PROGRESS.md
2. Read context.md (если первый раз в сессии или фаза сменилась)
3. Read prompts.md → секция текущей фазы
4. Set phase_status = in_progress
5. Execute phase (код, прогоны, отчёты)
6. Measure KPI (quality_summary.json, procurement_lots count)
7. Update PROGRESS.md:
   - phase_status: completed | blocked | in_progress
   - last_updated, last_session_summary
   - session log row
   - checklist [x] если фаза done
   - if completed → current_phase += 1
8. Report пользователю: что сделано, KPI до/после, что на «дальше»
```

---

## Фазы

| # | Название | Кратко |
|---|----------|--------|
| 1 | Аудит | Gap-анализ, backlog, без кода |
| 2 | Сбор данных | EIS lots, лимиты, entity_scope, ЭТП |
| 3 | БД + качество | PostgreSQL, validation, dedup |
| 4 | Аналитика | YoY, macro, anomalies, unit-price, LLM |
| 5 | Сдача | README, notebook, compliance |

Подробности — в [prompts.md](prompts.md).

---

## Правила

- **Измеряй KPI** до и после; baseline в PROGRESS
- **Не коммить/не пушить** без явной просьбы
- **Минимальный diff** — не переписывать архитектуру без нужды
- **Блокеры** (капча, логин, creds) → SOS, спросить пользователя, не застревать
- **Инструменты без ограничений:** Playwright, shell, subagents, любые skills
- При длинном pipeline — background shell или высокий timeout

---

## Ответ пользователю после сессии

Всегда заканчивай блоком:

```markdown
## Playbook status
- Фаза: N — [название] — [completed|in_progress|blocked]
- KPI: lots X, entities Y/24, price coverage Z%
- Следующий шаг: напиши **«дальше»**
- Нужна помощь: [или «нет»]
```

---

## Quick reference: текущий baseline

См. таблицу KPI в [PROGRESS.md](PROGRESS.md). На 2026-06-14: **1533 лота**, **13/24 юрлиц**, главный gap — **EIS не отдаёт лоты в core**.
