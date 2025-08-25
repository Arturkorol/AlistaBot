import math
from tks_customs import CustomsCalculator

def test_individual_gasoline_under_3():
    calc = CustomsCalculator('tks_config.yaml')
    calc.set_vehicle_data({
        "age": "1-3",
        "engine_capacity": 2500,
        "engine_type": "gasoline",
        "power": 150,
        "price": 20000,
        "currency": "USD",
        "owner_type": "individual",
    })
    result = calc.calculate_tariff()
    assert result["price_rub"] == 2000000.0
    assert result["duty"] == 1287375.0
    assert result["clearance"] == 8530.0
    assert result["vat"] == 0.0
    assert result["util_fee"] == 3400.0
    assert result["total"] == 1299305.0
