from __future__ import annotations

import hashlib
import re

# Vietnamese phone numbers:
# - 10-digit starting with 03x, 05x, 07x, 08x, 09x
# - International format +84 followed by 9 digits
# Separators between digits can be spaces, dots or dashes (optional)
# The pattern uses a negative lookbehind/lookahead to avoid matching substrings of longer numbers.
_VN_PHONE_CORE = r"(?:3[2-9]|5[25689]|7[06-9]|8[0-9]|9[0-9])(?:[ .-]?\d){7}"
_VN_PHONE = rf"(?<!\d)(?:\+84[ .-]?{_VN_PHONE_CORE}|0{_VN_PHONE_CORE})(?!\d)"

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": _VN_PHONE,
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    # Additional patterns
    "passport_vn": r"\b[A-Z]\d{7}\b",
}


def scrub_text(text: str) -> str:
    """Replace all detected PII patterns with [REDACTED_<TYPE>]."""
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe, flags=re.IGNORECASE)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    """Return a scrubbed, truncated preview of text for logging."""
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    """One-way hash of user_id for pseudonymisation."""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
