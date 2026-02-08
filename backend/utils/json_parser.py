import json
import re


def clean_json_response(text: str) -> str:
    """Aggressively clean LLM output to extract valid JSON"""

    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)

    if "{" in text:
        text = text[text.index("{") :]

    if "}" in text:
        text = text[: text.rindex("}") + 1]

    text = text.replace("\n", " ")
    text = text.replace("\t", " ")
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    return text.strip()


def safe_json_parse(text: str, retries: int = 3) -> dict:
    """Parse JSON with multiple fallback strategies"""

    for attempt in range(retries):
        try:
            cleaned = clean_json_response(text)
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            if attempt < retries - 1:
                text = re.sub(r"[^\{\}\[\]:,\"\d\w\s\.\-]", "", text)
                continue
            raise ValueError(
                f"Could not parse JSON after {retries} attempts: {exc}"
            ) from exc

    return {}
