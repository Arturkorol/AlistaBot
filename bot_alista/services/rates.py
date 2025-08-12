"""Utilities for validating manual currency rates."""

def validate_or_prompt_rate(text: str) -> float | None:
    """Validate user-provided currency rate.

    Parameters
    ----------
    text: str
        Raw text input from user containing a currency rate. Commas are allowed
        as decimal separators.

    Returns
    -------
    float | None
        Parsed float value if the input is a valid positive number, otherwise
        ``None``.
    """
    if text is None:
        return None
    try:
        rate = float(text.replace(",", ".").strip())
        if rate <= 0:
            return None
        return rate
    except (ValueError, AttributeError):
        return None
