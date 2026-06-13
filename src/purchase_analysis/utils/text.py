import html
import re
from datetime import datetime


def normalize_spaces(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def html_unescape(value: str | None) -> str:
    return html.unescape(value or "")


def parse_ru_decimal(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = normalize_spaces(value)
    cleaned = re.sub(r"[^\d,.\-]", "", cleaned)
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", ".")
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_ru_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = normalize_spaces(value)
    for fmt in (
        "%d.%m.%Y",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%y",
        "%d.%m.%y %H:%M",
        "%d.%m.%y %H:%M:%S",
    ):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    match = re.search(r"(\d{2}\.\d{2}\.\d{2,4})", cleaned)
    if match:
        candidate = match.group(1)
        fmt = "%d.%m.%Y" if len(candidate.split(".")[-1]) == 4 else "%d.%m.%y"
        return datetime.strptime(candidate, fmt)
    return None


def safe_slug(value: str) -> str:
    normalized = normalize_spaces(value).lower()
    normalized = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE)
    normalized = normalized.replace("_", "-").strip("-")
    return normalized or "unknown"


def token_category(*parts: str | None) -> str:
    haystack = normalize_spaces(" ".join("" if part is None else str(part) for part in parts)).lower()
    rules = {
        "Telecom & Devices": [
            "\u0442\u0435\u043b\u0435\u043a\u043e\u043c",
            "\u0441\u043c\u0430\u0440\u0442\u0444\u043e\u043d",
            "\u0442\u0435\u043b\u0435\u0444\u043e\u043d",
            "\u0438\u043d\u0442\u0435\u0440\u043d\u0435\u0442",
            "\u0441\u0432\u044f\u0437",
            "sim",
            "gps",
            "gsm",
            "\u0442\u0440\u0435\u043a\u0435\u0440",
            "\u043d\u0430\u0432\u0438\u0433\u0430\u0446",
            "\u0440\u043e\u0443\u0442\u0435\u0440",
            "\u043c\u043e\u0434\u0435\u043c",
            "infinix",
            "iphone",
            "galaxy",
            "honor",
            "vertex",
        ],
        "Software & Cloud": [
            "\u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c",
            "\u043b\u0438\u0446\u0435\u043d\u0437",
            "server",
            "cloud",
            "saas",
            "\u0431\u0434",
            "\u0441\u0438\u0441\u0442\u0435\u043c\u0430",
            "\u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445",
        ],
        "Infrastructure": [
            "\u0441\u0442\u0440\u043e\u0438\u0442",
            "\u0440\u0435\u043c\u043e\u043d\u0442",
            "\u043c\u043e\u043d\u0442\u0430\u0436",
            "\u043a\u0430\u0431\u0435\u043b\u044c",
            "\u0438\u043d\u0436\u0435\u043d\u0435\u0440\u043d",
            "\u0441\u043c\u0435\u0442",
        ],
        "Security": [
            "\u0431\u0435\u0437\u043e\u043f\u0430\u0441",
            "\u043e\u0445\u0440\u0430\u043d\u0430",
            "\u043a\u043e\u043d\u0442\u0440\u043e\u043b\u044c \u0434\u043e\u0441\u0442\u0443\u043f\u0430",
            "firewall",
        ],
        "Logistics": [
            "\u0434\u043e\u0441\u0442\u0430\u0432",
            "\u043b\u043e\u0433\u0438\u0441\u0442",
            "\u043f\u0435\u0440\u0435\u0432\u043e\u0437",
            "\u0441\u043a\u043b\u0430\u0434",
        ],
        "Consulting": [
            "\u043a\u043e\u043d\u0441\u0430\u043b\u0442",
            "\u0430\u0443\u0434\u0438\u0442",
            "\u0438\u0441\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u043d",
            "\u044d\u043a\u0441\u043f\u0435\u0440\u0442",
        ],
        "Office & Admin": [
            "\u043a\u0430\u043d\u0446\u0435\u043b",
            "\u043e\u0444\u0438\u0441",
            "\u043c\u0435\u0431\u0435\u043b",
            "\u0445\u043e\u0437",
        ],
    }
    for category, keywords in rules.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return "Other"
