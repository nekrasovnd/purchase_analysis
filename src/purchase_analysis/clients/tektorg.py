from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import xml.etree.ElementTree as ET

import requests

from purchase_analysis.utils.text import normalize_spaces, parse_ru_decimal


WSDL_URL = "https://api.tektorg.ru/procedures/wsdl"
SOAP_URL = "https://api.tektorg.ru/procedures/soap"
SOAP_ACTION = "urn:procedures"
SOAP_NS = "https://api.tektorg.ru/procedures/soap"


@dataclass(slots=True)
class TektorgSearchItem:
    source_system: str
    platform_section: str
    entity_name: str
    customer_query: str
    procedure_number: str
    lot_number: str
    subject: str
    customer_name: str
    customer_inn: str
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
    organizer_inn: str


@dataclass(slots=True)
class TektorgSearchResponse:
    total_procedures: int = 0
    current_page: int = 0
    total_pages: int = 0
    limit_per_page: int = 0
    section_name: str = ""
    section_code: str = ""
    fault_string: str = ""
    items: list[TektorgSearchItem] = field(default_factory=list)


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


def build_request_xml(
    *,
    customer_inn: str | None = None,
    organizer_inn: str | None = None,
    registry_number: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    limit_page: int = 100,
) -> str:
    fields: list[str] = []
    if start_date:
        fields.append(f'<startDate xsi:type="xsd:dateTime">{normalize_spaces(start_date)}</startDate>')
    if end_date:
        fields.append(f'<endDate xsi:type="xsd:dateTime">{normalize_spaces(end_date)}</endDate>')
    if registry_number:
        fields.append(
            f'<registryNumber xsi:type="xsd:string">{normalize_spaces(registry_number)}</registryNumber>'
        )
    if customer_inn:
        fields.append(f'<customerINN xsi:type="xsd:string">{normalize_spaces(customer_inn)}</customerINN>')
    if organizer_inn:
        fields.append(
            f'<organizerINN xsi:type="xsd:string">{normalize_spaces(organizer_inn)}</organizerINN>'
        )
    fields.append(f'<limitPage xsi:type="xsd:int">{int(limit_page)}</limitPage>')
    fields.append(f'<page xsi:type="xsd:int">{int(page)}</page>')

    body = "\n        ".join(fields)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<SOAP-ENV:Envelope '
        'xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        f'xmlns:tns="{SOAP_NS}">\n'
        "  <SOAP-ENV:Body>\n"
        "    <tns:procedures>\n"
        '      <symbol xsi:type="tns:exportRequestType">\n'
        f"        {body}\n"
        "      </symbol>\n"
        "    </tns:procedures>\n"
        "  </SOAP-ENV:Body>\n"
        "</SOAP-ENV:Envelope>"
    )


def fetch_procedures(
    request_xml: str,
    *,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> str:
    session = session or create_session(timeout=timeout)
    response = session.post(
        SOAP_URL,
        data=request_xml.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": SOAP_ACTION,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    if ":" in tag:
        return tag.split(":", 1)[1]
    return tag


def _find_first(node: ET.Element | None, name: str) -> ET.Element | None:
    if node is None:
        return None
    for child in list(node):
        if _local_name(child.tag) == name:
            return child
    return None


def _find_all(node: ET.Element | None, name: str) -> list[ET.Element]:
    if node is None:
        return []
    return [child for child in list(node) if _local_name(child.tag) == name]


def _find_text(node: ET.Element | None, name: str) -> str:
    child = _find_first(node, name)
    if child is None:
        return ""
    return normalize_spaces("".join(child.itertext()))


def parse_fault(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    for node in root.iter():
        if _local_name(node.tag) != "Fault":
            continue
        return _find_text(node, "faultstring")
    return ""


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _procedure_items(
    procedure_node: ET.Element,
    *,
    section_name: str,
    section_code: str,
    entity_name: str,
    customer_query: str,
) -> list[TektorgSearchItem]:
    procedure_number = _find_text(procedure_node, "registryNumber") or _find_text(procedure_node, "remoteId")
    procedure_title = _find_text(procedure_node, "title")
    published_at = _find_text(procedure_node, "datePublished") or None
    application_deadline = _find_text(procedure_node, "dateEndRegistration") or None
    method_name = _find_text(_find_first(procedure_node, "procedureType"), "title")
    organizer_node = _find_first(procedure_node, "organizer")
    organizer_name = _find_text(organizer_node, "fullName")
    organizer_inn = _find_text(organizer_node, "inn")
    region = _find_text(_find_first(organizer_node, "legal"), "region") or _find_text(
        _find_first(organizer_node, "postal"),
        "region",
    )
    currency = _find_text(procedure_node, "currency") or "RUB"
    detail_url = _find_text(procedure_node, "url_to_showcase")

    lots_node = _find_first(procedure_node, "lots")
    lot_nodes = _find_all(lots_node, "lot")
    if not lot_nodes:
        lot_nodes = [procedure_node]

    items: list[TektorgSearchItem] = []
    for lot_node in lot_nodes:
        customers_node = _find_first(lot_node, "customers")
        customer_names: list[str] = []
        customer_inns: list[str] = []
        for customer_node in _find_all(customers_node, "customer"):
            customer_name = _find_text(customer_node, "fullName")
            customer_inn = _find_text(customer_node, "inn")
            if customer_name and customer_name not in customer_names:
                customer_names.append(customer_name)
            if customer_inn and customer_inn not in customer_inns:
                customer_inns.append(customer_inn)

        items.append(
            TektorgSearchItem(
                source_system="tektorg",
                platform_section=section_name or section_code,
                entity_name=entity_name,
                customer_query=customer_query,
                procedure_number=procedure_number,
                lot_number=_find_text(lot_node, "number") or "1",
                subject=_find_text(lot_node, "subject") or procedure_title,
                customer_name=" | ".join(customer_names),
                customer_inn=" | ".join(customer_inns),
                region=region,
                status=_find_text(lot_node, "status"),
                tender_type=section_code,
                price_rub=parse_ru_decimal(_find_text(lot_node, "startPrice")),
                deadline_at=_find_text(lot_node, "dateEndRegistration") or application_deadline,
                detail_url=detail_url,
                tags=section_code,
                published_at=published_at,
                application_deadline=_find_text(lot_node, "dateEndRegistration") or application_deadline,
                method_name=method_name,
                currency=currency,
                organizer_name=organizer_name,
                organizer_inn=organizer_inn,
            )
        )
    return items


def parse_search_response(
    xml_text: str,
    *,
    entity_name: str,
    customer_query: str,
) -> TektorgSearchResponse:
    root = ET.fromstring(xml_text)
    fault_string = parse_fault(xml_text)
    if fault_string:
        return TektorgSearchResponse(fault_string=fault_string)

    response_node: ET.Element | None = None
    for node in root.iter():
        if _local_name(node.tag) == "proceduresResponse":
            response_node = node
            break
    if response_node is None:
        return TektorgSearchResponse()

    section_name = _find_text(response_node, "sectionName")
    section_code = _find_text(response_node, "sectionCode")
    procedures_container = _find_first(response_node, "procedures")
    items: list[TektorgSearchItem] = []
    for procedure_node in _find_all(procedures_container, "procedure"):
        items.extend(
            _procedure_items(
                procedure_node,
                section_name=section_name,
                section_code=section_code,
                entity_name=entity_name,
                customer_query=customer_query,
            )
        )

    return TektorgSearchResponse(
        total_procedures=_parse_int(_find_text(response_node, "totalProcedures")),
        current_page=_parse_int(_find_text(response_node, "currentPage")),
        total_pages=_parse_int(_find_text(response_node, "totalPage")),
        limit_per_page=_parse_int(_find_text(response_node, "limitProceduresInPage")),
        section_name=section_name,
        section_code=section_code,
        items=items,
    )


def parse_total(xml_text: str) -> int:
    return parse_search_response(
        xml_text,
        entity_name="",
        customer_query="",
    ).total_procedures


def search_item_to_dict(item: TektorgSearchItem) -> dict:
    return asdict(item)
