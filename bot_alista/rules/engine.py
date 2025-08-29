# bot_alista/rules/engine.py
from __future__ import annotations

from typing import Literal, Dict, Any, List

# Caller should provide a preloaded (and ideally cached) list of RuleRow
# entries to avoid repeated CSV parsing in performance-sensitive paths.
from .loader import pick_rule, RuleRow

PersonType = Literal["individual", "company"]
UsageType = Literal["personal", "commercial"]

def calc_fl_stp(
    *, rules: List[RuleRow], customs_value_eur: float, eur_rub_rate: float, engine_cc: int,
    segment: str, category: str, fuel: str, age_bucket: str
) -> Dict[str, Any]:
    """
    Individuals (personal use) — STP unified payment from rules:
      - Prefer STP% if present, OR
      - STP minimum €/cc if present,
      - Some datasets contain both (use max(ad valorem, min €/cc)).
    Returns duty_eur and duty_rub as the 'STP' (no separate VAT/excise).
    """
    rule = pick_rule(rules, segment=segment, category=category, fuel=fuel,
                     age_bucket=age_bucket, engine_cc=engine_cc, engine_hp=None)
    if not rule:
        raise ValueError("Не найдена строка правил для выбранных параметров (ФЛ).")

    stp_eur = 0.0
    # Option A: percent of customs value (if present)
    if rule.stp_pct:
        stp_eur = max(stp_eur, (customs_value_eur * (rule.stp_pct / 100.0)))
    # Option B: min €/cc
    if rule.stp_min_eur_cc:
        stp_eur = max(stp_eur, engine_cc * rule.stp_min_eur_cc)
    # Option C: some datasets provide only 'spec_eur_cc' for FL buckets -> treat as €/cc
    if rule.spec_eur_cc and not rule.stp_pct and not rule.stp_min_eur_cc:
        stp_eur = max(stp_eur, engine_cc * rule.spec_eur_cc)

    duty_eur = round(stp_eur, 2)
    duty_rub = round(duty_eur * eur_rub_rate, 2)
    return {
        "mode": "FL_STP",
        "rule": rule,
        "duty_eur": duty_eur,
        "duty_rub": duty_rub,
        "vat_rub": 0.0,
        "excise_rub": 0.0,
    }

def calc_ul(
    *, rules: List[RuleRow], customs_value_eur: float, eur_rub_rate: float,
    engine_cc: int, engine_hp: int, segment: str, category: str,
    fuel: str, age_bucket: str, vat_override_pct: float | None = None
) -> Dict[str, Any]:
    """
    Companies/commercial — ad valorem vs min €/cc vs specific €/cc + excise + VAT.
    """
    rule = pick_rule(rules, segment=segment, category=category, fuel=fuel,
                     age_bucket=age_bucket, engine_cc=engine_cc, engine_hp=engine_hp)
    if not rule:
        raise ValueError("Не найдена строка правил для выбранных параметров (ЮЛ).")

    duty_eur = 0.0
    # Case: ad valorem with minimum €/cc
    if rule.duty_type and "адвалор" in rule.duty_type.lower():
        ad_valorem_eur = (customs_value_eur * (float(rule.duty_pct or 0.0) / 100.0))
        min_eur = engine_cc * float(rule.min_eur_cc or 0.0)
        duty_eur = max(ad_valorem_eur, min_eur)
    elif rule.spec_eur_cc:
        duty_eur = engine_cc * rule.spec_eur_cc
    else:
        # fallback: if only percent
        duty_eur = customs_value_eur * (float(rule.duty_pct or 0.0) / 100.0)

    duty_eur = round(duty_eur, 2)
    duty_rub = round(duty_eur * eur_rub_rate, 2)

    # Excise (rub per hp from rules row if provided, else 0)
    excise_rub_hp = float(rule.excise_rub_hp or 0.0)
    excise_rub = round(excise_rub_hp * float(engine_hp or 0), 2)

    # VAT
    vat_pct = float(vat_override_pct if vat_override_pct is not None else (rule.vat_pct or 20.0))
    vat_rub = round(( (customs_value_eur * eur_rub_rate) + duty_rub + excise_rub ) * (vat_pct / 100.0), 2)

    return {
        "mode": "UL",
        "rule": rule,
        "duty_eur": duty_eur,
        "duty_rub": duty_rub,
        "excise_rub": excise_rub,
        "vat_rub": vat_rub,
    }
