# Progress Tracker

> Агент обновляет этот файл после каждой сессии. Пользователь может править `current_phase` вручную.

```yaml
current_phase: 1
phase_status: pending
last_updated: 2026-06-14
last_session_summary: "Playbook создан; работа не начата."
blockers: []
user_help_needed: []
```

## KPI baseline (2026-06-14)

| metric | value |
|--------|-------|
| lots_total | 1533 |
| entities_with_lots | 13 / 24 |
| price_coverage | 25% |
| sources_in_core | sberbank_ast (940), roseltorg (593) |
| winners_total | 0 |

## Phase checklist

- [ ] **1** — Аудит и backlog
- [ ] **2** — Расширение сбора данных (EIS, лимиты, entity_scope)
- [ ] **3** — PostgreSQL, дедуп, валидация
- [ ] **4** — Аналитика, аномалии, LLM, unit-price бонус
- [ ] **5** — Финализация (README, notebook, compliance)

## Session log

| date | phase | outcome | next |
|------|-------|---------|------|
| 2026-06-14 | setup | Playbook skill создан | phase 1 audit |
