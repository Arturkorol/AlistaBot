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
# Clearance fee scale (RUB) per customs value (RUB), per current FCS guidance.
# Matches spec: <=200k:500; 200-450k:1000; 450k-1.2M:2000; 1.2-2.7M:5000; 2.7-5M:7500; >5M:20000
CUSTOMS_CLEARANCE_TAX_RANGES = [
    (200_000, 500),
    (450_000, 1_000),
    (1_200_000, 2_000),
    (2_700_000, 5_000),
    (5_000_000, 7_500),
    (float('inf'), 20_000),
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

            # EV (8703 80 …): zero duty and excise through 31.12.2025
            if self.engine_type == EngineType.ELECTRIC:
                # EV: duty=0, excise=0, VAT on customs value only (price_rub)
                clearance_fee = self.calculate_clearance_tax()
                util_fee = self.calculate_util_fee()
                vat = price_rub * vat_rate
                total_pay = clearance_fee + util_fee + vat
                return {
                    "Mode": "CTP",
                    "Price (RUB)": price_rub,
                    "Duty (RUB)": 0.0,
                    "Excise (RUB)": 0.0,
                    "VAT (RUB)": vat,
                    "Clearance Fee (RUB)": clearance_fee,
                    "Util Fee (RUB)": util_fee,
                    "Total Pay (RUB)": total_pay,
                }

            # Calculate Duty: 20% of price or 0.44 EUR/cm³ minimum
            duty_rate = 0.2
            min_duty_per_cc = self.convert_to_local_currency(0.44, "EUR")
            duty_rub = max(price_rub * duty_rate, min_duty_per_cc * self.engine_capacity)

            # Calculate Excise: 2025 fixed bands (RUB per HP)
            excise = self.calculate_excise()

            # Calculate VAT: Applied to price + duty + excise (+ optional items)
            # VAT base per spec: customs value + duty + excise (no clearance/util)
            vat = (price_rub + duty_rub + excise) * vat_rate

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
        """Calculate customs clearance fee in RUB using fixed ranges by customs value."""
        try:
            price_rub = self.convert_to_local_currency(self.vehicle_price, self.vehicle_currency)
        except Exception as e:
            logger.error(f"Failed to convert price for clearance ranges: {e}")
            return CUSTOMS_CLEARANCE_TAX_RANGES[0][1]

        for price_limit, tax in CUSTOMS_CLEARANCE_TAX_RANGES:
            if price_rub <= price_limit:
                logger.info(f"Customs clearance tax (by ranges): {tax} RUB")
                return tax
        return CUSTOMS_CLEARANCE_TAX_RANGES[-1][1]

    def calculate_util_fee(self) -> float:
        """Calculate utilization fee in RUB.

        Priority:
        1) tariffs.util_fee_1291 (detailed schema per PP RF #1291)
        2) tariffs.util_fee (legacy multiplicative coefficients)
        """
        tariffs = (self.config or {}).get('tariffs', {})
        u1291 = tariffs.get('util_fee_1291')

        def _age_key() -> str:
            # Map VehicleAge enum to lt3y / ge3y buckets
            if self.vehicle_age in {VehicleAge.NEW, VehicleAge.ONE_TO_THREE}:
                return 'lt3y'
            return 'ge3y'

        if isinstance(u1291, dict):
            base = float(u1291.get('base_rub', 20000))
            age_key = _age_key()

            if self.owner_type == VehicleOwnerType.INDIVIDUAL:
                personal = u1291.get('personal_use', {})
                # Primary: flat per-age coefficients
                bucket = personal.get(age_key, {})
                coeff = bucket.get('coefficient')
                if coeff is None:
                    # fallback to engine_types if provided
                    et = personal.get('engine_types', {})
                    # In personal use both branches are equal; choose any
                    branch = et.get('ev_or_hybrid_series') or et.get('ice_or_hybrid_parallel') or {}
                    coeff = (branch.get(age_key) or {}).get('coefficient', 0.0)
                fee = base * float(coeff or 0.0)
                logger.info(f"Util fee 1291 (personal,{age_key}) = {fee}")
                return fee
            else:
                # Commercial / company
                comm = u1291.get('commercial', {})
                et = (comm.get('engine_types') or {})
                coeff: float | None = None
                # EVs often use dedicated coefficients
                if self.engine_type == EngineType.ELECTRIC and 'ev' in et:
                    coeff = float((et['ev'].get(age_key) or {}).get('coefficient', 0.0))
                elif self.engine_type == EngineType.HYBRID and 'hybrid_series' in et:
                    # Without explicit UI, we conservatively treat hybrids as parallel/ICE below.
                    pass
                if not coeff:
                    # Use by_engine_cc ladder
                    bycc = (comm.get('by_engine_cc') or {}).get(age_key, [])
                    cap = float(self.engine_capacity or 0)
                    selected = None
                    for row in bycc:
                        to_cc = row.get('to_cc')
                        if to_cc is None or cap <= float(to_cc):
                            selected = row
                            break
                    if selected is None and bycc:
                        selected = bycc[-1]
                    if selected:
                        coeff = float(selected.get('coefficient', 0.0))
                    else:
                        coeff = 0.0
                fee = base * float(coeff or 0.0)
                logger.info(f"Util fee 1291 (commercial,{age_key}) coeff={coeff} -> {fee}")
                return fee

        # --- Legacy fallback ---
        u = tariffs.get('util_fee', {})
        base = float(u.get('base_rub', 0))
        owner_map = u.get('owner_coeff', {})
        engine_map = u.get('engine_coeff', {})
        age_adj = u.get('age_adjustments', {})
        coeff_owner = float(owner_map.get(self.owner_type.value, 1.0))
        coeff_engine = float(engine_map.get(self.engine_type.value, 1.0))
        coeff_age = float(age_adj.get(self.vehicle_age.value, {}).get(self.engine_type.value, 1.0))
        fee = base * coeff_owner * coeff_engine * coeff_age
        logger.info(f"Util fee (legacy): {fee} RUB (owner={coeff_owner}, engine={coeff_engine}, age={coeff_age})")
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

    # --- Fixed 2025 excise bands (RUB per 1 HP) ---
    _EXCISE_PER_HP_BANDS: list[tuple[float | None, float]] = [
        (90, 0.0),
        (150, 61.0),
        (200, 583.0),
        (300, 955.0),
        (400, 1628.0),
        (500, 1685.0),
        (None, 1740.0),
    ]

    def _pick_excise_rate(self, hp: float) -> float:
        for upper, rate in self._EXCISE_PER_HP_BANDS:
            if upper is None or hp <= upper:
                return rate
        return self._EXCISE_PER_HP_BANDS[-1][1]

    def calculate_excise(self):
        """Calculate excise using fixed 2025 bands in RUB per HP."""
        power_hp = float(self.vehicle_power or 0)
        rate = self._pick_excise_rate(power_hp)
        excise = power_hp * rate
        logger.info(f"Excise (2025 bands): {excise} RUB (rate={rate} per HP)")
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

        # Select calculation branch strictly by importer status per spec:
        # - individual (личное пользование): unified payment (ETC path)
        # - company/commercial: duty+excise+VAT (CTP path)
        if self.owner_type == VehicleOwnerType.INDIVIDUAL:
            return self.calculate_etc()
        else:
            return self.calculate_ctp()

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

