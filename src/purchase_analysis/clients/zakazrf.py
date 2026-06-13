from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from purchase_analysis.utils.text import normalize_spaces, parse_ru_datetime, parse_ru_decimal

BASE_URL = "https://etp.zakazrf.ru"
REGISTRY_URL = f"{BASE_URL}/NotificationEx"
CUSTOMER_DIALOG_URL = f"{BASE_URL}/Customer"
DEFAULT_NOTIFICATION_PARAMS = {
    "Filter": "1",
    "SelectedTabPage": "ALL",
    "IsConstructionProcurement": "0",
    "IsGroup": "0",
    "QuantityUndefined": "0",
    "ContractBlocked": "0",
    "AsPublic": "0",
}


@dataclass(slots=True)
class ZakazRfCustomerDialogContext:
    main_page_id: str
    dialog_page_id: str
    dialog_url: str
    page_size: int
    serializable_table: str
    serializable_table_key: str


@dataclass(slots=True)
class ZakazRfCustomerCandidate:
    internal_id: str
    full_name: str
    inn: str
    role_name: str
    registration_date: str
    address: str


@dataclass(slots=True)
class ZakazRfSearchItem:
    source_system: str
    platform_section: str
    entity_name: str
    customer_query: str
    procedure_number: str
    lot_number: str
    subject: str
    customer_name: str
    region: str
    status: str
    tender_type: str
    price_rub: float | None
    deadline_at: str | None
    detail_url: str
    tags: str
    published_at: str | None
    application_deadline: str | None
    method_name: str
    currency: str
    organizer_name: str
    contact_person: str
    federal_law: str


def create_session(timeout: int = 30) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.6",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    session.request_timeout = timeout
    return session


def fetch_registry_page(
    *,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> str:
    session = session or create_session(timeout=timeout)
    response = session.get(REGISTRY_URL, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_main_page_id(html_text: str) -> str:
    match = re.search(r'name="_orm_PageID"[^>]*value="([A-F0-9]+)"', html_text)
    if not match:
        raise ValueError("Could not find ZakazRF main _orm_PageID")
    return match.group(1)


def fetch_customer_dialog(
    main_page_id: str,
    *,
    dialog_id: str = "dialog_probe",
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        CUSTOMER_DIALOG_URL,
        params={
            "IsPartialView": "1",
            "_orm_DialogMode": "select",
            "_orm_IdDialog": dialog_id,
            "pageId": main_page_id,
            "_orm_ResultMode": "inputs",
            "IdField": "Filter_Customer",
            "NameField": "Filter_Customer_editView",
            "DisplayPath": "FullName",
            "_ORM_IsFilterSelect": "1",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text, response.url


def parse_customer_dialog_context(
    html_text: str,
    *,
    main_page_id: str,
    dialog_url: str = CUSTOMER_DIALOG_URL,
) -> ZakazRfCustomerDialogContext:
    soup = BeautifulSoup(html_text, "lxml")
    dialog_page_id = _input_value(soup, "_orm_PageID")
    if not dialog_page_id:
        raise ValueError("Could not find ZakazRF customer dialog _orm_PageID")
    page_size_value = _input_value(soup, f"PageSize{dialog_page_id}") or "20"
    return ZakazRfCustomerDialogContext(
        main_page_id=main_page_id,
        dialog_page_id=dialog_page_id,
        dialog_url=dialog_url,
        page_size=int(page_size_value),
        serializable_table=_input_value(soup, "_orm_SerializableTable"),
        serializable_table_key=_input_value(soup, "_orm_SerializableTableKey"),
    )


def _input_value(soup: BeautifulSoup, name: str) -> str:
    element = soup.select_one(f'input[name="{name}"]')
    return element.get("value", "") if element else ""


def build_customer_search_payload(
    context: ZakazRfCustomerDialogContext,
    *,
    inn: str = "",
    full_name: str = "",
) -> dict[str, str]:
    page_id = context.dialog_page_id
    return {
        "_orm_PageID": page_id,
        "_orm_PageURL": context.dialog_url,
        "_orm_collaps_state": "",
        "AutoSaveField": "",
        "ORM_Chgange_Fields": "",
        "_orm_ClientType": "Browser",
        f"SortColumn{page_id}": "",
        f"SortColumnDesc{page_id}": "0",
        f"PageNumber{page_id}": "1",
        f"PageSize{page_id}": str(context.page_size),
        f"PageListViewMode{page_id}": "0",
        "TableSelectedItems": "",
        f"IncludeColumns{page_id}": "",
        "FilterSelect.SelectedTabPage": "all",
        "FilterSelect.ID": "",
        "FilterSelect.RegNum": "",
        "FilterSelect.FullName": normalize_spaces(full_name),
        "FilterSelect.INN": normalize_spaces(inn),
        "FilterSelect.OGRN": "",
        "FilterSelect.KPP": "",
        "FilterSelect.RegDateFrom": "",
        "FilterSelect.RegDateTo": "",
        "FilterSelect.CustomerRole": "",
        "_orm_SerializableTable": context.serializable_table,
        "_orm_SerializableTableKey": context.serializable_table_key,
    }


def search_customer_candidates(
    context: ZakazRfCustomerDialogContext,
    *,
    inn: str = "",
    full_name: str = "",
    dialog_id: str = "dialog_probe",
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    session = session or create_session(timeout=timeout)
    url = (
        f"{CUSTOMER_DIALOG_URL}?IsPartialView=1&_orm_DialogMode=select"
        f"&_orm_IdDialog={dialog_id}&pageId={context.main_page_id}"
        "&_orm_ResultMode=inputs&IdField=Filter_Customer"
        "&NameField=Filter_Customer_editView&DisplayPath=FullName"
        "&_ORM_IsFilterSelect=1&IsTableContentOnlyRequest=1&orm_update_request="
    )
    response = session.post(
        url,
        data=build_customer_search_payload(context, inn=inn, full_name=full_name),
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text, response.url


def parse_customer_candidates(html_text: str) -> list[ZakazRfCustomerCandidate]:
    soup = BeautifulSoup(html_text, "lxml")
    table = soup.select_one("table.reporttable")
    if table is None:
        return []

    row_mappings = re.findall(
        r"SelectRow\d+_[A-F0-9]+\(\)\{\s*\$\('#form[A-F0-9]+'\)\.find\('#Filter_Customer'\)"
        r"\.val\(aposDecode\('([^']*)'\)\);\s*\$\('#form[A-F0-9]+'\)"
        r"\.find\('#Filter_Customer_editView'\)\.val\(aposDecode\('([^']*)'\)\);",
        html_text,
        flags=re.S,
    )

    table_rows = table.select("tr")[1:]
    candidates: list[ZakazRfCustomerCandidate] = []
    for row, mapping in zip(table_rows, row_mappings, strict=False):
        cells = [normalize_spaces(cell.get_text(" ", strip=True)) for cell in row.select("td")]
        if len(cells) < 5:
            continue
        internal_id, full_name = mapping
        candidates.append(
            ZakazRfCustomerCandidate(
                internal_id=normalize_spaces(internal_id),
                full_name=normalize_spaces(full_name),
                inn=cells[1],
                role_name=cells[2],
                registration_date=cells[3],
                address=cells[4],
            )
        )
    return candidates


def fetch_notifications(
    customer_id: str,
    *,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    session = session or create_session(timeout=timeout)
    params = dict(DEFAULT_NOTIFICATION_PARAMS)
    params["Customer"] = normalize_spaces(customer_id)
    response = session.get(REGISTRY_URL, params=params, timeout=timeout)
    response.raise_for_status()
    return response.text, response.url


def parse_total_rows(html_text: str) -> int:
    match = re.search(r'name="TotalRows[A-F0-9]+"[^>]*value="(\d+)"', html_text)
    if not match:
        return 0
    return int(match.group(1))


def _clean_datetime_text(value: str) -> str:
    cleaned = normalize_spaces(value)
    cleaned = re.sub(r"\s*\(\+\d{2}:\d{2}\)$", "", cleaned)
    return normalize_spaces(cleaned)


def parse_notification_rows(
    html_text: str,
    *,
    entity_name: str,
    customer_query: str,
) -> list[ZakazRfSearchItem]:
    soup = BeautifulSoup(html_text, "lxml")
    table = soup.select_one("table.reporttable")
    if table is None:
        return []

    items: list[ZakazRfSearchItem] = []
    for row in table.select("tr")[1:]:
        cells = row.select("td")
        if len(cells) < 15:
            continue
        detail_link = row.select_one('td.RowActionRaw a[href]') or row.select_one('a[href*="/NotificationEx/id/"]')
        published = parse_ru_datetime(_clean_datetime_text(cells[9].get_text(" ", strip=True)))
        deadline = parse_ru_datetime(_clean_datetime_text(cells[11].get_text(" ", strip=True)))
        items.append(
            ZakazRfSearchItem(
                source_system="zakazrf",
                platform_section=normalize_spaces(cells[0].get_text(" ", strip=True)),
                entity_name=entity_name,
                customer_query=customer_query,
                procedure_number=normalize_spaces(cells[1].get_text(" ", strip=True)),
                lot_number="1",
                subject=normalize_spaces(cells[4].get_text(" ", strip=True)),
                customer_name=normalize_spaces(cells[7].get_text(" ", strip=True)),
                region="",
                status=normalize_spaces(cells[2].get_text(" ", strip=True)),
                tender_type=normalize_spaces(cells[3].get_text(" ", strip=True)),
                price_rub=parse_ru_decimal(cells[5].get_text(" ", strip=True)),
                deadline_at=deadline.isoformat() if deadline else None,
                detail_url=urljoin(BASE_URL, detail_link.get("href", "")) if detail_link else "",
                tags=f"law={normalize_spaces(cells[0].get_text(' ', strip=True))}",
                published_at=published.isoformat() if published else None,
                application_deadline=deadline.isoformat() if deadline else None,
                method_name=normalize_spaces(cells[3].get_text(" ", strip=True)),
                currency="RUB",
                organizer_name=normalize_spaces(cells[6].get_text(" ", strip=True)),
                contact_person=normalize_spaces(cells[8].get_text(" ", strip=True)),
                federal_law=normalize_spaces(cells[0].get_text(" ", strip=True)),
            )
        )
    return items


def customer_candidate_to_dict(item: ZakazRfCustomerCandidate) -> dict:
    return asdict(item)


def search_item_to_dict(item: ZakazRfSearchItem) -> dict:
    return asdict(item)
