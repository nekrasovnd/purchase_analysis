from __future__ import annotations

import os
from pathlib import Path

import requests

from purchase_analysis.utils.io import write_text

RESPONSES_URL = "https://api.openai.com/v1/responses"


def _extract_output_text(payload: dict) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct

    parts: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(str(content["text"]))
    return "\n\n".join(parts).strip()


def maybe_write_llm_summary(
    context_markdown: str,
    output_path: Path,
    timeout: int = 120,
) -> bool:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        write_text(
            output_path,
            (
                "# LLM Summary\n\n"
                "Автоматическая генерация summary пропущена: переменная окружения `OPENAI_API_KEY` не задана.\n\n"
                "Для ручного или внешнего LLM-запуска используйте `data/reports/llm_prompt_pack.md`.\n"
            ),
            utf8_bom=True,
        )
        return False

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a senior procurement analyst. "
                    "Write a concise markdown report in Russian. "
                    "For each analytical block use Observation, Interpretation, Significance, Limitation."
                ),
            },
            {
                "role": "user",
                "content": context_markdown,
            },
        ],
        "text": {
            "format": {"type": "text"},
            "verbosity": "low",
        },
    }
    try:
        response = requests.post(
            RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
        output_text = _extract_output_text(body)
        if not output_text:
            output_text = "# LLM Summary\n\nМодель вернула пустой текстовый ответ."
        write_text(output_path, output_text, utf8_bom=True)
        return True
    except requests.RequestException as error:
        write_text(
            output_path,
            (
                "# LLM Summary\n\n"
                "Автоматическая генерация summary завершилась с ошибкой и не повлияла на основной ETL.\n\n"
                f"Ошибка: `{error}`\n\n"
                "Для ручного или внешнего LLM-запуска используйте `data/reports/llm_prompt_pack.md`.\n"
            ),
            utf8_bom=True,
        )
        return False
