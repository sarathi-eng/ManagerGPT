import json
import re


def parse_llm_json(text: str, expect_array: bool = False):
    """Parse LLM text response into JSON (dict or list).

    Args:
        text: Raw LLM response text.
        expect_array: If True, try to extract a JSON array and return [] as fallback.
    """
    if not text or not isinstance(text, str):
        return [] if expect_array else _dict_fallback()

    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    # 1. try normal parse
    try:
        result = json.loads(cleaned)
        if expect_array and isinstance(result, list):
            return result
        if not expect_array and isinstance(result, dict):
            return result
        # Got valid JSON but wrong type — still usable
        return result
    except Exception:
        pass

    # 2. extract json block (try array first if expected)
    if expect_array:
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass

    # 3. try object extraction
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    # 4. try array extraction even if not expected
    if not expect_array:
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass

    # 5. safe fallback
    return [] if expect_array else _dict_fallback()


def _dict_fallback():
    return {
        "recommendation": "CONDITIONAL",
        "reasoning": "Insufficient structured response from analysis model; decision requires manual validation.",
        "confidence": 0.25,
        "primary_risk": "uncertain operational factors",
        "required_validation": "collect real usage data before action",
    }
