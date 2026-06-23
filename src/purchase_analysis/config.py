from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "configs"
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = ROOT_DIR / "output"
CURATED_DIR = OUTPUT_DIR / "curated"
REPORTS_DIR = OUTPUT_DIR / "reports"
DOCS_DIR = ROOT_DIR / "docs"
NOTEBOOKS_DIR = ROOT_DIR / "notebooks"


@dataclass(slots=True)
class RunConfig:
    date_from: str = "01.01.2024"
    date_to: str = "31.12.2025"
    max_pages: int = 120
    request_timeout: int = 30
    max_sberb2b_details: int = 1000
    download_documents_limit: int = 250
    max_document_size_bytes: int = 10_000_000
    max_sberb2b_api_probes: int = 25
    entity_scope_path: Path = CONFIG_DIR / "entity_scope.csv"
