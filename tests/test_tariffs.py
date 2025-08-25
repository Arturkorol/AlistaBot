import sys
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
get_tariffs = tariffs_mod.get_tariffs
CONFIG = ROOT / "external" / "tks_api_official" / "config.yaml"


def reset_cache():
    tariffs_mod._cache = None
    tariffs_mod._cache_date = None


def test_get_tariffs_env_override(monkeypatch):
    reset_cache()
    monkeypatch.setenv(
        "CUSTOMS_TARIFF_DATA", "clearance_tax_ranges: []\nvehicle_types: {}"
    )
    data = get_tariffs(path=CONFIG)
    assert data["clearance_tax_ranges"] == []
    monkeypatch.delenv("CUSTOMS_TARIFF_DATA")


def test_get_tariffs_env_override_invalid(monkeypatch):
    reset_cache()
    monkeypatch.setenv("CUSTOMS_TARIFF_DATA", "foo: 1")
    with pytest.raises(ValueError):
        get_tariffs(path=CONFIG)
    monkeypatch.delenv("CUSTOMS_TARIFF_DATA")


def test_get_tariffs_network_success(monkeypatch):
    reset_cache()

    class Resp:
        headers = {"Content-Type": "application/json"}

        def json(self):
            return {"clearance_tax_ranges": [], "vehicle_types": {}}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(tariffs_mod.requests, "get", lambda *a, **kw: Resp())
    data = get_tariffs(path=CONFIG)
    assert data == {"clearance_tax_ranges": [], "vehicle_types": {}}


def test_get_tariffs_network_invalid(monkeypatch):
    reset_cache()

    class Resp:
        headers = {"Content-Type": "application/json"}

        def json(self):
            return {"foo": 1}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(tariffs_mod.requests, "get", lambda *a, **kw: Resp())
    data = get_tariffs(path=CONFIG)
    assert "clearance_tax_ranges" in data


def test_get_tariffs_network_failure(monkeypatch):
    reset_cache()

    def fake_get(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(tariffs_mod.requests, "get", fake_get)
    data = get_tariffs(path=CONFIG)
    assert "clearance_tax_ranges" in data
