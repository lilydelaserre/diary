"""Natural language date parsing utility."""
import re
import dateparser


def parse_natural_date(text: str) -> str | None:
    """Parse a natural language date string into YYYY-MM-DD.

    Supports: 'today', 'tomorrow', 'next thursday', 'in 5 days', 'march 15', etc.
    Also accepts raw YYYY-MM-DD strings (passed through).
    Returns None if parsing fails.
    """
    text = text.strip()
    if not text:
        return None

    # Pass through ISO dates
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text

    # Normalize 'next X' → 'X' (dateparser handles day names with PREFER_DATES_FROM=future)
    normalized = re.sub(r"\bnext\s+", "", text, flags=re.IGNORECASE)
    result = dateparser.parse(normalized, settings={"PREFER_DATES_FROM": "future"})
    if result:
        return result.date().isoformat()
    return None
