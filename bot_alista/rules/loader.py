# bot_alista/rules/loader.py
from __future__ import annotations
import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "rules" / "russia_auto_import_rules_2025_formulas.csv"

# Column headers (Cyrillic, as in the CSV)
COL = {
    "segment": "Сегмент",
    "category": "Категория ТС",
    "fuel": "Топливо/Тип привода",
    "age_bucket": "Возрастная категория",
    "range_cc": "Диапазон объёма, см³",
    "range_hp": "Диапазон мощности, л.с.",
    "duty_type": "Тип ставки пошлины",
    "duty_pct": "Ставка пошлины, %",
    "min_eur_cc": "Минимум пошлины, €/см³",
    "spec_eur_cc": "Специфическая пошлина, €/см³",
    "stp_pct": "СТП (для ФЛ), %",
    "stp_min_eur_cc": "СТП (для ФЛ), минимум €/см³",
    "vat_pct": "НДС, %",
    "excise_rub_hp": "Акциз, ₽/л.с.",
}

@dataclass
class RuleRow:
    segment: str
    category: str
    fuel: str
    age_bucket: str
    cc_from: Optional[int]
    cc_to: Optional[int]
    hp_from: Optional[int]
    hp_to: Optional[int]
    duty_type: Optional[str]
    duty_pct: Optional[float]
    min_eur_cc: Optional[float]
    spec_eur_cc: Optional[float]
    stp_pct: Optional[float]
    stp_min_eur_cc: Optional[float]
    vat_pct: Optional[float]
    excise_rub_hp: Optional[float]

def _parse_range(v: str) -> Tuple[Optional[float], Optional[float]]:
    if not v or v.strip().lower() in {"", "—", "-", "нет", "n/a"}:
        return None, None
    s = v.replace(" ", "").replace("—", "-").replace("..", "-").replace(",", ".")
    if "-" in s:
        a, b = s.split("-", 1)
        try:
            return float(a), float(b)
        except:
            return None, None
    try:
        x = float(s)
        return x, x
    except:
        return None, None

def _to_float(v: str) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", ".").replace(" ", "")
    if s == "":
        return None
    try:
        return float(s)
    except:
        return None

@lru_cache(maxsize=1)
def load_rules(path: str = str(DATA_PATH)) -> List[RuleRow]:
    """Load rule rows from CSV or return a minimal fallback set.

    The result is cached to avoid repeated disk reads during tariff calculations.
    """
    data_path = Path(path)
    rows: List[RuleRow] = []
    if data_path.exists():
        with data_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for r in reader:
                cc_from, cc_to = _parse_range(r.get(COL["range_cc"], ""))
                hp_from, hp_to = _parse_range(r.get(COL["range_hp"], ""))
                rows.append(
                    RuleRow(
                        segment=(r.get(COL["segment"]) or "").strip(),
                        category=(r.get(COL["category"]) or "").strip(),
                        fuel=(r.get(COL["fuel"]) or "").strip(),
                        age_bucket=(r.get(COL["age_bucket"]) or "").strip(),
                        cc_from=int(cc_from) if cc_from is not None else None,
                        cc_to=int(cc_to) if cc_to is not None else None,
                        hp_from=int(hp_from) if hp_from is not None else None,
                        hp_to=int(hp_to) if hp_to is not None else None,
                        duty_type=(r.get(COL["duty_type"]) or "").strip() or None,
                        duty_pct=_to_float(r.get(COL["duty_pct"])),
                        min_eur_cc=_to_float(r.get(COL["min_eur_cc"])),
                        spec_eur_cc=_to_float(r.get(COL["spec_eur_cc"])),
                        stp_pct=_to_float(r.get(COL["stp_pct"])),
                        stp_min_eur_cc=_to_float(r.get(COL["stp_min_eur_cc"])),
                        vat_pct=_to_float(r.get(COL["vat_pct"])),
                        excise_rub_hp=_to_float(r.get(COL["excise_rub_hp"])),
                    )
                )
    else:
        # Fallback minimal rules (to keep bot operable if CSV is absent).
        rows = [
            # Individuals (FL), passenger, ≤3y, 1801–2300 cc: STP 6.2 €/cc min
            RuleRow("Легковой", "M1", "Бензин", "≤3", 1801, 2300, None, None, "СТП", None, None, None, None, 6.2, None, None),
            # Individuals (FL), passenger, ≤3y, 2301–3000 cc: STP 5.0 €/cc min
            RuleRow("Легковой", "M1", "Бензин", "≤3", 2301, 3000, None, None, "СТП", None, None, None, None, 5.0, None, None),
            # Individuals (FL), passenger, 3–5y, 2301–3000 cc: STP 3.0 €/cc
            RuleRow("Легковой", "M1", "Бензин", "3–5", 2301, 3000, None, None, "СТП", None, None, 3.0, None, None, None, None),
            # Individuals (FL), >7y, >3000 cc: STP 5.7 €/cc
            RuleRow("Легковой", "M1", "Бензин", ">7", 3001, 10000, None, None, "СТП", None, None, 5.7, None, None, None, None),
            # Companies (UL), 3–7y, 2301–3000 cc: 20% but ≥ 0.44 €/cc, VAT 20%, excise ladder must be supplied separately
            RuleRow("Легковой", "M1", "Бензин", "3–7", 2301, 3000, None, None, "Адвалор+Мин", 20.0, 0.44, None, None, None, 20.0, 0.0),
        ]
    return rows

def _match(v: Optional[int], lo: Optional[int], hi: Optional[int]) -> bool:
    if lo is None and hi is None:
        return True
    if v is None:
        return False
    if lo is not None and v < lo:
        return False
    if hi is not None and v > hi:
        return False
    return True

def pick_rule(rows: List[RuleRow], *, segment: str, category: str, fuel: str,
              age_bucket: str, engine_cc: Optional[int], engine_hp: Optional[int]) -> Optional[RuleRow]:
    # First pass: exact filters
    cand = [r for r in rows
            if r.segment == segment and r.category == category and r.fuel == fuel and r.age_bucket == age_bucket
            and _match(engine_cc, r.cc_from, r.cc_to) and _match(engine_hp, r.hp_from, r.hp_to)]
    if cand:
        return cand[0]
    # Relax HP if needed
    cand = [r for r in rows
            if r.segment == segment and r.category == category and r.fuel == fuel and r.age_bucket == age_bucket
            and _match(engine_cc, r.cc_from, r.cc_to)]
    return cand[0] if cand else None

def get_available_age_labels(rows: List[RuleRow]) -> set[str]:
    """Return a set of age bucket labels available in provided rules."""
    return { r.age_bucket for r in rows if r.age_bucket }

def normalize_fuel_label(user_fuel: str) -> str:
    s = (user_fuel or "").strip().lower()
    if any(x in s for x in ("элект", "bev", "electric")):
        return "Электро"
    if any(x in s for x in ("гибрид", "hev", "phev", "hybrid")):
        return "Гибрид"
    if "диз" in s or "diesel" in s:
        return "Дизель"
    # default
    return "Бензин"
