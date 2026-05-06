import json
import re
import logging
from typing import Optional

logger = logging.getLogger("tx_scanner.parser")

REQUIRED_FIELDS = ["交易对手名称", "交易日期", "摘要", "交易金额"]


def parse_ai_response(raw_text: str) -> Optional[dict]:
    """Parse AI response. Returns structured dict or None if not a transaction."""
    text = raw_text.strip()

    # Check for explicit non-transaction marker
    if "NOT_TRANSACTION" in text.upper():
        return None

    # Try to extract JSON
    data = _extract_json(text)
    if data is None:
        logger.warning("Could not parse JSON from AI response: %s", text[:200])
        return None

    # Check if AI explicitly says it's not a transaction
    if not data.get("is_transaction", True):
        return None

    # Validate and normalize
    result = {}
    for field in REQUIRED_FIELDS:
        value = data.get(field, "未知")
        result[field] = str(value) if value is not None else "未知"

    # Coerce 交易金额 to float
    try:
        amount_str = str(data.get("交易金额", 0)).replace(",", "").replace("，", "")
        result["交易金额"] = float(amount_str)
    except (ValueError, TypeError):
        logger.warning("Cannot parse amount: %s", data.get("交易金额"))
        result["交易金额"] = 0.0

    return result


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON object from text. Tries direct parse first, then regex extraction."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block
    patterns = [
        r'\{[\s\S]*?\}',           # greedy: last }
        r'\{[^{}]*\}',             # non-nested
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    return None
