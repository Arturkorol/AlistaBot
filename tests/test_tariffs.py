import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICES_PATH = ROOT / "bot_alista" / "services"

spec = importlib.util.spec_from_file_location(
    "services.tariffs", SERVICES_PATH / "tariffs.py"
)
tariffs_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tariffs_mod)  # type: ignore[attr-defined]
get_tariffs_async = tariffs_mod.get_tariffs_async
CONFIG = ROOT / "external" / "tks_api_official" / "config.yaml"


def reset_cache():
    tariffs_mod._cache = None
    tariffs_mod._cache_date = None


@pytest.mark.asyncio
async def test_get_tariffs_env_override(monkeypatch):
    reset_cache()
    monkeypatch.setenv(
        "CUSTOMS_TARIFF_DATA", "clearance_tax_ranges: []\nvehicle_types: {}"
    )
    data = await get_tariffs_async(path=CONFIG)
    assert data["clearance_tax_ranges"] == []
    monkeypatch.delenv("CUSTOMS_TARIFF_DATA")


@pytest.mark.asyncio
async def test_get_tariffs_env_override_invalid(monkeypatch):
    reset_cache()
    monkeypatch.setenv("CUSTOMS_TARIFF_DATA", "foo: 1")
    with pytest.raises(ValueError):
        await get_tariffs_async(path=CONFIG)
    monkeypatch.delenv("CUSTOMS_TARIFF_DATA")


@pytest.mark.asyncio
async def test_get_tariffs_network_success(monkeypatch):
    reset_cache()

    class Resp:
        headers = {"Content-Type": "application/json"}

        async def json(self):
            return {"clearance_tax_ranges": [], "vehicle_types": {}}

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            return Resp()

    monkeypatch.setattr(tariffs_mod.aiohttp, "ClientSession", lambda *a, **kw: Session())
    data = await get_tariffs_async(path=CONFIG)
    assert data == {"clearance_tax_ranges": [], "vehicle_types": {}}


@pytest.mark.asyncio
async def test_get_tariffs_network_invalid(monkeypatch):
    reset_cache()

    class Resp:
        headers = {"Content-Type": "application/json"}

        async def json(self):
            return {"foo": 1}

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            return Resp()

    monkeypatch.setattr(tariffs_mod.aiohttp, "ClientSession", lambda *a, **kw: Session())
    data = await get_tariffs_async(path=CONFIG)
    assert "clearance_tax_ranges" in data


@pytest.mark.asyncio
async def test_get_tariffs_network_failure(monkeypatch):
    reset_cache()

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("boom")

    async def fake_sleep(_):
        pass

    monkeypatch.setattr(tariffs_mod.aiohttp, "ClientSession", lambda *a, **kw: Session())
    monkeypatch.setattr(tariffs_mod.asyncio, "sleep", fake_sleep)
    data = await get_tariffs_async(path=CONFIG)
    assert "clearance_tax_ranges" in data
