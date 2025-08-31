import pytest

from bot_alista.services.calc import CustomsCalculator, VehicleOwnerType


def make_calc(cfg: dict, rates: dict[str, float] | None = None) -> CustomsCalculator:
    return CustomsCalculator(config=cfg, rates_snapshot=rates or {"EUR": 100.0, "USD": 90.0})


def base_cfg() -> dict:
    return {
        "tariffs": {
            "currency": "EUR",
            "vat": {"rate": 0.20, "include_clearance_fee_in_vat_base": False, "include_util_fee_in_vat_base": False},
            "clearance_fee": {"base_rub": 0},
            "excise": {
                "unit": "rub_per_hp",
                "brackets": [
                    {"hp_max": 90, "rate": 0},
                    {"hp_max": None, "rate": 0},
                ],
            },
            "util_fee": {
                "base_rub": 0,
                "owner_coeff": {"individual": 1.0, "company": 1.0},
                "engine_coeff": {"gasoline": 1.0, "diesel": 1.0, "hybrid": 1.0, "electric": 1.0},
                "age_adjustments": {},
            },
            "age_groups": {"5-7": {"gasoline": {"flat": {"rate_per_cc": 0, "min_duty": 0}}}},
        }
    }


def set_vehicle(calc: CustomsCalculator, *, owner="company", price_eur=10000, cc=2000, hp=80):
    calc.set_vehicle_details(
        age="5-7",
        engine_capacity=cc,
        engine_type="gasoline",
        power=hp,
        price=price_eur,
        owner_type=owner,
        currency="EUR",
        power_unit="hp",
    )


def test_ctp_duty_advalorem_with_min():
    cfg = base_cfg()
    cfg["tariffs"]["ctp_duty"] = {"ad_valorem_percent": 20, "min_eur_per_cc": 0.44}
    calc = make_calc(cfg)
    set_vehicle(calc, price_eur=10000, cc=2500, hp=80)  # price_rub=1,000,000
    res = calc.calculate_ctp()
    # 20% of 1,000,000 = 200,000; min 0.44*2500*100=110,000 -> expect 200,000
    assert res["Duty (RUB)"] == pytest.approx(200000.00)


def test_ctp_duty_per_cc_only():
    cfg = base_cfg()
    cfg["tariffs"]["ctp_duty"] = {"per_cc_only_eur": 0.60}
    calc = make_calc(cfg)
    set_vehicle(calc, price_eur=5000, cc=2000, hp=80)
    res = calc.calculate_ctp()
    # 0.6 EUR/cc * 2000cc * 100 RUB/EUR = 120,000 RUB
    assert res["Duty (RUB)"] == pytest.approx(120000.00)


def test_clearance_fee_yaml_ranges():
    cfg = base_cfg()
    cfg["tariffs"]["clearance_fee"]["ranges"] = [
        {"max_rub": 200000, "fee_rub": 500},
        {"max_rub": None, "fee_rub": 20000},
    ]
    calc = make_calc(cfg)
    set_vehicle(calc, price_eur=1000, cc=1600, hp=80)  # price_rub=100,000 -> first bracket
    res = calc.calculate_ctp()
    assert res["Clearance Fee (RUB)"] == pytest.approx(500.00)


def test_vat_flags_include_clearance_and_util():
    cfg = base_cfg()
    # Enable VAT flags
    cfg["tariffs"]["vat"]["include_clearance_fee_in_vat_base"] = True
    cfg["tariffs"]["vat"]["include_util_fee_in_vat_base"] = True
    # Simple duty 0 to isolate VAT effect
    cfg["tariffs"]["ctp_duty"] = {"ad_valorem_percent": 0}
    # Util fee via legacy util_fee base
    cfg["tariffs"]["util_fee"]["base_rub"] = 20000
    cfg["tariffs"]["util_fee"]["owner_coeff"]["company"] = 1.2
    # Clearance ranges
    cfg["tariffs"]["clearance_fee"]["ranges"] = [
        {"max_rub": 200000, "fee_rub": 500},
        {"max_rub": None, "fee_rub": 20000},
    ]
    calc = make_calc(cfg)
    set_vehicle(calc, price_eur=1000, cc=1600, hp=80)
    res = calc.calculate_ctp()
    # price_rub=100,000; duty=0; excise=0; util=20000*1.2=24000; clearance=500
    # VAT base with flags: 100000 + 0 + 0 + 24000 + 500 = 124,500
    # VAT=24,900
    assert res["VAT (RUB)"] == pytest.approx(24900.00)

