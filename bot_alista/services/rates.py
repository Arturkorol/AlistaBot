import asyncio
from currency_converter_free import CurrencyConverter

_converter = CurrencyConverter(source="CBR")


async def get_rates(codes: list[str] | None = None) -> dict[str, float]:
    codes = codes or ["USD", "EUR"]
    rates: dict[str, float] = {}
    for code in codes:
        rate = await asyncio.to_thread(_converter.convert, 1, code, "RUB")
        rates[code] = rate
    return rates


async def close_rates_session() -> None:
    close = getattr(_converter, "close", None)
    if close:
        await asyncio.to_thread(close)
