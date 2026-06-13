from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from purchase_analysis.utils.text import normalize_spaces


@dataclass(slots=True)
class DocumentExtraction:
    text: str
    extraction_method: str
    text_chars: int
    ocr_required: bool
    pii_findings_count: int


EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-zА-Яа-я]{2,}")
PHONE_RE = re.compile(r"(?:\+7|8)\s*(?:\(?\d{3}\)?[\s-]*)\d{3}[\s-]*\d{2}[\s-]*\d{2}")
PASSPORT_RE = re.compile(r"\b\d{2}\s?\d{2}\s?\d{6}\b")
SNILS_RE = re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b")


def mask_pii(text: str) -> tuple[str, int]:
    masked = text
    count = 0
    for regex, replacement in [
        (EMAIL_RE, "[EMAIL]"),
        (PHONE_RE, "[PHONE]"),
        (PASSPORT_RE, "[PASSPORT]"),
        (SNILS_RE, "[SNILS]"),
    ]:
        masked, replacements = regex.subn(replacement, masked)
        count += replacements
    return masked, count


def _extract_docx_text(path: Path) -> str:
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    parts: list[str] = []
    with ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.startswith("word/") and name.endswith(".xml")]
        for name in sorted(names):
            if name not in {"word/document.xml", "word/footnotes.xml", "word/endnotes.xml"}:
                continue
            root = ET.fromstring(archive.read(name))
            for paragraph in root.findall(".//w:p", namespaces):
                texts = [node.text or "" for node in paragraph.findall(".//w:t", namespaces)]
                line = normalize_spaces("".join(texts))
                if line:
                    parts.append(line)
    return "\n".join(parts)


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            parts.append(page_text)
    return "\n".join(parts)


def extract_text_from_document(path: Path, mime_type: str = "") -> DocumentExtraction:
    suffix = path.suffix.lower()
    raw_text = ""
    method = "unsupported"
    ocr_required = False

    try:
        if (
            suffix == ".docx"
            or "wordprocessingml.document" in mime_type
            or path.read_bytes()[:4] == b"PK\x03\x04"
        ):
            raw_text = _extract_docx_text(path)
            method = "docx_xml"
        elif suffix == ".pdf" or "pdf" in mime_type or path.read_bytes()[:4] == b"%PDF":
            raw_text = _extract_pdf_text(path)
            method = "pdf_text"
            ocr_required = len(normalize_spaces(raw_text)) < 50
    except (BadZipFile, ET.ParseError, OSError):
        raw_text = ""
        method = "extract_error"

    masked_text, pii_count = mask_pii(raw_text)
    normalized = normalize_spaces(masked_text)
    if method == "unsupported":
        ocr_required = False
    return DocumentExtraction(
        text=normalized,
        extraction_method=method,
        text_chars=len(normalized),
        ocr_required=ocr_required,
        pii_findings_count=pii_count,
    )
