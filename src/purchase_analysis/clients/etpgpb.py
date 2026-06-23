from dataclasses import dataclass, field
from typing import Any, Optional
import requests

@dataclass
class EtpgpbSearchItem:
    id: str
    registry_number: Optional[str]
    title: Optional[str]
    url: Optional[str]
    amount: Optional[str]
    stage: Optional[str]
    date_published: Optional[str]
    company_name: Optional[str]
    company_url: Optional[str]
    raw_data: dict[str, Any] = field(repr=False)


@dataclass
class EtpgpbDocument:
    title: str
    url: str
    file_size: Optional[int] = None


@dataclass
class EtpgpbProcedureDetail:
    id: str
    registry_number: Optional[str]
    url: str
    documents: list[EtpgpbDocument]
    raw_data: dict[str, Any] = field(repr=False)


class EtpgpbClient:
    """Client for ETP GPB (https://etpgpb.ru/)."""
    
    BASE_URL = "https://etpgpb.ru"
    API_URL = "https://etpgpb.ru/api/v2"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json"
        })

    def search(self, query: str, limit: int = 20) -> list[EtpgpbSearchItem]:
        """Search procedures by a query string (usually INN, OGRN, or Title)."""
        # We will fetch up to 'limit' items. ETP GPB API paginates by default.
        page = 1
        per_page = 20
        all_items = []
        
        while len(all_items) < limit:
            res = self.session.get(
                f"{self.API_URL}/procedures/",
                params={
                    "page": page,
                    "per": per_page,
                    "search": query,
                    "sort": "by_relevance"
                }
            )
            res.raise_for_status()
            data = res.json()
            
            items = data.get("data", [])
            if not items:
                break
                
            for item in items:
                attr = item.get("attributes", {})
                platform_url = attr.get("platform_url") or ""
                # Ensure URL is absolute if it starts with /
                if platform_url.startswith("/"):
                    platform_url = self.BASE_URL + platform_url
                    
                search_item = EtpgpbSearchItem(
                    id=item.get("id", ""),
                    registry_number=attr.get("registry_number"),
                    title=attr.get("title"),
                    url=platform_url,
                    amount=attr.get("amount"),
                    stage=attr.get("stage"),
                    date_published=attr.get("date_published"),
                    company_name=attr.get("company_name"),
                    company_url=attr.get("company_url"),
                    raw_data=item
                )
                all_items.append(search_item)
                
            page += 1
            # If total_count is reached, break
            total_count = data.get("meta", {}).get("total_count", 0)
            if len(all_items) >= total_count:
                break
                
        return all_items[:limit]

    def fetch_procedure_detail(self, procedure_id: str, url: str) -> EtpgpbProcedureDetail:
        """Fetch details of a procedure including documents.
        The ETP GPB API provides an endpoint for procedure details:
        /api/v2/procedures/<id>/
        """
        # For documents, they might be in the procedure detail API or a separate endpoint
        # Let's fetch the detail API first
        docs = []
        try:
            res = self.session.get(f"{self.API_URL}/procedures/{procedure_id}/")
            res.raise_for_status()
            data = res.json().get("data", {})
            attr = data.get("attributes", {})
            
            # Try to parse documents from included (JSON API spec)
            included = res.json().get("included", [])
            for inc in included:
                if inc.get("type") in ("document", "file"):
                    inc_attr = inc.get("attributes", {})
                    doc_url = inc_attr.get("url") or inc_attr.get("file_url")
                    doc_title = inc_attr.get("name") or inc_attr.get("title") or "Document"
                    if doc_url:
                        if doc_url.startswith("/"):
                            doc_url = self.BASE_URL + doc_url
                        docs.append(EtpgpbDocument(title=doc_title, url=doc_url))
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                # Some procedures (e.g. fz44) don't have details in this API.
                data = {}
                attr = {}
            else:
                raise

        detail = EtpgpbProcedureDetail(
            id=data.get("id", ""),
            registry_number=attr.get("registry_number"),
            url=url,
            documents=docs,
            raw_data=data
        )
        return detail
