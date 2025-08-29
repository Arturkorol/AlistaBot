import asyncio
import time
from currency_converter_free import CurrencyConverter

_converter = CurrencyConverter(source="CBR")
_cache: dict[str, tuple[float, float]] = {}


async def get_rates(
    codes: list[str] | None = None,
    ttl: int = 3600,
    force_refresh: bool = False,
) -> dict[str, float]:
    codes = codes or ["USD", "EUR"]
    now = time.time()
    rates: dict[str, float] = {}
    for code in codes:
        cached = _cache.get(code)
        if (
            not force_refresh
            and cached is not None
            and now - cached[1] < ttl
        ):
            rates[code] = cached[0]
            continue
        rate = await asyncio.to_thread(_converter.convert, 1, code, "RUB")
        _cache[code] = (rate, now)
        rates[code] = rate
    return rates


async def close_rates_session() -> None:
    close = getattr(_converter, "close", None)
    if close:
        await asyncio.to_thread(close)
