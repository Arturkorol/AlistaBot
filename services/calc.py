import logging
import yaml
from enum import Enum
from tabulate import tabulate
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
    """
    Lenient schema for the expanded tariff configuration.
    Keeps validation broad so YAML shape can evolve without code changes.
    """
    currency: str = "EUR"
    vat: dict
    clearance_fee: dict
    excise: dict
    util_fee: dict
    age_groups: dict
    mode_selection: dict | None = None

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
        # Optional shared snapshot of FX rates (RUB per 1 unit).
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

    # Currency helpers based on snapshot or live converter
    def _tariff_currency(self) -> str:
        try:
            return str(self.config["tariffs"].get("currency", "EUR")).upper()
        except Exception:
            return "EUR"

    def convert_currency(self, amount: float, from_code: str, to_code: str) -> float:
        """Convert using snapshot rates (RUB per 1 unit)."""
        if self._rates_snapshot is None:
            raise ValueError("Rates snapshot not provided")
        src = from_code.upper()
        dst = to_code.upper()
        if src not in self._rates_snapshot or dst not in self._rates_snapshot:
            raise ValueError(f"Unsupported currency conversion: {from_code}->{to_code}")
        return amount * (self._rates_snapshot[src] / self._rates_snapshot[dst])

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
            tariffs = self.config['tariffs']
            age_group = tariffs['age_groups'].get(self.vehicle_age.value)
            if age_group is None:
                raise WrongParamException(f"No tariffs for age group '{self.vehicle_age.value}'")
            engine_tariffs = age_group.get(self.engine_type.value)
            if engine_tariffs is None:
                raise WrongParamException(
                    f"No ETC tariff for engine type '{self.engine_type.value}' in age group '{self.vehicle_age.value}'"
                )

            # Determine duty according to config rules
            duty_eur = 0.0
            if 'price_brackets' in engine_tariffs and engine_tariffs['price_brackets']:
                tar_cur = self._tariff_currency()
                price_in_tar = self.convert_currency(self.vehicle_price, self.vehicle_currency, tar_cur)
                selected = None
                for br in engine_tariffs['price_brackets']:
                    mx = br.get('price_max')
                    if mx is None or price_in_tar <= mx:
                        selected = br
                        break
                if selected is None:
                    selected = engine_tariffs['price_brackets'][-1]
                percent = float(selected['percent']) / 100.0
                min_rate_per_cc = float(selected['min_rate_per_cc'])
                duty_by_percent = price_in_tar * percent
                duty_min = self.engine_capacity * min_rate_per_cc
                duty_eur = max(duty_by_percent, duty_min)
            elif 'cc_brackets' in engine_tariffs and engine_tariffs['cc_brackets']:
                selected = None
                for br in engine_tariffs['cc_brackets']:
                    mx = br.get('cc_max')
                    if mx is None or self.engine_capacity <= mx:
                        selected = br
                        break
                if selected is None:
                    selected = engine_tariffs['cc_brackets'][-1]
                rate_per_cc = float(selected['rate_per_cc'])
                duty_eur = self.engine_capacity * rate_per_cc
            elif 'flat' in engine_tariffs and engine_tariffs['flat']:
                flat = engine_tariffs['flat']
                rate_per_cc = float(flat.get('rate_per_cc', 0))
                min_duty = float(flat.get('min_duty', 0))
                duty_eur = max(self.engine_capacity * rate_per_cc, min_duty)
            else:
                raise WrongParamException("Unsupported ETC tariff structure in config")

            duty_rub = self.convert_to_local_currency(duty_eur, "EUR")

            clearance_fee = self.calculate_clearance_tax()
            util_fee = self.calculate_util_fee()
            recycling_fee = 0.0

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
            vat_cfg = (self.config or {}).get('tariffs', {}).get('vat', {})
            vat_rate = float(vat_cfg.get('rate', BASE_VAT))

            # Calculate Duty: 20% of price or 0.44 EUR/cm³ minimum
            duty_rate = 0.2
            min_duty_per_cc = self.convert_to_local_currency(0.44, "EUR")
            duty_rub = max(price_rub * duty_rate, min_duty_per_cc * self.engine_capacity)

            # Calculate Excise: Based on engine power
            excise = self.calculate_excise()

            # Calculate VAT: Applied to price + duty + excise (+ optional items)
            vat_base = price_rub + duty_rub + excise
            if bool(vat_cfg.get('include_clearance_fee_in_vat_base', False)):
                vat_base += self.calculate_clearance_tax()
            if bool(vat_cfg.get('include_util_fee_in_vat_base', False)):
                vat_base += self.calculate_util_fee()
            vat = vat_base * vat_rate

            clearance_fee = self.calculate_clearance_tax()

            # Util Fee from config
            util_fee = self.calculate_util_fee()

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
        """Calculate customs clearance fee.

        Uses config base amount if available, otherwise falls back to ranges.
        """
        try:
            base = float(self.config['tariffs']['clearance_fee']['base_rub'])
            logger.info(f"Customs clearance fee (config): {base} RUB")
            return base
        except Exception:
            price_rub = self.convert_to_local_currency(self.vehicle_price, self.vehicle_currency)
            for price_limit, tax in CUSTOMS_CLEARANCE_TAX_RANGES:
                if price_rub <= price_limit:
                    logger.info(f"Customs clearance tax: {tax} RUB")
                    return tax
            return CUSTOMS_CLEARANCE_TAX_RANGES[-1][1]

    def calculate_util_fee(self) -> float:
        """Calculate utilization fee in RUB using coefficients from config."""
        u = self.config['tariffs']['util_fee']
        base = float(u.get('base_rub', 0))
        owner_map = u.get('owner_coeff', {})
        engine_map = u.get('engine_coeff', {})
        age_adj = u.get('age_adjustments', {})
        coeff_owner = float(owner_map.get(self.owner_type.value, 1.0))
        coeff_engine = float(engine_map.get(self.engine_type.value, 1.0))
        coeff_age = float(age_adj.get(self.vehicle_age.value, {}).get(self.engine_type.value, 1.0))
        fee = base * coeff_owner * coeff_engine * coeff_age
        logger.info(f"Util fee: {fee} RUB (owner={coeff_owner}, engine={coeff_engine}, age={coeff_age})")
        return fee

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
        """Calculate excise based on horsepower brackets (RUB per HP)."""
        exc = self.config['tariffs']['excise']
        unit = str(exc.get('unit', 'rub_per_hp')).lower()
        if unit not in {"rub_per_hp", "rub_per_kw"}:
            unit = "rub_per_hp"
        brackets = exc.get('brackets', [])
        # Our internal power is in HP
        power_hp = self.vehicle_power
        if unit == "rub_per_kw":
            # If rates are per kW, convert provided HP to kW
            power_hp = self.vehicle_power / 1.35962
        selected = None
        for br in brackets:
            mx = br.get('hp_max')
            if mx is None or power_hp <= mx:
                selected = br
                break
        if selected is None and brackets:
            selected = brackets[-1]
        rate = float(selected.get('rate', 0)) if selected else 0.0
        excise = power_hp * rate
        logger.info(f"Excise: {excise} RUB (rate={rate}, unit={unit})")
        return excise

    def convert_to_local_currency(self, amount, currency="EUR"):
        """Convert amount from the specified currency to RUB using snapshot rates."""
        cur = currency.upper()
        if self._rates_snapshot is None or cur not in self._rates_snapshot:
            raise ValueError(f"Unsupported currency: {currency}")
        rate_per_unit = self._rates_snapshot[cur]
        value = amount * rate_per_unit
        logger.info(f"Converted {amount} {cur} to {value:.2f} RUB (snapshot)")
        return value

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
        try:
            forced_ages = sel_cfg.get("ctp_age_groups")
            forced_ctp_ages = set(VehicleAge(a) for a in forced_ages) if forced_ages else {
                VehicleAge.NEW, VehicleAge.ONE_TO_THREE
            }
        except Exception:
            forced_ctp_ages = {VehicleAge.NEW, VehicleAge.ONE_TO_THREE}
        price_threshold = float(sel_cfg.get("ctp_price_threshold_rub", 1_000_000))
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
