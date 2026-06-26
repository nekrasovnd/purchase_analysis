"""
export_to_sqlite.py
===================
Экспортирует данные закупок Сбера из CSV в SQLite-базу данных.
Создаёт готовые представления (VIEW) для демонстрации в DB Browser.

Запуск:
    python export_to_sqlite.py

Результат: purchase_analysis.db  (открывать в DB Browser for SQLite)
"""
import sqlite3
import pandas as pd
from pathlib import Path
import re

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "output"
CFG_DIR = ROOT / "configs"
DB_PATH = ROOT / "purchase_analysis.db"

# ─── Загрузка ─────────────────────────────────────────────────────────────────
print("Загружаем данные...")

merged = pd.read_csv(OUT_DIR / "merged_sprints.csv", encoding="utf-8-sig", low_memory=False)
print(f"  merged_sprints: {len(merged)} строк")

entity_scope = pd.read_csv(CFG_DIR / "entity_scope.csv", encoding="utf-8-sig", low_memory=False)
print(f"  entity_scope:   {len(entity_scope)} строк")

# ─── Нормализация ─────────────────────────────────────────────────────────────
# Выбираем и чистим ключевые поля
cols_keep = [
    "source_system", "entity_name",
    "procedure_number", "lot_number",
    "subject", "customer_name", "customer_inn",
    "status", "tender_type", "price_rub",
    "published_at", "application_deadline", "deadline_at",
    "method_name", "sprint_batch", "detail_url",
]
# Добавляем detail-поля если есть
for c in ["detail_subject", "detail_category", "detail_procedure_status"]:
    if c in merged.columns:
        cols_keep.append(c)

df = merged[[c for c in cols_keep if c in merged.columns]].copy()

# Нормализуем даты
for col in ["published_at", "application_deadline", "deadline_at"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")

# Добавляем вычисляемые поля
df["year_month"] = pd.to_datetime(df["published_at"], errors="coerce").dt.to_period("M").astype(str)
df["year"]       = pd.to_datetime(df["published_at"], errors="coerce").dt.year
df["source_label"] = df["source_system"].map({
    "sberbank_ast": "Sberbank-AST",
    "b2b_center":   "B2B-Center",
    "eis":          "ЕИС",
}).fillna(df["source_system"])

# Числа
df["price_rub"] = pd.to_numeric(df["price_rub"], errors="coerce")
df["lot_number"] = pd.to_numeric(df["lot_number"], errors="coerce").fillna(1).astype(int)

print(f"  Итого строк для загрузки: {len(df)}")

# ─── Запись в SQLite ──────────────────────────────────────────────────────────
print(f"\nЗаписываем в {DB_PATH}...")

if DB_PATH.exists():
    DB_PATH.unlink()

con = sqlite3.connect(DB_PATH)

# Главная таблица
df.to_sql("lots", con, index=False, if_exists="replace")

# Таблица юрлиц
entity_scope.to_sql("entity_scope", con, index=False, if_exists="replace")

# ─── Представления (VIEW) ─────────────────────────────────────────────────────
views = {

"v_summary": """
-- Краткая сводка по всему датасету
SELECT
    COUNT(*)                                                    AS total_lots,
    COUNT(DISTINCT entity_name)                                 AS entities_count,
    COUNT(DISTINCT source_system)                               AS sources_count,
    ROUND(SUM(price_rub) / 1e9, 2)                             AS total_budget_bln,
    ROUND(AVG(price_rub) / 1e6, 3)                             AS avg_lot_mln,
    ROUND(MAX(price_rub) / 1e9, 3)                             AS max_lot_bln,
    MIN(published_at)                                           AS date_from,
    MAX(published_at)                                           AS date_to
FROM lots
WHERE price_rub IS NOT NULL
""",

"v_by_source": """
-- Разбивка по источнику данных
SELECT
    source_label                                                AS источник,
    COUNT(*)                                                    AS лотов,
    COUNT(DISTINCT entity_name)                                 AS юрлиц,
    ROUND(SUM(price_rub) / 1e9, 3)                             AS бюджет_млрд,
    ROUND(AVG(price_rub) / 1e6, 3)                             AS средний_лот_млн
FROM lots
WHERE price_rub IS NOT NULL
GROUP BY source_label
ORDER BY бюджет_млрд DESC
""",

"v_by_entity": """
-- Топ юрлиц по объёму закупок
SELECT
    entity_name                                                 AS юрлицо,
    source_label                                                AS площадка,
    COUNT(*)                                                    AS лотов,
    ROUND(SUM(price_rub) / 1e9, 3)                             AS бюджет_млрд,
    ROUND(SUM(price_rub) * 100.0 /
        (SELECT SUM(price_rub) FROM lots WHERE price_rub IS NOT NULL), 1) AS доля_пct
FROM lots
WHERE price_rub IS NOT NULL
GROUP BY entity_name, source_label
ORDER BY бюджет_млрд DESC
""",

"v_top20": """
-- 20 самых дорогих закупок
SELECT
    procedure_number                                            AS номер_процедуры,
    lot_number                                                  AS номер_лота,
    entity_name                                                 AS заказчик,
    SUBSTR(subject, 1, 100)                                     AS предмет_закупки,
    ROUND(price_rub / 1e6, 2)                                  AS цена_млн,
    published_at                                                AS опубликовано,
    method_name                                                 AS способ_закупки,
    source_label                                                AS площадка
FROM lots
WHERE price_rub IS NOT NULL
ORDER BY price_rub DESC
LIMIT 20
""",

"v_monthly": """
-- Динамика по месяцам (2024-2025)
SELECT
    year_month                                                  AS месяц,
    year                                                        AS год,
    COUNT(*)                                                    AS лотов,
    ROUND(SUM(price_rub) / 1e9, 3)                             AS бюджет_млрд,
    ROUND(AVG(price_rub) / 1e6, 3)                             AS средний_лот_млн
FROM lots
WHERE price_rub IS NOT NULL
  AND year_month != 'NaT'
GROUP BY year_month
ORDER BY year_month
""",

"v_hhi": """
-- Расчёт индекса HHI по вендорам
WITH shares AS (
    SELECT
        entity_name,
        SUM(price_rub) AS total,
        SUM(price_rub) * 100.0 / (SELECT SUM(price_rub) FROM lots WHERE price_rub IS NOT NULL) AS share_pct
    FROM lots
    WHERE price_rub IS NOT NULL
    GROUP BY entity_name
)
SELECT
    entity_name                                                 AS вендор,
    ROUND(total / 1e9, 3)                                      AS бюджет_млрд,
    ROUND(share_pct, 2)                                         AS доля_pct,
    ROUND(share_pct * share_pct, 2)                            AS вклад_в_HHI
FROM shares
ORDER BY total DESC
""",

"v_hhi_total": """
-- Итоговый HHI
WITH shares AS (
    SELECT
        entity_name,
        SUM(price_rub) * 100.0 / (SELECT SUM(price_rub) FROM lots WHERE price_rub IS NOT NULL) AS share_pct
    FROM lots WHERE price_rub IS NOT NULL GROUP BY entity_name
)
SELECT
    ROUND(SUM(share_pct * share_pct)) AS hhi_index,
    CASE
        WHEN SUM(share_pct * share_pct) > 2500 THEN '🚨 Высококонцентрированный (> 2500)'
        WHEN SUM(share_pct * share_pct) > 1500 THEN '⚠️ Умеренно концентрированный'
        ELSE '✅ Конкурентный (< 1500)'
    END                                AS оценка_рынка
FROM shares
""",

"v_anomaly_zero_savings": """
-- Аномалия: дорогие лоты без конкуренции (цена > 1 млн)
-- Прокси: single_supplier лоты — метод 'Закупка у единственного поставщика'
SELECT
    procedure_number                                            AS процедура,
    entity_name                                                 AS заказчик,
    SUBSTR(subject, 1, 100)                                     AS предмет,
    ROUND(price_rub / 1e6, 2)                                  AS цена_млн,
    method_name                                                 AS способ,
    published_at                                                AS опубликовано,
    source_label                                                AS площадка
FROM lots
WHERE price_rub > 1000000
  AND (
      method_name LIKE '%единственного поставщика%'
      OR method_name LIKE '%единственного%'
      OR method_name LIKE '%single%'
  )
  AND price_rub IS NOT NULL
ORDER BY price_rub DESC
LIMIT 30
""",

"v_budget_by_month_entity": """
-- Бюджет по месяцам в разрезе топ-5 юрлиц
WITH top5 AS (
    SELECT entity_name FROM lots
    WHERE price_rub IS NOT NULL
    GROUP BY entity_name
    ORDER BY SUM(price_rub) DESC LIMIT 5
)
SELECT
    year_month                                                  AS месяц,
    l.entity_name                                               AS юрлицо,
    COUNT(*)                                                    AS лотов,
    ROUND(SUM(l.price_rub) / 1e6, 1)                          AS бюджет_млн
FROM lots l
JOIN top5 ON l.entity_name = top5.entity_name
WHERE l.price_rub IS NOT NULL AND year_month != 'NaT'
GROUP BY year_month, l.entity_name
ORDER BY year_month, бюджет_млн DESC
""",

"v_large_lots": """
-- Крупные лоты (> 100 млн руб) — для проверки комиссией
SELECT
    procedure_number                                            AS процедура,
    entity_name                                                 AS заказчик,
    SUBSTR(subject, 1, 120)                                     AS предмет,
    ROUND(price_rub / 1e6, 1)                                  AS цена_млн,
    method_name                                                 AS способ,
    published_at                                                AS опубликовано,
    source_label                                                AS площадка
FROM lots
WHERE price_rub > 100000000
ORDER BY price_rub DESC
""",

"v_entity_scope_stats": """
-- Юрлица в скопе и их представленность в данных
SELECT
    e.entity_name                                               AS юрлицо,
    e.inn                                                       AS ИНН,
    COUNT(l.procedure_number)                                   AS закупок,
    ROUND(COALESCE(SUM(l.price_rub), 0) / 1e6, 1)             AS бюджет_млн,
    CASE WHEN COUNT(l.procedure_number) > 0 THEN '✅ Найдено' ELSE '❌ Нет данных' END AS статус
FROM entity_scope e
LEFT JOIN lots l ON l.entity_name = e.entity_name
GROUP BY e.entity_name, e.inn
ORDER BY бюджет_млн DESC
""",
}

cur = con.cursor()
for view_name, sql in views.items():
    cur.execute(f"DROP VIEW IF EXISTS {view_name}")
    cur.execute(f"CREATE VIEW {view_name} AS {sql}")
    print(f"  VIEW {view_name} создан")

con.commit()

# --- Финальная проверка -------------------------------------------------------
print("\n-- Проверка ----------------------------------------------------------")
for view_name in views:
    try:
        row = pd.read_sql(f"SELECT * FROM {view_name} LIMIT 1", con)
        print(f"  [OK] {view_name}: {len(row.columns)} столбцов")
    except Exception as e:
        print(f"  [ERR] {view_name}: {e}")

size_mb = DB_PATH.stat().st_size / 1024 / 1024
print(f"\nОК  Файл: {DB_PATH}")
print(f"    Размер: {size_mb:.1f} MB")
print(f"    Строк в lots: {pd.read_sql('SELECT COUNT(*) AS n FROM lots', con).iloc[0,0]}")
print("\nОткрой в DB Browser for SQLite:")
print(f"  1. File > Open Database > {DB_PATH}")
print("  2. Вкладка 'Execute SQL' — вставь запрос из demo_queries.sql")

con.close()
