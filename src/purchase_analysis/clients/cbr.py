from datetime import datetime
from io import StringIO
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from purchase_analysis.utils.text import normalize_spaces, parse_ru_decimal

USD_XML_URL = "https://www.cbr.ru/scripts/XML_dynamic.asp"
KEY_RATE_URL = "https://www.cbr.ru/hd_base/keyrate/"
INFLATION_URL = "https://www.cbr.ru/hd_base/infl/"


def create_session(timeout: int = 30) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.6",
        }
    )
    session.request_timeout = timeout
    return session


def _to_cbr_date(value: str) -> str:
    dt = datetime.strptime(value, "%d.%m.%Y")
    return dt.strftime("%d/%m/%Y")


def fetch_usd_rates(
    date_from: str,
    date_to: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> list[dict]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        USD_XML_URL,
        params={
            "date_req1": _to_cbr_date(date_from),
            "date_req2": _to_cbr_date(date_to),
            "VAL_NM_RQ": "R01235",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    rows: list[dict] = []
    for record in root.findall("Record"):
        rows.append(
            {
                "factor_date": datetime.strptime(record.attrib["Date"], "%d.%m.%Y").date().isoformat(),
                "usd_rub": parse_ru_decimal(record.findtext("Value")),
                "nominal": parse_ru_decimal(record.findtext("Nominal")),
            }
        )
    return rows


def fetch_key_rate(
    date_from: str,
    date_to: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> list[dict]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        KEY_RATE_URL,
        params={
            "UniDbQuery.Posted": "True",
            "UniDbQuery.From": date_from,
            "UniDbQuery.To": date_to,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    table = tables[0]
    table.columns = ["factor_date", "key_rate"]
    rows: list[dict] = []
    for record in table.to_dict(orient="records"):
        rate_value = parse_ru_decimal(str(record["key_rate"]))
        if rate_value is not None and rate_value > 100:
            rate_value = rate_value / 100
        rows.append(
            {
                "factor_date": datetime.strptime(
                    normalize_spaces(str(record["factor_date"])), "%d.%m.%Y"
                ).date().isoformat(),
                "key_rate": rate_value,
            }
        )
    return rows


def fetch_inflation_yoy(
    date_from: str,
    date_to: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> list[dict]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        INFLATION_URL,
        params={
            "UniDbQuery.Posted": "True",
            "UniDbQuery.From": date_from,
            "UniDbQuery.To": date_to,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    if not tables:
        return []
    table = tables[0]
    table.columns = ["month", "key_rate_month_end", "inflation_yoy_pct", "inflation_target_pct"]
    rows: list[dict] = []
    for record in table.to_dict(orient="records"):
        month_text = normalize_spaces(str(record["month"]))
        if "." not in month_text:
            continue
        month, year = month_text.split(".", 1)
        month_date = datetime(int(year), int(month), 1).date().isoformat()
        inflation = parse_ru_decimal(str(record["inflation_yoy_pct"]))
        target = parse_ru_decimal(str(record["inflation_target_pct"]))
        key_rate = parse_ru_decimal(str(record["key_rate_month_end"]))
        rows.append(
            {
                "month_date": month_date,
                "inflation_yoy_pct": inflation / 100 if inflation and inflation > 100 else inflation,
                "inflation_target_pct": target / 100 if target and target > 100 else target,
                "key_rate_month_end": key_rate / 100 if key_rate and key_rate > 100 else key_rate,
            }
        )
    return rows
