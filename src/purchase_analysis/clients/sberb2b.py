from __future__ import annotations

from dataclasses import dataclass
import html
import json
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from purchase_analysis.utils.text import normalize_spaces

BASE_URL = "https://sberb2b.ru"
GOODS_ITEMS_PATH = "/request/api/{condition_id}/get-from-description-goods-items/{side}"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(slots=True)
class SberB2BPublicNeed:
    procedure_number: str
    lot_number: str
    need_id: str
    condition_id: str
    subject: str
    customer_name: str
    customer_inn: str
    status: str
    state: str
    public_request_status: str
    detail_price_rub: float | None
    published_at: str | None
    application_deadline: str | None
    method_name: str
    currency: str
    raw_need: dict


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


def is_public_need_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if not parsed.netloc.lower().endswith("sberb2b.ru"):
        return False
    return parsed.path.startswith("/needs/") or parsed.path.startswith("/request/supplier/preview/")


def fetch_public_need_page(
    url: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> str:
    session = session or create_session(timeout=timeout)
    response = _get_with_retry(session, url, timeout=timeout)
    return response.text


def _get_with_retry(
    session: requests.Session,
    url: str,
    *,
    params: dict | None = None,
    timeout: int = 30,
    attempts: int = 4,
) -> requests.Response:
    last_response: requests.Response | None = None
    for attempt in range(1, attempts + 1):
        response = session.get(url, params=params, timeout=timeout)
        last_response = response
        if response.status_code not in RETRY_STATUS_CODES:
            response.raise_for_status()
            return response
        if attempt < attempts:
            time.sleep(1.5 * attempt)
    assert last_response is not None
    last_response.raise_for_status()
    return last_response


def _as_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_text(*values: object) -> str:
    for value in values:
        normalized = normalize_spaces("" if value is None else str(value))
        if normalized:
            return normalized
    return ""


def extract_need_json(html_text: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")
    tag = soup.find("need-for-public-page")
    if tag is None:
        raise ValueError("Could not find SberB2B need-for-public-page component")
    raw_need = tag.get(":need") or tag.get("need")
    if not raw_need:
        raise ValueError("Could not find embedded SberB2B public need JSON")
    return json.loads(html.unescape(raw_need))


def parse_public_need(html_text: str) -> SberB2BPublicNeed:
    need = extract_need_json(html_text)
    condition = need.get("need_condition") or {}
    customer = need.get("customer") or {}
    condition_id = _first_text(condition.get("id"))
    need_id = _first_text(need.get("id"))
    return SberB2BPublicNeed(
        procedure_number=_first_text(need.get("number")),
        lot_number="1",
        need_id=need_id,
        condition_id=condition_id,
        subject=_first_text(need.get("name")),
        customer_name=_first_text(customer.get("short_name"), customer.get("name")),
        customer_inn=_first_text(customer.get("inn")),
        status=_first_text(need.get("status")),
        state=_first_text(need.get("state")),
        public_request_status=_first_text(need.get("public_request_status")),
        detail_price_rub=_as_float(condition.get("total_price")),
        published_at=_first_text(need.get("created_at")) or None,
        application_deadline=_first_text(
            need.get("send_kp_until_at"),
            condition.get("offer_limitation_validity_from_datetime"),
        )
        or None,
        method_name="SberB2B public request",
        currency="RUB",
        raw_need=need,
    )


def public_need_to_detail_dict(need: SberB2BPublicNeed) -> dict:
    return {
        "procedure_number": need.procedure_number,
        "lot_number": need.lot_number,
        "published_at": need.published_at,
        "application_deadline": need.application_deadline,
        "detail_price_rub": need.detail_price_rub,
        "method_name": need.method_name,
        "currency": need.currency,
        "sberb2b_need_id": need.need_id,
        "sberb2b_condition_id": need.condition_id,
        "sberb2b_status": need.status,
        "sberb2b_state": need.state,
        "sberb2b_public_request_status": need.public_request_status,
        "customer_name": need.customer_name,
        "customer_inn": need.customer_inn,
    }


def fetch_goods_items_page(
    condition_id: str,
    page: int = 1,
    limit: int = 100,
    side: str = "customer",
    session: requests.Session | None = None,
    timeout: int = 30,
) -> dict:
    session = session or create_session(timeout=timeout)
    url = urljoin(BASE_URL, GOODS_ITEMS_PATH.format(condition_id=condition_id, side=side))
    response = _get_with_retry(
        session,
        url,
        params={"page": page, "limit": limit},
        timeout=timeout,
    )
    return response.json()


def fetch_all_goods_items(
    condition_id: str,
    side: str = "customer",
    page_size: int = 100,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> dict:
    session = session or create_session(timeout=timeout)
    collected: list[dict] = []
    total = 0
    page = 1
    while True:
        payload = fetch_goods_items_page(
            condition_id=condition_id,
            page=page,
            limit=page_size,
            side=side,
            session=session,
            timeout=timeout,
        )
        data = payload.get("data") or {}
        goods = data.get("goods") or []
        collected.extend(goods)
        total = int(data.get("total") or len(collected))
        if len(collected) >= total or not goods:
            return {
                "success": payload.get("success", True),
                "data": {
                    "page": 1,
                    "limit": page_size,
                    "total": total,
                    "goods": collected,
                },
            }
        page += 1


def goods_payload_to_item_rows(
    payload: dict,
    public_need: SberB2BPublicNeed,
    source_system: str = "sberbank_ast",
    entity_name: str = "",
    focus_category: str = "",
) -> list[dict]:
    data = payload.get("data") or {}
    goods = data.get("goods") or []
    rows: list[dict] = []
    for index, item in enumerate(goods, start=1):
        unit_price = _as_float(item.get("c_priceWithTax"))
        quantity = _as_float(item.get("c_count"))
        line_total = unit_price * quantity if unit_price is not None and quantity is not None else None
        rows.append(
            {
                "source_system": source_system,
                "entity_name": entity_name,
                "procedure_number": public_need.procedure_number,
                "lot_number": public_need.lot_number,
                "line_no": index,
                "item_id_external": _first_text(item.get("c_id")),
                "item_name": _first_text(item.get("c_description")),
                "item_description": _first_text(item.get("c_comment")),
                "okpd_code": _first_text(item.get("c_okpd2Code")),
                "okpd_name": _first_text(item.get("c_okpd2Name")),
                "quantity": quantity,
                "unit": _first_text(item.get("c_unitName")),
                "okei_code": _first_text(item.get("c_unitOkeiCode")),
                "unit_price_rub": unit_price,
                "line_total_rub": line_total,
                "price_rub": line_total,
                "focus_category": focus_category,
                "sberb2b_need_id": public_need.need_id,
                "sberb2b_condition_id": public_need.condition_id,
                "unit_price_source": "sberb2b_goods_api",
            }
        )
    return rows


def iter_public_documents(need_payload: dict) -> list[dict]:
    condition = need_payload.get("need_condition") or {}
    candidates: list[dict] = []
    for key in ["medias", "attachments_files", "interaction_files"]:
        values = condition.get(key) or []
        if isinstance(values, list):
            candidates.extend(item for item in values if isinstance(item, dict))

    rows: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        file_payload = item.get("file") if isinstance(item.get("file"), dict) else item
        web_path = _first_text(file_payload.get("web_path"), item.get("web_path"))
        stored_name = _first_text(file_payload.get("name"), item.get("name"))
        if not web_path or not stored_name:
            continue
        document_url = urljoin(BASE_URL, f"{web_path}{stored_name}")
        original_name = _first_text(
            file_payload.get("original_name"),
            item.get("original_name"),
            stored_name,
        )
        key = _first_text(file_payload.get("file_hash"), document_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "document_name": original_name,
                "document_url": document_url,
                "document_storage_name": stored_name,
                "document_mime_type": _first_text(file_payload.get("type"), item.get("type")),
                "document_size_bytes": int(file_payload.get("size") or item.get("size") or 0),
                "document_hash": _first_text(file_payload.get("file_hash")),
                "is_available": True,
            }
        )
    return rows


def extract_public_participants(public_need: SberB2BPublicNeed) -> list[dict]:
    need = public_need.raw_need
    rows: list[dict] = []

    def add(role: str, payload: dict | None, price: object = None) -> None:
        if not isinstance(payload, dict):
            return
        name = _first_text(payload.get("short_name"), payload.get("name"), payload.get("supplier_short_name"))
        inn = _first_text(payload.get("inn"))
        company_id = _first_text(payload.get("id"))
        if not any([name, inn, company_id]):
            return
        rows.append(
            {
                "source_system": "sberbank_ast",
                "procedure_number": public_need.procedure_number,
                "lot_number": public_need.lot_number,
                "participant_role": role,
                "participant_name": name,
                "participant_inn": inn,
                "participant_external_id": company_id,
                "offer_price_rub": _as_float(price),
                "is_winner": role == "winner",
                "evidence_source": "sberb2b_public_need_json",
            }
        )

    add("winner", need.get("supplier"))
    deal = need.get("deal") if isinstance(need.get("deal"), dict) else {}
    add("winner", deal.get("supplier") if isinstance(deal, dict) else None)
    auction = need.get("auction") if isinstance(need.get("auction"), dict) else {}
    best_offer = auction.get("best_offer_condition") if isinstance(auction, dict) else {}
    if isinstance(best_offer, dict):
        add(
            "winner",
            {
                "short_name": best_offer.get("supplier_short_name"),
                "id": best_offer.get("supplier_id"),
            },
            price=best_offer.get("total_price"),
        )

    for key in ["suppliers", "invited_suppliers", "selected_suppliers"]:
        values = need.get(key) or []
        if isinstance(values, list):
            for supplier in values:
                add("invited_supplier", supplier)

    unique_rows: list[dict] = []
    seen: set[tuple] = set()
    for row in rows:
        key = (
            row["procedure_number"],
            row["participant_role"],
            row["participant_name"],
            row["participant_inn"],
            row["participant_external_id"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows
