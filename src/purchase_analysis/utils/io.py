import json
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, content: str, utf8_bom: bool = False) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8-sig" if utf8_bom else "utf-8")


def write_json(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
