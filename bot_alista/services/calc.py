import logging
from decimal import Decimal, ROUND_HALF_UP
import yaml
from enum import Enum
from tabulate import tabulate
from pydantic import BaseModel, ValidationError
from pydantic import model_validator
from bot_alista.models.constants import KW_TO_HP

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

# Shared enums (consolidated)
from bot_alista.models.enums import (
    EnginePowerUnit,
    EngineTypeLegacy as EngineType,
    VehicleAgeLegacy as VehicleAge,
    OwnerType as VehicleOwnerType,
)


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
    ctp_duty: dict | None = None
    age_groups: dict
    mode_selection: dict | None = None


class CTPEngineSchedule(BaseModel):
    ad_valorem_pct: float | None = None
    ad_valorem_percent: float | None = None
    min_eur_per_cc: float | None = None
    per_cc_only_eur: float | None = None

    @model_validator(mode="after")
    def _normalize_and_check(self):  # type: ignore[override]
        adv = self.ad_valorem_pct
        if adv is None and self.ad_valorem_percent is not None:
            self.ad_valorem_pct = self.ad_valorem_percent / 100.0
            adv = self.ad_valorem_pct
        if adv is not None and not (0.0 <= adv <= 1.0):
            raise ValueError("ad_valorem_pct must be within 0..1")
        if self.per_cc_only_eur is not None and self.per_cc_only_eur < 0:
            raise ValueError("per_cc_only_eur must be >= 0")
        if self.min_eur_per_cc is not None and self.min_eur_per_cc < 0:
            raise ValueError("min_eur_per_cc must be >= 0")
        if self.per_cc_only_eur is None and adv is None:
            raise ValueError("engine schedule must define per_cc_only_eur or ad_valorem")
        return self


class CTPDutyModel(BaseModel):
    ad_valorem_pct: float | None = None
    ad_valorem_percent: float | None = None
    min_eur_per_cc: float | None = None
    per_cc_only_eur: float | None = None
    by_engine: dict[str, CTPEngineSchedule] | None = None

    @model_validator(mode="after")
    def _normalize_and_check(self):  # type: ignore[override]
        adv = self.ad_valorem_pct
        if adv is None and self.ad_valorem_percent is not None:
            self.ad_valorem_pct = self.ad_valorem_percent / 100.0
            adv = self.ad_valorem_pct
        if adv is not None and not (0.0 <= adv <= 1.0):
            raise ValueError("ad_valorem_pct must be within 0..1")
        if self.per_cc_only_eur is not None and self.per_cc_only_eur < 0:
            raise ValueError("per_cc_only_eur must be >= 0")
        if self.min_eur_per_cc is not None and self.min_eur_per_cc < 0:
            raise ValueError("min_eur_per_cc must be >= 0")
        if self.by_engine is None and (adv is None and self.per_cc_only_eur is None):
            raise ValueError("ctp_duty must define a top-level schedule or by_engine map")
        return self


class ClearanceRange(BaseModel):
    max_rub: float | None = None
    fee_rub: float

    @model_validator(mode="after")
    def _check_vals(self):  # type: ignore[override]
        if self.max_rub is not None and self.max_rub < 0:
            raise ValueError("max_rub must be >= 0 or null")
        if self.fee_rub < 0:
            raise ValueError("fee_rub must be >= 0")
        return self


class ClearanceFeeModel(BaseModel):
    ranges: list[ClearanceRange] | None = None

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

# Rounding helpers (2 decimal places, HALF_UP)
TWOPL = Decimal("0.01")


def _q(x: float | int | Decimal) -> Decimal:
    try:
        return (x if isinstance(x, Decimal) else Decimal(str(x))).quantize(TWOPL, rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _qf(x: float | int | Decimal) -> float:
    return float(_q(x))

class CustomsCalculator:
    """
    Customs Calculator for vehicle import duties.
    """

    def __init__(self, config_path="config.yaml", config: dict | None = None, *, rates_snapshot: dict[str, float] | None = None):
        if config is not None:
            self.config = config
            try:
                TariffConfig.model_validate((self.config or {}).get("tariffs", {}))
                self._validate_tariffs((self.config or {}).get("tariffs", {}))
            except Exception:
                # Let downstream consumers handle if config is incomplete
                pass
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
            # Lightweight validation of optional ctp_duty and clearance ranges
            self._validate_tariffs(config.get("tariffs", {}))
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
        hybrid_subtype: str | None = None,
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
            # Store hybrid subtype hint for YAML mapping (parallel/series)
            try:
                self.hybrid_subtype = (hybrid_subtype or "").strip().lower() if self.engine_type == EngineType.HYBRID else None
            except Exception:
                self.hybrid_subtype = None
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

    # --- Tariffs sanity checks ---
    def _validate_tariffs(self, tariffs: dict) -> None:
        try:
            ctp = tariffs.get("ctp_duty")
            if isinstance(ctp, dict):
                # Top-level schedule
                if "ad_valorem_pct" in ctp:
                    v = float(ctp["ad_valorem_pct"])  # 0..1
                    if v < 0 or v > 1:
                        raise ValueError("ctp_duty.ad_valorem_pct must be 0..1")
                if "ad_valorem_percent" in ctp:
                    v = float(ctp["ad_valorem_percent"])  # 0..100
                    if v < 0 or v > 100:
                        raise ValueError("ctp_duty.ad_valorem_percent must be 0..100")
                if "min_eur_per_cc" in ctp and float(ctp["min_eur_per_cc"]) < 0:
                    raise ValueError("ctp_duty.min_eur_per_cc must be >= 0")
                if "per_cc_only_eur" in ctp and float(ctp["per_cc_only_eur"]) < 0:
                    raise ValueError("ctp_duty.per_cc_only_eur must be >= 0")
                # by_engine schedules
                be = ctp.get("by_engine")
                if isinstance(be, dict):
                    for k, sch in be.items():
                        if not isinstance(sch, dict):
                            raise ValueError(f"ctp_duty.by_engine.{k} must be mapping")
                        if "per_cc_only_eur" in sch:
                            if float(sch["per_cc_only_eur"]) < 0:
                                raise ValueError(f"ctp_duty.by_engine.{k}.per_cc_only_eur must be >=0")
                        else:
                            adv = sch.get("ad_valorem_pct")
                            if adv is None and "ad_valorem_percent" in sch:
                                adv = float(sch["ad_valorem_percent"]) / 100.0
                            if adv is not None:
                                adv = float(adv)
                                if adv < 0 or adv > 1:
                                    raise ValueError(f"ctp_duty.by_engine.{k}.ad_valorem_pct must be 0..1")
                            if "min_eur_per_cc" in sch and float(sch["min_eur_per_cc"]) < 0:
                                raise ValueError(f"ctp_duty.by_engine.{k}.min_eur_per_cc must be >=0")
            # clearance ranges
            cf = tariffs.get("clearance_fee")
            if isinstance(cf, dict) and isinstance(cf.get("ranges"), list):
                last_has_null = False
                for row in cf["ranges"]:
                    if not isinstance(row, dict):
                        raise ValueError("clearance_fee.ranges entries must be mapping")
                    lim = row.get("max_rub", row.get("price_max_rub", row.get("limit_rub")))
                    if lim is not None and float(lim) < 0:
                        raise ValueError("clearance_fee.ranges.max_rub must be >= 0 or null")
                    fee = float(row.get("fee_rub", 0))
                    if fee < 0:
                        raise ValueError("clearance_fee.ranges.fee_rub must be >= 0")
                    if lim is None:
                        last_has_null = True
                if not last_has_null:
                    logger.warning("clearance_fee.ranges: consider adding a terminal row with max_rub: null")
        except Exception as e:
            # Surface validation exceptions the same way as schema issues
            raise

    def calculate_etc(self):
        """Calculate customs duties using the ETC method."""
        if self.is_already_cleared:
            return {
                "Mode": "ETC",
                "Clearance Fee (RUB)": 0,
                "Duty (RUB)": 0,
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

            # Quantize components to 2dp (HALF_UP)
            duty_rub_q = _qf(duty_rub)
            clearance_q = _qf(clearance_fee)
            util_q = _qf(util_fee)
            total_pay = _qf(duty_rub_q + clearance_q + util_q)
            return {
                "Mode": "ETC",
                "Clearance Fee (RUB)": clearance_q,
                "Duty (RUB)": duty_rub_q,
                "Util Fee (RUB)": util_q,
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
                # EV: duty=0, excise=0; VAT base per config flags
                clearance_fee = self.calculate_clearance_tax()
                util_fee = self.calculate_util_fee()
                vat_base = price_rub
                if bool(vat_cfg.get('include_clearance_fee_in_vat_base', False)):
                    vat_base += clearance_fee
                if bool(vat_cfg.get('include_util_fee_in_vat_base', False)):
                    vat_base += util_fee
                vat = vat_base * vat_rate
                # Quantize for output
                price_q = _qf(price_rub)
                clearance_q = _qf(clearance_fee)
                util_q = _qf(util_fee)
                vat_q = _qf(vat)
                total_pay = _qf(clearance_q + util_q + vat_q)
                return {
                    "Mode": "CTP",
                    "Price (RUB)": price_q,
                    "Duty (RUB)": 0.0,
                    "Excise (RUB)": 0.0,
                    "VAT (RUB)": vat_q,
                    "Clearance Fee (RUB)": clearance_q,
                    "Util Fee (RUB)": util_q,
                    "Total Pay (RUB)": total_pay,
                }

            # Calculate Duty: 20% of price or 0.44 EUR/cm³ minimum
            duty_rub = self._compute_ctp_duty_from_yaml(price_rub)
            if duty_rub is None:
                duty_rate = 0.2
                min_duty_per_cc = self.convert_to_local_currency(0.44, "EUR")
                duty_rub = max(price_rub * duty_rate, min_duty_per_cc * self.engine_capacity)

            # Calculate Excise: 2025 fixed bands (RUB per HP)
            excise = self.calculate_excise()

            # Calculate VAT: Apply to price + duty + excise (+ optional items via config flags)
            vat_base = price_rub + duty_rub + excise
            if bool(vat_cfg.get('include_clearance_fee_in_vat_base', False)):
                vat_base += self.calculate_clearance_tax()
            if bool(vat_cfg.get('include_util_fee_in_vat_base', False)):
                vat_base += self.calculate_util_fee()
            vat = vat_base * vat_rate

            clearance_fee = self.calculate_clearance_tax()

            # Util Fee from config
            util_fee = self.calculate_util_fee()

            # Quantize components and total
            price_q = _qf(price_rub)
            duty_q = _qf(duty_rub)
            excise_q = _qf(excise)
            vat_q = _qf(vat)
            clearance_q = _qf(clearance_fee)
            util_q = _qf(util_fee)
            total_pay = _qf(duty_q + excise_q + vat_q + clearance_q + util_q)
            return {
                "Mode": "CTP",
                "Price (RUB)": price_q,
                "Duty (RUB)": duty_q,
                "Excise (RUB)": excise_q,
                "VAT (RUB)": vat_q,
                "Clearance Fee (RUB)": clearance_q,
                "Util Fee (RUB)": util_q,
                "Total Pay (RUB)": total_pay,
            }
        except KeyError as e:
            logger.error(f"Missing tariff configuration: {e}")
            raise


    def calculate_clearance_tax(self):
        """Calculate customs clearance fee in RUB using YAML ranges if present, else defaults."""
        try:
            price_rub = self.convert_to_local_currency(self.vehicle_price, self.vehicle_currency)
        except Exception as e:
            logger.error(f"Failed to convert price for clearance ranges: {e}")
            return CUSTOMS_CLEARANCE_TAX_RANGES[0][1]

        # Prefer YAML-configured ranges under tariffs.clearance_fee.ranges
        try:
            tariffs = (self.config or {}).get('tariffs', {})
            cf = tariffs.get('clearance_fee', {}) if isinstance(tariffs, dict) else {}
            ranges = cf.get('ranges') if isinstance(cf, dict) else None
            parsed: list[tuple[float | None, float]] = []
            if isinstance(ranges, list):
                for row in ranges:
                    if not isinstance(row, dict):
                        continue
                    lim = row.get('max_rub', row.get('price_max_rub', row.get('limit_rub')))
                    try:
                        lim_f = None if lim is None else float(lim)
                        fee_f = float(row.get('fee_rub', 0))
                        parsed.append((lim_f, fee_f))
                    except Exception:
                        continue
                if parsed:
                    parsed.sort(key=lambda p: float('inf') if p[0] is None else p[0])
                    for lim_f, fee_f in parsed:
                        if lim_f is None or price_rub <= lim_f:
                            logger.info(f"Customs clearance tax (yaml ranges): {fee_f} RUB")
                            return fee_f
        except Exception:
            pass

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
                    # Choose by subtype if present
                    if (self.engine_type == EngineType.ELECTRIC) or (getattr(self, 'hybrid_subtype', None) == 'series'):
                        branch = et.get('ev_or_hybrid_series') or {}
                    else:
                        branch = et.get('ice_or_hybrid_parallel') or {}
                    coeff = (branch.get(age_key) or {}).get('coefficient', 0.0)
                fee = base * float(coeff or 0.0)
                logger.info(f"Util fee 1291 (personal,{age_key}) coeff={coeff} -> {fee}")
                return fee
            else:
                # Commercial / company
                comm = u1291.get('commercial', {})
                et = (comm.get('engine_types') or {})
                coeff: float | None = None
                # EVs often use dedicated coefficients
                if self.engine_type == EngineType.ELECTRIC and 'ev' in et:
                    coeff = float((et['ev'].get(age_key) or {}).get('coefficient', 0.0))
                elif self.engine_type == EngineType.HYBRID and getattr(self, 'hybrid_subtype', None) == 'series' and 'hybrid_series' in et:
                    coeff = float((et['hybrid_series'].get(age_key) or {}).get('coefficient', 0.0))
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

    # Removed legacy 'recycling fee' concept from outputs; util_fee covers current workflows.

    # --- Fixed 2025 excise bands (RUB per 1 HP) ---
    def calculate_excise(self):
        """Calculate excise based on YAML config brackets (RUB per HP or per kW)."""
        exc = self.config['tariffs']['excise']
        unit = str(exc.get('unit', 'rub_per_hp')).lower()
        if unit not in {"rub_per_hp", "rub_per_kw"}:
            unit = "rub_per_hp"
        brackets = exc.get('brackets', [])
        # Internal power stored in HP
        power_value = float(self.vehicle_power or 0)
        if unit == "rub_per_kw":
            # If rates are per kW, convert HP to kW for banding and amount
            power_value = power_value / KW_TO_HP
        selected = None
        for br in brackets:
            mx = br.get('hp_max')
            if mx is None or power_value <= float(mx):
                selected = br
                break
        if selected is None and brackets:
            selected = brackets[-1]
        rate = float(selected.get('rate', 0)) if selected else 0.0
        excise = power_value * rate
        logger.info(f"Excise: {excise} RUB (rate={rate}, unit={unit})")
        return excise

    # --- Helpers: CTP duty from YAML ---
    def _compute_ctp_duty_from_yaml(self, price_rub: float) -> float | None:
        """Compute commercial/legal duty using tariffs.ctp_duty if provided.

        Supported schema options (pick one):
          tariffs:
            ctp_duty:
              # Option A: top-level schedule
              ad_valorem_percent: 20     # or ad_valorem_pct: 0.2
              min_eur_per_cc: 0.44       # optional
              # or per-cc only:
              # per_cc_only_eur: 0.6

              # Option B: engine-specific schedules
              by_engine:
                gasoline: { ad_valorem_percent: 20, min_eur_per_cc: 0.44 }
                diesel:   { per_cc_only_eur: 0.6 }
        """
        try:
            tariffs = (self.config or {}).get('tariffs', {})
            ctp = tariffs.get('ctp_duty') if isinstance(tariffs, dict) else None
            if not isinstance(ctp, dict):
                return None

            def _eval_sched(sched: dict) -> float | None:
                if not isinstance(sched, dict):
                    return None
                # per-cc only in EUR
                if 'per_cc_only_eur' in sched and sched.get('per_cc_only_eur') is not None:
                    try:
                        per_cc_rub = self.convert_to_local_currency(float(sched['per_cc_only_eur']), 'EUR')
                        return float(self.engine_capacity or 0) * per_cc_rub
                    except Exception:
                        return None
                # ad valorem schedule
                adv = sched.get('ad_valorem_pct')
                if adv is None and 'ad_valorem_percent' in sched:
                    adv = float(sched['ad_valorem_percent']) / 100.0
                adv = None if adv is None else float(adv)
                if adv is None:
                    return None
                duty = price_rub * adv
                # minimum per-cc in EUR
                if 'min_eur_per_cc' in sched and sched.get('min_eur_per_cc') is not None:
                    try:
                        min_per_cc_rub = self.convert_to_local_currency(float(sched['min_eur_per_cc']), 'EUR')
                        duty = max(duty, float(self.engine_capacity or 0) * min_per_cc_rub)
                    except Exception:
                        pass
                return duty

            selected = ctp
            by_engine = ctp.get('by_engine') if isinstance(ctp, dict) else None
            if isinstance(by_engine, dict):
                # Try subtype-specific keys first for hybrids
                keys_to_try: list[str] = []
                if self.engine_type == EngineType.HYBRID:
                    subtype = (getattr(self, 'hybrid_subtype', None) or '').lower()
                    if subtype == 'series':
                        keys_to_try += ['hybrid_series']
                    elif subtype == 'parallel':
                        keys_to_try += ['hybrid_parallel']
                # Generic engine key
                et_key = (self.engine_type.value if self.engine_type else '').lower()
                keys_to_try += [et_key]
                for k in keys_to_try:
                    sched = by_engine.get(k)
                    if isinstance(sched, dict):
                        selected = sched
                        break
            return _eval_sched(selected)
        except Exception:
            return None

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
