import logging
import yaml
from enum import Enum
from tabulate import tabulate
from currency_converter_free import CurrencyConverter
from pydantic import BaseModel, ValidationError

try:  # Configure logging based on settings
    from bot_alista.settings import settings

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
except Exception:  # Fallback if settings unavailable
    level = logging.INFO

logging.basicConfig(level=level, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Custom Exceptions
class WrongParamException(Exception):
    """Exception raised for invalid parameters."""
    def __init__(self, message):
        super().__init__(message)
        logger.error(message)

# Enums for Vehicle Attributes
class EnginePowerUnit(Enum):
    KW = "kilowatt"
    HP = "horsepower"

class EngineType(Enum):
    GASOLINE = "gasoline"
    DIESEL = "diesel"
    ELECTRIC = "electric"
    HYBRID = "hybrid"

class VehicleAge(Enum):
    NEW = "new"
    ONE_TO_THREE = "1-3"
    THREE_TO_FIVE = "3-5"
    FIVE_TO_SEVEN = "5-7"
    OVER_SEVEN = "over_7"

class VehicleOwnerType(Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


class TariffConfig(BaseModel):
    base_clearance_fee: float
    base_util_fee: float
    base_recycling_fee: float
    etc_util_coeff_base: float
    ctp_util_coeff_base: float
    excise_rates: dict[str, float]
    recycling_factors: dict
    age_groups: dict

# Constants for Tariffs
BASE_VAT = 0.2
CUSTOMS_CLEARANCE_TAX_RANGES = [
    (200000, 775),
    (450000, 1550),
    (1200000, 3100),
    (2700000, 8530),
    (4200000, 12000),
    (5500000, 15500),
    (7000000, 20000),
    (8000000, 23000),
    (9000000, 25000),
    (10000000, 27000),
    (float('inf'), 30000)
]

class CustomsCalculator:
    """
    Customs Calculator for vehicle import duties.
    """

    def __init__(self, config_path="config.yaml", config: dict | None = None, *, rates_snapshot: dict[str, float] | None = None):
        if config is not None:
            self.config = config
        else:
            self.config = self._load_config(config_path)
        self.converter = CurrencyConverter(source="CBR")
        # Optional shared snapshot of FX rates (e.g., from get_rates()).
        # When provided, all conversions will use this snapshot to avoid
        # display vs compute mismatches.
        self._rates_snapshot: dict[str, float] | None = rates_snapshot
        self.reset_fields()

    def set_rates_snapshot(self, rates: dict[str, float] | None) -> None:
        """Inject a shared rates snapshot (RUB per 1 unit of currency)."""
        self._rates_snapshot = rates

    def _load_config(self, path):
        """Load configuration from a YAML file."""
        try:
            with open(path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
            if "tariffs" not in config:
                raise KeyError("Configuration missing required 'tariffs' structure.")
            TariffConfig.model_validate(config["tariffs"])
            logger.info("Configuration loaded.")
            return config
        except (ValidationError, Exception) as e:
            logger.error(f"Error loading config: {e}")
            raise

    def reset_fields(self):
        """Reset calculation fields."""
        self.vehicle_age = None
        self.engine_capacity = None
        self.engine_type = None
        self.vehicle_power = None
        self.vehicle_price = None
        self.owner_type = None
        self.vehicle_currency = "USD"
        self.is_already_cleared = False

    def set_vehicle_details(
        self,
        age,
        engine_capacity,
        engine_type,
        power,
        price,
        owner_type,
        currency="USD",
        power_unit="hp",
    ):
        """Set the details of the vehicle."""
        try:
            self.vehicle_age = VehicleAge(age)
            self.engine_capacity = engine_capacity
            self.engine_type = EngineType(engine_type)

            # Determine power unit and convert to HP if necessary
            if isinstance(power_unit, str):
                unit = power_unit.lower()
                if unit in {"kw", "kilowatt"}:
                    power_unit_enum = EnginePowerUnit.KW
                elif unit in {"hp", "horsepower"}:
                    power_unit_enum = EnginePowerUnit.HP
                else:
                    raise ValueError(f"Invalid power unit: {power_unit}")
            else:
                power_unit_enum = EnginePowerUnit(power_unit)

            # Preserve the provided unit while converting power to HP for
            # internal calculations.  This allows consumers to know which
            # unit was originally supplied.
            self.power_unit = power_unit_enum
            if power_unit_enum == EnginePowerUnit.KW:
                self.vehicle_power = power * 1.35962  # Convert kW to HP
            else:
                self.vehicle_power = power

            self.vehicle_price = price
            self.owner_type = VehicleOwnerType(owner_type)
            self.vehicle_currency = currency.upper()
        except ValueError as e:
            raise WrongParamException(f"Invalid parameter: {e}")

    def calculate_etc(self):
        """Calculate customs duties using the ETC method."""
        if self.is_already_cleared:
            return {
                "Mode": "ETC",
                "Clearance Fee (RUB)": 0,
                "Duty (RUB)": 0,
                "Recycling Fee (RUB)": 0,
                "Util Fee (RUB)": 0,
                "Total Pay (RUB)": 0,
            }
        try:
            all_overrides = self.config['tariffs']['age_groups']['overrides']
            overrides = all_overrides.get(self.vehicle_age.value)
            if overrides is None:
                # Fallback to a known age bucket to avoid hard failures
                # when config misses a specific age group.
                fallback_age = '5-7' if '5-7' in all_overrides else next(iter(all_overrides.keys()))
                logger.warning(
                    f"No ETC overrides for age '{self.vehicle_age.value}', falling back to '{fallback_age}'"
                )
                overrides = all_overrides[fallback_age]
            engine_tariffs = overrides.get(self.engine_type.value)
            if engine_tariffs is None:
                raise WrongParamException(
                    f"No ETC tariff for engine type '{self.engine_type.value}' in age group '{self.vehicle_age.value}'"
                )

            rate_per_cc = engine_tariffs['rate_per_cc']
            min_duty = engine_tariffs.get('min_duty', 0)
            duty_eur = max(rate_per_cc * self.engine_capacity, min_duty)
            duty_rub = self.convert_to_local_currency(duty_eur, "EUR")

            clearance_fee = self.calculate_clearance_tax()
            util_base = self.config['tariffs']['base_util_fee']
            util_coeff = self.config['tariffs'].get('etc_util_coeff_base', 1.0)
            if self.owner_type == VehicleOwnerType.COMPANY:
                util_coeff *= 1.1
            util_fee = util_base * util_coeff
            recycling_fee = self.calculate_recycling_fee()

            total_pay = clearance_fee + duty_rub + util_fee + recycling_fee
            return {
                "Mode": "ETC",
                "Clearance Fee (RUB)": clearance_fee,
                "Duty (RUB)": duty_rub,
                "Recycling Fee (RUB)": recycling_fee,
                "Util Fee (RUB)": util_fee,
                "Total Pay (RUB)": total_pay,
            }
        except KeyError as e:
            logger.error(f"Missing tariff configuration: {e}")
            raise

    def calculate_ctp(self):
        """Calculate customs duties using the CTP method."""
        if self.is_already_cleared:
            return {
                "Mode": "CTP",
                "Price (RUB)": 0,
                "Duty (RUB)": 0,
                "Excise (RUB)": 0,
                "VAT (RUB)": 0,
                "Clearance Fee (RUB)": 0,
                "Util Fee (RUB)": 0,
                "Total Pay (RUB)": 0,
            }
        try:
            # Convert price to RUB
            price_rub = self.convert_to_local_currency(self.vehicle_price, self.vehicle_currency)
            vat_rate = BASE_VAT

            # Calculate Duty: 20% of price or 0.44 EUR/cm³ minimum
            duty_rate = 0.2
            min_duty_per_cc = self.convert_to_local_currency(0.44, "EUR")
            duty_rub = max(price_rub * duty_rate, min_duty_per_cc * self.engine_capacity)

            # Calculate Excise: Based on engine power
            excise = self.calculate_excise()

            # Calculate VAT: Applied to price + duty + excise
            vat = (price_rub + duty_rub + excise) * vat_rate

            clearance_fee = self.calculate_clearance_tax()

            # Util Fee: Applied based on multiplier
            util_coeff = self.config['tariffs']['ctp_util_coeff_base']
            if self.owner_type == VehicleOwnerType.COMPANY:
                util_coeff *= 1.1
            util_fee = self.config['tariffs']['base_util_fee'] * util_coeff

            # Total Pay
            total_pay = duty_rub + excise + vat + clearance_fee + util_fee
            return {
                "Mode": "CTP",
                "Price (RUB)": price_rub,
                "Duty (RUB)": duty_rub,
                "Excise (RUB)": excise,
                "VAT (RUB)": vat,
                "Clearance Fee (RUB)": clearance_fee,
                "Util Fee (RUB)": util_fee,
                "Total Pay (RUB)": total_pay,
            }
        except KeyError as e:
            logger.error(f"Missing tariff configuration: {e}")
            raise


    def calculate_clearance_tax(self):
        """Calculate customs clearance tax based on price."""
        price_rub = self.convert_to_local_currency(self.vehicle_price, self.vehicle_currency)
        for price_limit, tax in CUSTOMS_CLEARANCE_TAX_RANGES:
            if price_rub <= price_limit:
                logger.info(f"Customs clearance tax: {tax} RUB")
                return tax
        return CUSTOMS_CLEARANCE_TAX_RANGES[-1][1]  # Default to the last range

    def calculate_recycling_fee(self):
        """Calculate recycling fee."""
        factors = self.config['tariffs']['recycling_factors']
        default_factors = factors.get('default', {})
        adjustments = factors.get('adjustments', {}).get(self.vehicle_age.value, {})
        engine_factor = adjustments.get(
            self.engine_type.value, default_factors.get(self.engine_type.value, 1.0)
        )
        base_rate = self.config['tariffs']['base_recycling_fee']
        fee = base_rate * engine_factor
        logger.info(f"Recycling fee: {fee} RUB")
        return fee

    def calculate_excise(self):
        """Calculate excise based on engine power and engine type."""
        excise_rate = self.config['tariffs']['excise_rates'][self.engine_type.value]
        excise = self.vehicle_power * excise_rate
        logger.info(f"Excise: {excise} RUB")
        return excise

    def convert_to_local_currency(self, amount, currency="EUR"):
        """Convert amount from the specified currency to RUB."""
        try:
            cur = currency.upper()
            if self._rates_snapshot is not None and cur in self._rates_snapshot:
                rate_per_unit = self._rates_snapshot[cur]
                value = amount * rate_per_unit
                logger.info(f"Converted {amount} {cur} to {value:.2f} RUB (snapshot)")
                return value
            # Fallback to live converter if snapshot not provided.
            value = self.converter.convert(amount, cur, "RUB")
            logger.info(f"Converted {amount} {cur} to {value:.2f} RUB")
            return value
        except Exception as e:
            logger.error(f"Currency conversion error: {e}")
            raise ValueError(f"Unsupported currency: {currency}")

    def calculate(self):
        """Automatically choose calculation mode based on vehicle data."""

        required = {
            "vehicle_age": self.vehicle_age,
            "engine_capacity": self.engine_capacity,
            "engine_type": self.engine_type,
            "vehicle_power": self.vehicle_power,
            "vehicle_price": self.vehicle_price,
            "owner_type": self.owner_type,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise WrongParamException(
                "Missing vehicle details: " + ", ".join(missing)
            )

        price_rub = self.convert_to_local_currency(self.vehicle_price, self.vehicle_currency)
        # Configurable selector: allows aligning with regulation without code changes.
        sel_cfg = (self.config or {}).get("tariffs", {}).get("mode_selection", {})
        forced_ctp_ages = set(
            VehicleAge(a) for a in sel_cfg.get("ctp_age_groups", [VehicleAge.NEW.value, VehicleAge.ONE_TO_THREE.value])
        )
        price_threshold = sel_cfg.get("ctp_price_threshold_rub", 1_000_000)
        if self.vehicle_age in forced_ctp_ages or price_rub > price_threshold:
            return self.calculate_ctp()
        return self.calculate_etc()

    def print_table(self, mode):
        """Print the calculation results as a table."""
        if mode == "ETC":
            results = self.calculate_etc()
        elif mode == "CTP":
            results = self.calculate_ctp()
        else:
            raise WrongParamException("Invalid calculation mode")

        table = [[k, f"{v:,.2f}" if isinstance(v, (float, int)) else v] for k, v in results.items()]
        print(tabulate(table, headers=["Description", "Amount"], tablefmt="psql"))

if __name__ == "__main__":
    # Example usage
    calculator = CustomsCalculator("config.yaml")

    # Set vehicle details (example values)
    calculator.set_vehicle_details(
        age="5-7", 
        engine_capacity=2000, 
        engine_type="gasoline", 
        power=150, 
        price=10000, 
        owner_type="individual",
        currency="USD")

    # Print results for ETC mode
    calculator.print_table("ETC")

    # Print results for CTP mode
    calculator.print_table("CTP")
