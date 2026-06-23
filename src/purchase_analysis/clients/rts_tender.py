import re
from dataclasses import dataclass
from typing import List

from bs4 import BeautifulSoup

from purchase_analysis.clients.browser_session import BrowserSession


INN_LABEL = "\u0418\u041d\u041d"
KPP_LABEL = "\u041a\u041f\u041f"
PURCHASE_LABEL = "\u0417\u0430\u043a\u0443\u043f\u043a\u0430"
NOTICE_LABEL = "\u0418\u0437\u0432\u0435\u0449\u0435\u043d\u0438\u0435"
DETAILS_LABEL = "\u043f\u043e\u0434\u0440\u043e\u0431\u043d\u0435\u0435"
INITIAL_PRICE_LABEL = "\u041d\u0410\u0427\u0410\u041b\u042c\u041d\u0410\u042f \u0426\u0415\u041d\u0410"
STATUS_LABEL = "\u0421\u0422\u0410\u0422\u0423\u0421"
PUBLISHED_LABEL = "\u041e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d\u043e:"
CUSTOMER_LABEL = "\u0417\u0410\u041a\u0410\u0417\u0427\u0418\u041a"
ORGANIZER_LABEL = "\u041e\u0420\u0413\u0410\u041d\u0418\u0417\u0410\u0422\u041e\u0420"


@dataclass
class RtsTenderDocument:
    title: str
    url: str


@dataclass
class RtsTenderSearchItem:
    id: str
    procedure_number: str
    title: str
    url: str
    amount: str
    stage: str
    date_published: str
    company_name: str
    company_inn: str
    organizer_name: str
    organizer_inn: str
    raw_html: str


@dataclass
class RtsTenderProcedureDetail:
    id: str
    procedure_number: str
    url: str
    documents: List[RtsTenderDocument]
    raw_html: str


class RtsTenderClient:
    BASE_URL = "https://www.rts-tender.ru"

    def __init__(self, session: BrowserSession):
        self.session = session

    def _extract_inn(self, text: str) -> str:
        match = re.search(fr"{INN_LABEL}[^\d]*(\d{{10,12}})", text)
        if match:
            return match.group(1)
        return ""

    def _extract_party(self, text_parts: list[str], label: str) -> tuple[str, str]:
        label = label.upper()
        for index, part in enumerate(text_parts):
            if part.upper() != label:
                continue

            name = ""
            inn = ""
            for candidate in text_parts[index + 1 : index + 5]:
                if candidate.upper() in {INN_LABEL, KPP_LABEL}:
                    break
                if candidate.startswith("("):
                    continue
                name = candidate
                break

            for probe_index in range(index + 1, min(index + 12, len(text_parts) - 1)):
                if text_parts[probe_index].upper() == INN_LABEL:
                    match = re.search(r"\d{10,12}", text_parts[probe_index + 1])
                    if match:
                        inn = match.group(0)
                    break
            return name, inn

        return "", ""

    def _value_after(self, text_parts: list[str], label: str, pieces: int = 1) -> str:
        label = label.upper()
        for index, part in enumerate(text_parts):
            if part.upper() == label:
                values = text_parts[index + 1 : index + 1 + pieces]
                return " ".join(values).strip()
        return ""

    def search(self, query: str) -> List[RtsTenderSearchItem]:
        page = self.session._page

        page.goto(f"{self.BASE_URL}/poisk", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        page.fill(".search__text", query)
        page.click(".mainButtonSearch")

        try:
            page.wait_for_selector(".card-item, .note-warning", timeout=15000)
        except Exception:
            return []

        page.wait_for_timeout(2000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all(lambda tag: tag.name == "div" and "card-item" in tag.get("class", []))

        items = []
        for card in cards:
            text_parts = [
                text.strip()
                for text in card.get_text(" | ", strip=True).split(" | ")
                if text.strip()
            ]
            full_text = " ".join(text_parts)

            url = ""
            title = PURCHASE_LABEL
            procedure_number = ""

            for anchor in card.find_all("a"):
                href = anchor.get("href", "")
                if href and "/poisk/id/" in href:
                    url = self.BASE_URL + href
                    title_elem = card.find(string=re.compile(fr"{PURCHASE_LABEL} \u2116|{NOTICE_LABEL} \u2116"))
                    if title_elem:
                        procedure_number = title_elem.strip()
                    break

            if not url:
                for anchor in card.find_all("a"):
                    if anchor.text.strip().lower() == DETAILS_LABEL and "id" in anchor.get("href", ""):
                        url = self.BASE_URL + anchor.get("href")

            if procedure_number and procedure_number in text_parts:
                procedure_index = text_parts.index(procedure_number)
                if procedure_index + 1 < len(text_parts):
                    title = text_parts[procedure_index + 1]

            amount = ""
            amount_match = re.search(
                fr"{INITIAL_PRICE_LABEL}\s*([\d\s\xa0,]+)",
                full_text,
                re.IGNORECASE,
            )
            if amount_match:
                amount = amount_match.group(1).strip()

            customer_name, customer_inn = self._extract_party(text_parts, CUSTOMER_LABEL)
            organizer_name, organizer_inn = self._extract_party(text_parts, ORGANIZER_LABEL)
            if not customer_inn:
                customer_inn = self._extract_inn(full_text)

            items.append(
                RtsTenderSearchItem(
                    id=procedure_number,
                    procedure_number=procedure_number,
                    title=title,
                    url=url,
                    amount=amount,
                    stage=self._value_after(text_parts, STATUS_LABEL) or "Active",
                    date_published=self._value_after(text_parts, PUBLISHED_LABEL, pieces=2),
                    company_name=customer_name,
                    company_inn=customer_inn,
                    organizer_name=organizer_name,
                    organizer_inn=organizer_inn,
                    raw_html=str(card),
                )
            )

        return items

    def fetch_procedure_detail(self, url: str) -> RtsTenderProcedureDetail:
        # RTS-Tender redirects to many sub-platforms; generic document parsing is skipped for now.
        return RtsTenderProcedureDetail(
            id="",
            procedure_number="",
            url=url,
            documents=[],
            raw_html="",
        )
