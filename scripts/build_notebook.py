from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import nbformat as nbf
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
MERGED_CSV = ROOT_DIR / "output" / "merged_sprints.csv"
MERGE_SUMMARY_JSON = ROOT_DIR / "output" / "merged_sprints_summary.json"
NOTEBOOK_PATH = ROOT_DIR / "notebooks" / "purchase_analysis.ipynb"


def ensure_clean_merge() -> None:
    if MERGED_CSV.exists() and MERGE_SUMMARY_JSON.exists():
        return
    subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "merge_sprints.py")],
        cwd=ROOT_DIR,
        check=True,
    )


def read_merged() -> pd.DataFrame:
    ensure_clean_merge()
    return pd.read_csv(MERGED_CSV, dtype=str, keep_default_na=False)


def read_summary() -> dict[str, object]:
    ensure_clean_merge()
    return json.loads(MERGE_SUMMARY_JSON.read_text(encoding="utf-8"))


def numeric_price(frame: pd.DataFrame) -> pd.Series:
    if "price_rub" not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame["price_rub"].replace("", pd.NA), errors="coerce")


def build_notebook() -> None:
    rows = read_merged()
    summary = read_summary()
    prices = numeric_price(rows)
    priced_rows = int(prices.notna().sum())
    total_price = float(prices.fillna(0).sum())
    source_counts = (
        rows["source_system"].value_counts().to_dict()
        if "source_system" in rows.columns
        else {}
    )
    entity_counts = (
        rows["entity_name"].value_counts().head(20).to_dict()
        if "entity_name" in rows.columns
        else {}
    )

    nb = nbf.v4.new_notebook()
    cells = [
        nbf.v4.new_markdown_cell(
            "# Анализ закупок группы Сбер за 2024-2025 годы\n\n"
            "Notebook построен из текущего clean source sprint merge, без старых curated snapshots.\n\n"
            f"- Batch-и: `{', '.join(summary['selected_batches'])}`\n"
            f"- Строк до cross-source dedupe: `{summary['rows_before_cross_source_dedupe']}`\n"
            f"- Удалено cross-source дублей: `{summary['cross_source_duplicates_dropped']}`\n"
            f"- Уникальных закупок после dedupe: `{summary['rows_after_cross_source_dedupe']}`\n"
            f"- Строк с раскрытой ценой: `{priced_rows}`\n"
            f"- Сумма раскрытых цен: `{total_price:,.2f}` RUB".replace(",", " ")
        ),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import pandas as pd\n"
            "import matplotlib.pyplot as plt\n"
            "\n"
            "ROOT = Path.cwd().resolve().parent if Path.cwd().name == 'notebooks' else Path.cwd().resolve()\n"
            "MERGED = ROOT / 'output' / 'merged_sprints.csv'\n"
            "SUMMARY = ROOT / 'output' / 'merged_sprints_summary.json'\n"
            "lots = pd.read_csv(MERGED, dtype=str, keep_default_na=False)\n"
            "summary = json.loads(SUMMARY.read_text(encoding='utf-8'))\n"
            "lots['price_rub_num'] = pd.to_numeric(lots.get('price_rub', ''), errors='coerce')\n"
            "lots.head()"
        ),
        nbf.v4.new_markdown_cell(
            "## Источники\n\n"
            "В clean dataset входят только источники из `configs/source_sprints_allowlist.csv`."
        ),
        nbf.v4.new_code_cell(
            "source_counts = lots['source_system'].value_counts()\n"
            "display(source_counts.rename_axis('source_system').reset_index(name='rows'))\n"
            "source_counts.plot(kind='bar', figsize=(8, 4), color='#2A9D8F')\n"
            "plt.title('Rows by source')\n"
            "plt.ylabel('Rows')\n"
            "plt.tight_layout()\n"
            "plt.show()"
        ),
        nbf.v4.new_markdown_cell(
            "## Дедупликация\n\n"
            "Основной ключ: `procedure_number + lot_number`. Между источниками используется тот же ключ без `source_system`, поэтому EIS-control строки удаляются как дубли уже найденных процедур."
        ),
        nbf.v4.new_code_cell(
            "pd.DataFrame([summary])"
        ),
        nbf.v4.new_markdown_cell(
            "## Активность по годам\n\n"
            "Дата берётся из `published_at`, где источник её отдаёт."
        ),
        nbf.v4.new_code_cell(
            "dates = pd.to_datetime(lots.get('published_at', ''), errors='coerce')\n"
            "yearly = lots.assign(publication_year=dates.dt.year)\n"
            "yearly = yearly[yearly['publication_year'].isin([2024, 2025])]\n"
            "yearly_summary = yearly.groupby('publication_year').agg(\n"
            "    rows=('procedure_number', 'count'),\n"
            "    priced_rows=('price_rub_num', lambda s: int(s.notna().sum())),\n"
            "    disclosed_price_rub=('price_rub_num', 'sum'),\n"
            ").reset_index()\n"
            "display(yearly_summary)\n"
            "yearly_summary.plot(x='publication_year', y='rows', kind='bar', legend=False, figsize=(7, 4), color='#457B9D')\n"
            "plt.title('Rows by publication year')\n"
            "plt.ylabel('Rows')\n"
            "plt.tight_layout()\n"
            "plt.show()"
        ),
        nbf.v4.new_markdown_cell(
            "## Топ заказчиков/юрлиц\n\n"
            "Этот блок показывает, какие entity дают основной наблюдаемый объём."
        ),
        nbf.v4.new_code_cell(
            "entity_counts = lots['entity_name'].value_counts().head(20)\n"
            "display(entity_counts.rename_axis('entity_name').reset_index(name='rows'))\n"
            "entity_counts.sort_values().plot(kind='barh', figsize=(10, 7), color='#E76F51')\n"
            "plt.title('Top entities by rows')\n"
            "plt.xlabel('Rows')\n"
            "plt.tight_layout()\n"
            "plt.show()"
        ),
        nbf.v4.new_markdown_cell(
            "## Топ лотов с раскрытой ценой\n\n"
            "Цена раскрыта не во всех источниках, поэтому список является shortlist для ручной проверки, а не полным рейтингом расходов."
        ),
        nbf.v4.new_code_cell(
            "top_priced = lots[lots['price_rub_num'].notna()].sort_values('price_rub_num', ascending=False)\n"
            "cols = [c for c in ['source_system', 'entity_name', 'procedure_number', 'lot_number', 'subject', 'price_rub_num', 'published_at', 'detail_url'] if c in top_priced.columns]\n"
            "display(top_priced[cols].head(20))"
        ),
        nbf.v4.new_markdown_cell(
            "## Вывод\n\n"
            "Проект сейчас находится в clean source sprint состоянии: старые probe/diag/generated артефакты удалены, итоговая статистика воспроизводится через `scripts/merge_sprints.py`, а правила включения новых источников закреплены в документации и тестах."
        ),
    ]

    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "source_summary": {
            "rows_after_cross_source_dedupe": summary["rows_after_cross_source_dedupe"],
            "source_counts": source_counts,
            "top_entities": entity_counts,
        },
    }
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTEBOOK_PATH.open("w", encoding="utf-8") as file:
        nbf.write(nb, file)


if __name__ == "__main__":
    build_notebook()
