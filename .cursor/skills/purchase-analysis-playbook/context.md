# Master Context

## Цель

Тестовое задание: собрать, обработать и проанализировать закупки **группы Сбер** за **2024–2025** из открытых источников. Сдать: GitHub, Jupyter Notebook, README.

## Критерии оценки

- Объём и качество данных — главный фактор балла
- Несколько источников, обогащение, дедуп, обезличивание ПДн
- 44-ФЗ и 223-ФЗ, период 2024–2025
- Полный перечень юрлиц группы Сбер
- PostgreSQL + полезные SQL
- YoY, корреляции (USD/RUB, ключевая ставка, ИПЦ), аномалии
- LLM для неструктурированных данных
- К каждому графику: Наблюдение / Интерпретация / Значимость / Ограничение
- Бонус: unit-price кейс (ремонт м², стулья и т.п.)

## Репозиторий

- Root: `D:/Nikita/Work/purchase_analysis`
- Scope: `configs/entity_scope.csv` (24 юрлица)
- Pipeline: `src/purchase_analysis/`
- Curated: `data/curated/`
- DB: `db/`
- Notebook: `notebooks/purchase_analysis.ipynb`

## Архитектура (кратко)

- EIS → entity resolution (лоты пока не в core)
- Roseltorg + Sberbank-AST → core lots
- SberB2B → enrichment (goods, unit price, docs)
- CBR → USD/RUB, key rate, CPI

## Лимиты RunConfig (config.py)

- max_pages: 120
- max_sberb2b_details: 1000
- download_documents_limit: 250

## Принципы агента

1. Измерь KPI до и после каждого этапа
2. Не снижай качество ради объёма (exact INN/role/date)
3. Воспроизводимость: raw snapshots, CLI, тests
4. Любые инструменты: Playwright, shell, subagents
5. Спрашивай пользователя только при блокерах (капча, логин, PG creds, API key)
6. Не коммить/не пушить без явной просьбы
7. Минимальный diff

## Definition of Done

- ≥5000 лотов ИЛИ доказанный потолок открытого контура с цифрами
- ≥18/24 юрлиц с лотами ИЛИ gap-отчёт
- EIS как источник лотов ИЛИ обоснованный блокер
- PostgreSQL demo-ready
- Notebook с narrative
- Unit-price benchmark (бонус)
- README с честными ограничениями

## Запуск

```powershell
$env:PYTHONPATH = "src"
python -m pip install -e .
python -m purchase_analysis.cli run-all
python -m unittest discover -s tests -v
```
