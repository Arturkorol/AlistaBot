import pytest

from bot_alista.services.unified_calc import UnifiedCalculator


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def base_config() -> dict:
    return {
        "tariffs": {
            "currency": "EUR",
            "vat": {
                "rate": 0.20,
                "include_clearance_fee_in_vat_base": False,
                "include_util_fee_in_vat_base": False,
            },
            "excise": {
                "unit": "rub_per_hp",
                "brackets": [
                    {"hp_max": 9999, "rate": 0},
                ],
            },
            "util_fee_1291": {
                "base_rub": 20000,
                "personal_use": {
                    "lt3y": {"coefficient": 0.17},
                    "ge3y": {"coefficient": 0.26},
                },
            },
            "clearance_fee": {
                "ranges": [{"max_rub": None, "fee_rub": 0}],
            },
            "age_groups": {  # minimal ETC table; not used in these tests
                "3-5": {"gasoline": {"cc_brackets": [{"cc_max": None, "rate_per_cc": 0}]}}
            },
            "ctp_duty": {
                "by_engine": {
                    "gasoline": {"per_cc_only_eur": 0.60},
                }
            },
        }
    }


def rates() -> dict[str, float]:
    return {"EUR": 100.0, "USD": 90.0, "JPY": 0.7, "CNY": 12.0}


def test_unified_individual_core_path():
    settings = Obj(tariff_config=base_config())
    calc = UnifiedCalculator(settings, rates())
    form = {
        "age": "1-3",  # lt3y for util coeff
        "engine": "gasoline",
        "capacity": 1000,
        "power": 80,
        "owner": "individual",
        "currency": "EUR",
        "price": 1000,
        "power_unit": "hp",
    }
    out = calc.calculate(form)
    # Duty should be > 0 (EESP), util fee = base*coeff = 20000*0.17
    assert float(out["duty_rub"]) > 0
    assert float(out["util_rub"]) == pytest.approx(3400.0)


def test_unified_company_ctp_path():
    settings = Obj(tariff_config=base_config())
    calc = UnifiedCalculator(settings, rates())
    form = {
        "age": "5-7",
        "engine": "gasoline",
        "capacity": 2000,
        "power": 80,
        "owner": "company",
        "currency": "EUR",
        "price": 10000,  # price_rub=1,000,000
        "power_unit": "hp",
    }
    out = calc.calculate(form)
    # Duty per-cc: 0.6 EUR/cc * 2000cc * 100 RUB/EUR = 120,000
    assert float(out["duty_rub"]) == pytest.approx(120000.0)
    # VAT base excludes clearance/util per config; excise=0
    # VAT = 20% * (1,000,000 + 120,000) = 224,000
    assert float(out["vat_rub"]) == pytest.approx(224000.0)

