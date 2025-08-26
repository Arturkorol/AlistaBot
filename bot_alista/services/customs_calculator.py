import logging
import yaml
from enum import Enum
from tabulate import tabulate
from currency_converter_free import CurrencyConverter

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
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

# Constants for Tariffs
BASE_VAT = 0.2

class CustomsCalculator:
    """
    Customs Calculator for vehicle import duties.
    """

    def __init__(self, config_path="config.yaml"):
        self.config = self._load_config(config_path)
        self.converter = CurrencyConverter(source="CBR")
        self.reset_fields()

    def _load_config(self, path):
        """Load configuration from a YAML file."""
        try:
            with open(path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
            if "tariffs" not in config:
                config = {"tariffs": config}
            logger.info("Configuration loaded.")
            return config
        except Exception as e:
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
        self.vehicle_type = "passenger"

    def set_vehicle_details(self, age, engine_capacity, engine_type, power, price, owner_type, currency="USD", vehicle_type="passenger"):
        """Set the details of the vehicle."""
        try:
            self.vehicle_age = VehicleAge(age)
            self.engine_capacity = engine_capacity
            self.engine_type = EngineType(engine_type)
            self.vehicle_power = power
            self.vehicle_price = price
            self.owner_type = VehicleOwnerType(owner_type)
            self.vehicle_currency = currency.upper()
            self.vehicle_type = vehicle_type
        except ValueError as e:
            raise WrongParamException(f"Invalid parameter: {e}")

    def calculate_etc(self):
        """Calculate customs duties using the ETC method."""
        try:
            vehicle_cfg = self.config['tariffs']['vehicle_types'][self.vehicle_type]
        except KeyError:
            raise WrongParamException(f"Vehicle type '{self.vehicle_type}' is not supported")
        try:
            age_cfg = vehicle_cfg['age_groups'][self.vehicle_age.value]
        except KeyError:
            raise WrongParamException(
                f"Age group '{self.vehicle_age.value}' not found for vehicle type '{self.vehicle_type}'"
            )
        try:
            engine_tariffs = age_cfg[self.engine_type.value]
        except KeyError:
            raise WrongParamException(
                f"Engine type '{self.engine_type.value}' not configured for age '{self.vehicle_age.value}'"
            )

        rate_per_cc = engine_tariffs.get('rate_per_cc')
        if rate_per_cc is None:
            raise WrongParamException(
                f"Missing rate_per_cc for engine type '{self.engine_type.value}' and age '{self.vehicle_age.value}'"
            )
        try:
            duty_rub = rate_per_cc * self.engine_capacity * self.convert_to_local_currency(1, "EUR")
        except WrongParamException as e:
            raise WrongParamException(f"Currency conversion failed during ETC calculation: {e}") from e

        clearance_fee = self.calculate_clearance_tax()
        base_util_fee = self.config['tariffs']['base_util_fee']
        etc_util_coeff = self.config['tariffs'].get('etc_util_coeff_base', 1.0)
        util_fee = base_util_fee * etc_util_coeff
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

    def calculate_ctp(self):
        """Calculate customs duties using the CTP method."""
        try:
            # Convert price to RUB
            try:
                price_rub = self.convert_to_local_currency(self.vehicle_price, self.vehicle_currency)
                min_duty_per_cc = self.convert_to_local_currency(0.44, "EUR")
            except WrongParamException as e:
                raise WrongParamException(f"Currency conversion failed during CTP calculation: {e}") from e
            vat_rate = self.config['tariffs'].get('vat_rate', BASE_VAT)

            # Calculate Duty: 20% of price or 0.44 EUR/cm³ minimum
            duty_rate = 0.2
            duty_rub = max(price_rub * duty_rate, min_duty_per_cc * self.engine_capacity)

            # Calculate Excise: Based on engine power
            excise = self.calculate_excise()

            # Calculate VAT: Applied to price + duty + excise
            vat = (price_rub + duty_rub + excise) * vat_rate

            # Clearance Fee: Based on price
            clearance_fee = self.calculate_clearance_tax()

            # Util Fee: Applied based on multiplier
            base_util_fee = self.config['tariffs']['base_util_fee']
            ctp_util_coeff = self.config['tariffs'].get('ctp_util_coeff_base', 1.0)
            util_fee = base_util_fee * ctp_util_coeff

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

    def calculate_auto(self):
        """Automatically choose between ETC and CTP methods."""
        if self.owner_type == VehicleOwnerType.COMPANY:
            return self.calculate_ctp()
        etc = self.calculate_etc()
        ctp = self.calculate_ctp()
        return etc if etc["Total Pay (RUB)"] <= ctp["Total Pay (RUB)"] else ctp

    def calculate_clearance_tax(self):
        """Calculate customs clearance tax based on price."""
        try:
            price_rub = self.convert_to_local_currency(
                self.vehicle_price, self.vehicle_currency
            )
        except WrongParamException as e:
            raise WrongParamException(
                f"Currency conversion failed during clearance tax calculation: {e}"
            ) from e

        try:
            ranges = self.config['tariffs']['clearance_tax_ranges']
        except KeyError:
            raise WrongParamException("Clearance tax ranges not defined in config")

        for price_limit, tax in ranges:
            if price_rub <= price_limit:
                logger.info(f"Customs clearance tax: {tax} RUB")
                return tax
        return ranges[-1][1]  # Default to the last range

    def calculate_recycling_fee(self):
        """Calculate recycling fee."""
        try:
            recycle_cfg = self.config['tariffs']['vehicle_types'][self.vehicle_type]['recycling_fee']
        except KeyError:
            raise WrongParamException(
                f"Recycling fee configuration missing for vehicle type '{self.vehicle_type}'"
            )

        base_rate = recycle_cfg.get('base_rate')
        if base_rate is None:
            raise WrongParamException("Recycling fee base_rate not defined")

        engine_factor = recycle_cfg.get('engine_factors', {}).get(self.engine_type.value)
        if engine_factor is None:
            raise WrongParamException(
                f"Recycling engine factor missing for engine type '{self.engine_type.value}'"
            )

        age_factor = (
            recycle_cfg.get('age_adjustments', {})
            .get(self.vehicle_age.value, {})
            .get(self.engine_type.value, 1)
        )
        owner_mult = recycle_cfg.get('owner_multipliers', {}).get(self.owner_type.value, 1)

        fee = base_rate * engine_factor * age_factor * owner_mult
        logger.info(f"Recycling fee: {fee} RUB")
        return fee

    def calculate_excise(self):
        """Calculate excise based on engine power and engine type."""
        try:
            excise_rate = self.config['tariffs']['vehicle_types'][self.vehicle_type]['excise_rates'][self.engine_type.value]
        except KeyError:
            raise WrongParamException(
                f"Excise rate missing for engine type '{self.engine_type.value}'"
            )
        excise = self.vehicle_power * excise_rate
        logger.info(f"Excise: {excise} RUB")
        return excise

    def convert_to_local_currency(self, amount, currency="EUR"):
        """Convert amount from the specified currency to RUB."""
        try:
            rate = self.converter.convert(amount, currency, "RUB")
            logger.info(f"Converted {amount} {currency} to {rate:.2f} RUB")
            return rate
        except Exception as e:
            raise WrongParamException(f"Currency conversion error: {e}")

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

__all__ = [
    "CustomsCalculator",
    "EnginePowerUnit",
    "EngineType",
    "VehicleAge",
    "VehicleOwnerType",
    "WrongParamException",
]
