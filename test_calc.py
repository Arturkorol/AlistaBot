import pytest
from pydantic import ValidationError
from tks_api_official.calc import CustomsCalculator, WrongParamException

@pytest.fixture
def valid_config(tmp_path):
    """Provide a valid configuration file for testing."""
    config_content = """
    tariffs:
      base_clearance_fee: 3100
      base_util_fee: 20000
      base_recycling_fee: 20000
      etc_util_coeff_base: 1.5
      ctp_util_coeff_base: 1.2
      excise_rates:
        gasoline: 58
        diesel: 58
        electric: 0
        hybrid: 58
      recycling_factors:
        default:
          gasoline: 1.0
          diesel: 1.1
          electric: 0.3
          hybrid: 0.9
        adjustments:
          5-7:
            gasoline: 0.26
            diesel: 0.26
            electric: 0.26
            hybrid: 0.26
      age_groups:
        overrides:
          5-7:
            gasoline:
              rate_per_cc: 4.8
              min_duty: 0
            diesel:
              rate_per_cc: 5.0
              min_duty: 0
            electric:
              rate_per_cc: 0
              min_duty: 1000
            hybrid:
              rate_per_cc: 2.0
              min_duty: 2500
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)
    return config_path

@pytest.fixture
def calculator(valid_config, monkeypatch):
    """Create an instance of the calculator with a valid config."""
    calc = CustomsCalculator(config_path=valid_config)

    def fake_convert(amount, currency="EUR"):
        supported = {"USD", "EUR", "KRW", "RUB"}
        if currency.upper() not in supported:
            raise ValueError(f"Unsupported currency: {currency}")
        return amount

    monkeypatch.setattr(calc, "convert_to_local_currency", fake_convert)
    return calc


def test_invalid_config_missing_field(tmp_path):
    bad_config = """
    tariffs:
      base_clearance_fee: 3100
    """
    path = tmp_path / "config.yaml"
    path.write_text(bad_config)
    with pytest.raises(ValidationError):
        CustomsCalculator(config_path=path)

def test_config_loading(calculator):
    """Test that the configuration loads correctly."""
    assert calculator.config['tariffs']['base_clearance_fee'] == 3100
    assert calculator.config['tariffs']['excise_rates']['gasoline'] == 58
    assert calculator.config['tariffs']['base_recycling_fee'] == 20000

def test_set_vehicle_details(calculator):
    """Test setting vehicle details."""
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=100000,
        owner_type="individual",
        currency="USD",
        power_unit="hp",
    )
    assert calculator.vehicle_age.value == "5-7"
    assert calculator.engine_capacity == 2000
    assert calculator.engine_type.value == "gasoline"
    assert calculator.vehicle_power == 150
    assert calculator.vehicle_price == 100000
    assert calculator.vehicle_currency == "USD"

def test_calculate_etc(calculator):
    """Test ETC calculation mode."""
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=100000,
        owner_type="individual",
        currency="USD",
        power_unit="hp"
    )
    results = calculator.calculate_etc()
    assert results["Mode"] == "ETC"
    assert results["Total Pay (RUB)"] > 0
    assert "Duty (RUB)" in results
    assert results["Util Fee (RUB)"] == 20000 * 1.5
    assert results["Recycling Fee (RUB)"] == 20000 * 0.26


def test_min_duty_applied(calculator, monkeypatch):
    """Ensure minimum duty from config is respected."""
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=1000,
        engine_type="hybrid",
        power=150,
        price=100000,
        owner_type="individual",
        currency="USD",
        power_unit="hp",
    )
    monkeypatch.setattr(
        calculator, "convert_to_local_currency", lambda amount, currency="EUR": amount * 100
    )
    results = calculator.calculate_etc()
    assert results["Duty (RUB)"] == 2500 * 100

def test_calculate_ctp(calculator):
    """Test CTP calculation mode."""
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=100000,
        owner_type="individual",
        currency="USD",
        power_unit="hp"
    )
    results = calculator.calculate_ctp()
    assert results["Mode"] == "CTP"
    assert results["Total Pay (RUB)"] > 0
    assert "Excise (RUB)" in results


def test_ctp_already_cleared(calculator):
    calculator.set_vehicle_details(
        age="1-3",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=100000,
        owner_type="individual",
        currency="USD",
        power_unit="hp",
    )
    calculator.is_already_cleared = True
    results = calculator.calculate_ctp()
    assert results["Total Pay (RUB)"] == 0


def test_min_duty_boundary(calculator, monkeypatch):
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=1250,
        engine_type="hybrid",
        power=150,
        price=100000,
        owner_type="individual",
        currency="USD",
        power_unit="hp",
    )
    monkeypatch.setattr(
        calculator, "convert_to_local_currency", lambda amount, currency="EUR": amount
    )
    results = calculator.calculate_etc()
    assert results["Duty (RUB)"] == 2500


def test_power_unit_conversion(calculator):
    """Ensure kilowatt inputs are converted to horsepower."""
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=100,
        price=100000,
        owner_type="individual",
        currency="USD",
        power_unit="kw",
    )
    assert calculator.vehicle_power == pytest.approx(135.962, rel=1e-3)


def test_invalid_currency(calculator):
    """Unsupported currencies should raise ValueError."""
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=100000,
        owner_type="individual",
        currency="XYZ",
        power_unit="hp",
    )
    with pytest.raises(ValueError, match="Unsupported currency: XYZ"):
        calculator.convert_to_local_currency(100, "XYZ")


def test_invalid_enum_values(calculator):
    with pytest.raises(WrongParamException):
        calculator.set_vehicle_details(
            age="bad",
            engine_capacity=2000,
            engine_type="gasoline",
            power=150,
            price=100000,
            owner_type="individual",
            currency="USD",
            power_unit="hp",
        )
    with pytest.raises(WrongParamException):
        calculator.set_vehicle_details(
            age="5-7",
            engine_capacity=2000,
            engine_type="rocket",
            power=150,
            price=100000,
            owner_type="individual",
            currency="USD",
            power_unit="hp",
        )
    with pytest.raises(WrongParamException):
        calculator.set_vehicle_details(
            age="5-7",
            engine_capacity=2000,
            engine_type="gasoline",
            power=150,
            price=100000,
            owner_type="individual",
            currency="USD",
            power_unit="bad",
        )


def test_already_cleared(calculator):
    """Calculation should be skipped for already cleared vehicles."""
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=100000,
        owner_type="individual",
        currency="USD",
        power_unit="hp",
    )
    calculator.is_already_cleared = True
    results = calculator.calculate_etc()
    assert results["Total Pay (RUB)"] == 0


def test_owner_type_affects_util_fee(calculator):
    """Companies should have higher util fees."""
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=100000,
        owner_type="company",
        currency="USD",
        power_unit="hp",
    )
    results = calculator.calculate_etc()
    assert results["Util Fee (RUB)"] == pytest.approx(20000 * 1.5 * 1.1)


def test_auto_mode_selection(calculator):
    """Calculator should choose mode based on age and price."""
    calculator.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=500000,
        owner_type="individual",
        currency="RUB",
        power_unit="hp",
    )
    assert calculator.calculate()["Mode"] == "ETC"

    calculator.set_vehicle_details(
        age="new",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=500000,
        owner_type="individual",
        currency="RUB",
        power_unit="hp",
    )
    assert calculator.calculate()["Mode"] == "CTP"

