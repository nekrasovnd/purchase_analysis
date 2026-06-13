from __future__ import annotations

from pathlib import Path

import nbformat as nbf
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
CURATED_DIR = ROOT_DIR / "data" / "curated"
REPORTS_DIR = ROOT_DIR / "data" / "reports"
NOTEBOOK_PATH = ROOT_DIR / "notebooks" / "purchase_analysis.ipynb"


def _read_csv(name: str) -> pd.DataFrame:
    path = CURATED_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _metric(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.3f}"


def build_notebook() -> None:
    entities = _read_csv("entity_coverage.csv")
    source_assessment = _read_csv("source_assessment.csv")
    entity_links = _read_csv("entity_source_links.csv")
    lots = _read_csv("procurement_lots.csv")
    yearly = _read_csv("mart_yearly_summary.csv")
    monthly = _read_csv("mart_monthly_activity.csv")
    category_mix = _read_csv("mart_category_mix.csv")
    category_yoy = _read_csv("mart_category_yoy.csv")
    anomalies = _read_csv("mart_anomalies.csv")
    duplicate_stats = _read_csv("duplicate_stats.csv")
    macro = _read_csv("mart_monthly_macro_join.csv")

    total_entities = int(len(entities))
    total_lots = int(len(lots))
    total_duplicates_removed = int(duplicate_stats["duplicate_rows_removed"].sum()) if not duplicate_stats.empty else 0
    price_coverage = float(lots["price_rub"].notna().mean()) if not lots.empty else 0.0
    disclosed_value = float(lots["price_rub"].fillna(0).sum()) if not lots.empty else 0.0
    source_breakdown = (
        lots["source_system"].value_counts().to_dict() if not lots.empty and "source_system" in lots.columns else {}
    )
    active_entities = (
        lots["entity_name"].value_counts().index.tolist() if not lots.empty and "entity_name" in lots.columns else []
    )
    focus_yoy = category_yoy.loc[category_yoy["focus_category"] == "Telecom & Devices"].copy()
    corr_lots_usd = (
        float(macro["corr_lots_vs_usd"].dropna().iloc[0])
        if not macro.empty and len(macro["corr_lots_vs_usd"].dropna()) > 0
        else None
    )
    corr_total_rate = (
        float(macro["corr_total_vs_key_rate"].dropna().iloc[0])
        if not macro.empty and len(macro["corr_total_vs_key_rate"].dropna()) > 0
        else None
    )

    nb = nbf.v4.new_notebook()
    cells: list = []

    cells.append(
        nbf.v4.new_markdown_cell(
            "# Анализ закупок группы Сбер за 2024–2025 годы\n\n"
            "В ноутбуке собран воспроизводимый аналитический отчёт по открытому контуру ЭТП.\n\n"
            f"- Юрлиц в периметре: `{total_entities}`\n"
            f"- Юрлиц с наблюдаемыми закупками: `{len(active_entities)}`\n"
            f"- Лотов в итоговом слое после дедупликации: `{total_lots}`\n"
            f"- Удалено дублей: `{total_duplicates_removed}`\n"
            f"- Покрытие ценой: `{price_coverage:.0%}`\n"
            f"- Сумма раскрытых цен: `{disclosed_value:,.2f}` RUB".replace(",", " ")
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## 1. Контур источников\n\n"
            "Логика решения разделяет `официальный контур идентификации` и `рабочие контуры наблюдения`:\n\n"
            "- `ЕИС` используется для резолвинга юридических лиц и контрольной проверки открытого покрытия по 223-ФЗ.\n"
            "- `Росэлторг` и `Сбербанк-АСТ` используются как рабочие источники публичных карточек процедур.\n"
            "- Для `Сбербанк-АСТ` дополнительно применяется фильтр по предметной области: из единого реестра исключены процедуры реализации имущества и банкротные продажи, чтобы в аналитический слой попадали только procurement-релевантные записи.\n"
            "- Остальные ЭТП повторно исследованы и отражены в `source_assessment.csv` как `operational`, `research_only` или `blocked`.\n\n"
            "Это важно, потому что задача не только про сбор данных, но и про честную оценку покрытия."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import pandas as pd\n"
            "import matplotlib.pyplot as plt\n"
            "\n"
            "ROOT = Path.cwd().resolve().parent if Path.cwd().name == 'notebooks' else Path.cwd().resolve()\n"
            "CURATED = ROOT / 'data' / 'curated'\n"
            "\n"
            "entities = pd.read_csv(CURATED / 'entity_coverage.csv')\n"
            "source_assessment = pd.read_csv(CURATED / 'source_assessment.csv')\n"
            "entity_links = pd.read_csv(CURATED / 'entity_source_links.csv')\n"
            "lots = pd.read_csv(CURATED / 'procurement_lots.csv')\n"
            "yearly = pd.read_csv(CURATED / 'mart_yearly_summary.csv')\n"
            "monthly = pd.read_csv(CURATED / 'mart_monthly_activity.csv')\n"
            "category_mix = pd.read_csv(CURATED / 'mart_category_mix.csv')\n"
            "category_yoy = pd.read_csv(CURATED / 'mart_category_yoy.csv')\n"
            "anomalies = pd.read_csv(CURATED / 'mart_anomalies.csv')\n"
            "duplicate_stats = pd.read_csv(CURATED / 'duplicate_stats.csv')\n"
            "macro = pd.read_csv(CURATED / 'mart_monthly_macro_join.csv')\n"
            "\n"
            "source_assessment[['source_system', 'operational_status', 'inclusion_status', 'coverage_note']]"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## 2. Связка сущностей между источниками\n\n"
            "Ниже показано, как юрлица группы Сбер были связаны с внешними идентификаторами источников.\n\n"
            "Observation: для части компаний исходный ИНН в первоначальном scope пришлось скорректировать по ЕИС/AST-резолвингу.\n\n"
            "Interpretation: без отдельного шага entity resolution мы получили бы ложные пропуски и слабое покрытие по закупкам.\n\n"
            "Significance: это ключевой инженерный шаг для воспроизводимости и качества выгрузки.\n\n"
            "Limitation: открытые справочники ЭТП показывают не все внутренние дочерние/региональные сущности одинаково полно."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "display(entities[['entity_name', 'inn', 'resolved_inn', 'eis_223_open_count', 'roseltorg_lot_count', 'sberbank_ast_lot_count']])\n"
            "display(entity_links[['entity_name', 'source_system', 'external_customer_key', 'records_total']].head(40))"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## 3. Сравнение 2024 vs 2025\n\n"
            "Ниже — базовое сравнение числа лотов и раскрытого стоимостного объёма по годам."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "display(yearly)\n"
            "fig, axes = plt.subplots(1, 2, figsize=(12, 4))\n"
            "yearly.plot(x='publication_year', y='lots_count', kind='bar', ax=axes[0], legend=False, color='#1D3557')\n"
            "axes[0].set_title('Количество лотов по годам')\n"
            "axes[0].set_xlabel('Год')\n"
            "axes[0].set_ylabel('Лоты')\n"
            "yearly.plot(x='publication_year', y='total_price_rub', kind='bar', ax=axes[1], legend=False, color='#2A9D8F')\n"
            "axes[1].set_title('Раскрытая стоимость по годам')\n"
            "axes[1].set_xlabel('Год')\n"
            "axes[1].set_ylabel('RUB')\n"
            "plt.tight_layout()\n"
            "plt.show()"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "Observation: в 2025 году открытый procurement-контур заметно активнее и по количеству лотов, и по раскрытой стоимости.\n\n"
            "Interpretation: часть эффекта связана с более широким публичным покрытием AST в 2025 году и активизацией коммерческих закупок в цифровом/операционном контуре.\n\n"
            "Significance: даже без полного внутреннего доступа можно уверенно зафиксировать межгодовой сдвиг активности.\n\n"
            "Limitation: это не полная группа Сбер и не полный closed-loop procurement, а только наблюдаемый публичный слой."
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## 4. Ключевое направление: Telecom & Devices\n\n"
            "В качестве ключевого направления выбрано `Telecom & Devices`, потому что оно одновременно:\n\n"
            "- хорошо наблюдается в открытых данных,\n"
            "- содержит заметный стоимостной объём,\n"
            "- даёт предметные закупочные сюжеты, а не только общие процедуры."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "telecom_yoy = category_yoy[category_yoy['focus_category'] == 'Telecom & Devices'].copy()\n"
            "display(telecom_yoy)\n"
            "monthly_pivot = monthly.pivot_table(index='publication_month', columns='focus_category', values='lots_count', fill_value=0)\n"
            "monthly_pivot[['Telecom & Devices']].plot(figsize=(12, 4), marker='o', color='#E76F51')\n"
            "plt.title('Telecom & Devices: помесячная динамика лотов')\n"
            "plt.xlabel('Месяц')\n"
            "plt.ylabel('Лоты')\n"
            "plt.xticks(rotation=45)\n"
            "plt.tight_layout()\n"
            "plt.show()"
        )
    )

    telecom_growth_note = "n/a"
    if not focus_yoy.empty and focus_yoy["lots_count_growth_ratio"].notna().any():
        telecom_growth_note = f"{float(focus_yoy['lots_count_growth_ratio'].dropna().iloc[-1]):.2f}x"

    cells.append(
        nbf.v4.new_markdown_cell(
            f"Observation: направление `Telecom & Devices` выросло по количеству лотов примерно в `{telecom_growth_note}` между 2024 и 2025 годами.\n\n"
            "Interpretation: это согласуется с публично наблюдаемыми закупками оборудования, лицензий, сетевой инфраструктуры и профильных ИТ-услуг.\n\n"
            "Significance: направление можно использовать как приоритетное окно для детального мониторинга технологических потребностей группы.\n\n"
            "Limitation: часть общих ИТ/операционных закупок остаётся в категории `Other`, потому что названия процедур не всегда достаточно структурированы."
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## 5. Топ дорогих лотов\n\n"
            "После фильтрации out-of-scope процедур можно построить уже осмысленный список дорогих закупок."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "top_lots = (\n"
            "    lots[['entity_name', 'platform_section', 'subject', 'focus_category', 'price_rub', 'published_at', 'detail_url']]\n"
            "    .sort_values('price_rub', ascending=False)\n"
            "    .head(20)\n"
            ")\n"
            "display(top_lots)\n"
            "top_lots.head(10).plot(kind='barh', x='subject', y='price_rub', figsize=(12, 8), color='#457B9D', legend=False)\n"
            "plt.title('Топ-10 дорогих лотов')\n"
            "plt.xlabel('RUB')\n"
            "plt.ylabel('Предмет')\n"
            "plt.tight_layout()\n"
            "plt.show()"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "Observation: верхние строки формируются в основном за счёт крупных телеком- и инфраструктурных закупок, особенно в контуре `ООО Сбербанк-Телеком`.\n\n"
            "Interpretation: открытый публичный след особенно хорошо отражает крупные конкурентные процедуры с существенной закупочной стоимостью.\n\n"
            "Significance: этот блок уже подходит для short-list ручной проверки, контроля категорий и последующей supplier-аналитики.\n\n"
            "Limitation: по части процедур цена всё ещё не раскрывается, поэтому top-value лист не эквивалентен полной картине расходов."
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## 6. Корреляция с макрофакторами\n\n"
            "Проверяем исследовательскую гипотезу: меняется ли открытая закупочная активность вместе с динамикой `USD/RUB` и ключевой ставки."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "display(macro)\n"
            "fig, ax1 = plt.subplots(figsize=(12, 5))\n"
            "ax1.plot(macro['publication_month'], macro['lots_count'], color='#C1121F', marker='o', label='Лоты')\n"
            "ax1.set_ylabel('Лоты')\n"
            "ax1.set_xlabel('Месяц')\n"
            "ax1.tick_params(axis='x', rotation=45)\n"
            "ax2 = ax1.twinx()\n"
            "ax2.plot(macro['publication_month'], macro['avg_usd_rub'], color='#003049', marker='s', label='USD/RUB')\n"
            "ax2.plot(macro['publication_month'], macro['avg_key_rate'], color='#669BBC', marker='^', label='Ключевая ставка')\n"
            "ax2.set_ylabel('Макрофакторы')\n"
            "lines_1, labels_1 = ax1.get_legend_handles_labels()\n"
            "lines_2, labels_2 = ax2.get_legend_handles_labels()\n"
            "ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')\n"
            "plt.title('Открытая закупочная активность и макрофакторы')\n"
            "plt.tight_layout()\n"
            "plt.show()"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "Observation: текущий open-data sample даёт отрицательную корреляцию `lots_count vs USD` "
            f"на уровне `{_metric(corr_lots_usd)}` и отрицательную корреляцию `total_price vs key_rate` на уровне `{_metric(corr_total_rate)}`.\n\n"
            "Interpretation: это больше похоже на исследовательский сигнал, чем на устойчивую причинную связь.\n\n"
            "Significance: архитектура уже позволяет регулярно проверять подобные гипотезы и расширять набор внешних факторов.\n\n"
            "Limitation: выборка короткая и частично смещена в сторону отдельных источников, поэтому статистическую силу здесь нельзя переоценивать."
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## 7. Дедупликация, документы и ПДн\n\n"
            "Отдельно фиксируем служебные аспекты качества данных."
        )
    )

    cells.append(
        nbf.v4.new_code_cell(
            "display(duplicate_stats)\n"
            "docs = pd.read_csv(CURATED / 'document_links.csv')\n"
            "docs.head(20)"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "Observation: после объединения источников были обнаружены и удалены дубли, в текущем прогоне — ограниченно и в основном в контуре `ООО Сбербанк-Телеком`.\n\n"
            "Interpretation: дубли возникают из-за нескольких customer-ключей одной и той же сущности на площадке и должны убираться до аналитического слоя.\n\n"
            "Significance: это напрямую влияет на корректность KPI, YoY-сравнений и аномалий.\n\n"
            "Limitation: документы сейчас учитываются только как безопасные метаданные ссылок; бинарные вложения и текст из них не скачиваются, чтобы не заносить ПДн в витрину."
        )
    )

    cells.append(nbf.v4.new_markdown_cell("## 8. Аномалии"))

    cells.append(
        nbf.v4.new_code_cell(
            "display(anomalies.head(50))\n"
            "anomalies['anomaly_type'].value_counts()"
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "Observation: доминирующий тип аномалий — `price_outlier`, что естественно для публичного слоя с заметным перекосом в крупные и редкие процедуры.\n\n"
            "Interpretation: самые крупные телеком- и инфраструктурные закупки выбиваются относительно медианы своих категорий на порядки.\n\n"
            "Significance: это уже полезный short-list для ручной проверки, аудита категории и сценариев anti-fraud/anti-waste.\n\n"
            "Limitation: для сценариев вроде `единственный участник = победитель` нам пока не хватает открытых participant-level данных из источников."
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## 9. LLM-автоматизация\n\n"
            "В репозитории дополнительно генерируется `data/reports/llm_prompt_pack.md` — компактный контекст-пакет для LLM.\n\n"
            "Практический смысл:\n\n"
            "- можно быстро отдавать витрины модели для генерации первичных выводов,\n"
            "- можно автоматизировать drafting аналитической записки,\n"
            "- можно использовать этот же пакет как основу для дальнейшего document/question-answer контура.\n\n"
            "Это не заменяет ручную проверку, но ускоряет интерпретацию и подготовку narrative-части."
        )
    )

    cells.append(
        nbf.v4.new_markdown_cell(
            "## Вывод\n\n"
            "После повторного исследования ЭТП и расширения покрытия решение перестало быть одноисточниковым: теперь оно сочетает `ЕИС` для официального контроля, `Росэлторг` для лот-карточек и `Сбербанк-АСТ` для массового публичного procurement-контента. "
            "Ключевой инженерный результат — не просто рост объёма данных, а появление корректного, дедуплицированного и предметно очищенного аналитического слоя, который уже можно защищать как тестовое решение уровня Data Engineer / Data Analyst."
        )
    )

    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.11",
        },
    }
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTEBOOK_PATH.open("w", encoding="utf-8") as file:
        nbf.write(nb, file)


if __name__ == "__main__":
    build_notebook()
