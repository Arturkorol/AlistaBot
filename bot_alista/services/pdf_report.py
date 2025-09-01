"""PDF report generation utilities (constants-driven).

Fix: add cross-platform font resolution to avoid crashes on Windows/macOS
when Linux font paths are unavailable. Falls back to core fonts if no
Unicode TTF is found (content may lose Cyrillic in that case, but avoids
crashing the request flow).
"""

from fpdf import FPDF
import unicodedata
import os
from typing import Tuple, Optional
from bot_alista.constants import (
    PDF_REQUEST_TITLE,
    PDF_FIELD_NAME,
    PDF_FIELD_CAR,
    PDF_FIELD_CONTACT,
    PDF_FIELD_PRICE,
    PDF_FIELD_COMMENT,
    PDF_PAGE_LABEL,
    PDF_CALC_TITLE,
    PDF_FIELD_CAR_TYPE,
    PDF_FIELD_YEAR,
    PDF_FIELD_POWER_HP,
    PDF_FIELD_ENGINE,
    PDF_FIELD_WEIGHT,
    PDF_FIELD_PRICE_EUR,
    PDF_SECTION_SUMMARY,
    PDF_LABEL_EUR_RATE,
    PDF_LABEL_DUTY,
    PDF_LABEL_EXCISE,
    PDF_LABEL_VAT,
    PDF_LABEL_UTIL,
    PDF_LABEL_CLEARANCE,
    PDF_LABEL_TOTAL_EUR,
    PDF_LABEL_TOTAL_RUB,
)


def _first_existing(paths: list[str]) -> Optional[str]:
    for p in paths:
        if not p:
            continue
        if os.path.exists(p):
            return p
    return None


def _resolve_font_paths() -> Tuple[Optional[str], Optional[str]]:
    """Return (regular, bold) font paths if found, else (None, None).

    Order of preference:
    - Environment overrides: PDF_FONT_REGULAR, PDF_FONT_BOLD
    - Linux DejaVu
    - Windows Arial
    - macOS Arial
    """
    env_reg = os.getenv("PDF_FONT_REGULAR")
    env_bold = os.getenv("PDF_FONT_BOLD")

    linux_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    linux_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    win_reg = r"C:\\Windows\\Fonts\\arial.ttf"
    win_bold = r"C:\\Windows\\Fonts\\arialbd.ttf"

    mac_reg_candidates = [
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    mac_bold_candidates = [
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]

    reg = _first_existing([env_reg, linux_reg, win_reg, *mac_reg_candidates])
    bold = _first_existing([env_bold, linux_bold, win_bold, *mac_bold_candidates])
    return reg, bold


class PDFReport(FPDF):
    """FPDF subclass pre-configured with Unicode fonts and sane defaults."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reg, bold = _resolve_font_paths()
        self._has_unicode_fonts = bool(reg and bold)
        if self._has_unicode_fonts:
            # Register found TTF fonts with Unicode support
            self.add_font("DejaVu", "", reg, uni=True)
            self.add_font("DejaVu", "B", bold, uni=True)
        else:
            # Fall back to core fonts; no Unicode, but do not crash
            pass

    def header(self):
        if getattr(self, "_has_unicode_fonts", False):
            self.set_font("DejaVu", "B", 14)
        else:
            self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, _sanitize(getattr(self, "title", ""), strip_currency=False), ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        if getattr(self, "_has_unicode_fonts", False):
            self.set_font("DejaVu", "", 8)
        else:
            self.set_font("Helvetica", "", 8)
        self.cell(0, 10, _sanitize(PDF_PAGE_LABEL.format(page=self.page_no()), strip_currency=False), align="C")

    # --- Sanitized text helpers -------------------------------------------------

    def cell(self, *args, **kwargs):  # type: ignore[override]
        if len(args) >= 3:
            args = list(args)
            args[2] = _sanitize(args[2])
        elif "txt" in kwargs:
            kwargs["txt"] = _sanitize(kwargs["txt"])
        return super().cell(*args, **kwargs)

    def multi_cell(self, *args, **kwargs):  # type: ignore[override]
        if len(args) >= 3:
            args = list(args)
            args[2] = _sanitize(args[2])
        elif "txt" in kwargs:
            kwargs["txt"] = _sanitize(kwargs["txt"])
        return super().multi_cell(*args, **kwargs)


def _sanitize(text: str, *, strip_currency: bool = True) -> str:
    """Remove or replace characters unsupported by FPDF/latin-1 buffer."""
    if not isinstance(text, str):
        text = str(text)
    if strip_currency:
        text = text.replace("€", " EUR").replace("₽", " RUB")
    normalized = unicodedata.normalize("NFKC", text)
    out: list[str] = []
    for ch in normalized:
        code = ord(ch)
        if code > 0xFF:  # outside latin-1 buffer used by FPDF
            continue
        if unicodedata.category(ch).startswith("C"):
            continue
        out.append(ch)
    return "".join(out)


def generate_request_pdf(data: dict, filename: str):
    """Generate PDF for a custom request form using constants templates."""
    pdf = PDFReport()
    # Ensure document info title does not contain non-latin1 to avoid encoding errors
    pdf.title = _sanitize(PDF_REQUEST_TITLE, strip_currency=False)
    pdf.add_page()

    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"{PDF_FIELD_NAME}: {data.get('name', '')}", ln=True)
    pdf.cell(0, 8, f"{PDF_FIELD_CAR}: {data.get('car', '')}", ln=True)
    pdf.cell(0, 8, f"{PDF_FIELD_CONTACT}: {data.get('contact', '')}", ln=True)
    pdf.cell(0, 8, f"{PDF_FIELD_PRICE}: {data.get('price', '')}", ln=True)
    pdf.multi_cell(0, 8, f"{PDF_FIELD_COMMENT}: {data.get('comment', '')}")

    pdf.output(filename)


def generate_calculation_pdf(result: dict, user_info: dict, filename: str):
    """Generate PDF for calculation results using constants templates."""
    pdf = PDFReport()
    pdf.set_compression(False)
    # Ensure document info title does not contain non-latin1 to avoid encoding errors
    pdf.title = _sanitize(PDF_CALC_TITLE, strip_currency=False)
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, f"{PDF_FIELD_CAR_TYPE}: {user_info.get('car_type', '')}", ln=True)
    pdf.cell(0, 8, f"{PDF_FIELD_YEAR}: {user_info.get('year', '')}", ln=True)
    pdf.cell(0, 8, f"{PDF_FIELD_POWER_HP}: {user_info.get('power_hp', '')}", ln=True)
    pdf.cell(0, 8, f"{PDF_FIELD_ENGINE}: {user_info.get('engine', '')}", ln=True)
    pdf.cell(0, 8, f"{PDF_FIELD_WEIGHT}: {user_info.get('weight', '')}", ln=True)

    eur_rate = result.get("eur_rate") or 1
    price_eur = result.get("price_eur") or result.get("vehicle_price_eur")
    if price_eur is None:
        rub_price = result.get("Price (RUB)")
        if rub_price is not None and eur_rate:
            price_eur = rub_price / eur_rate
    price_eur_str = price_eur if price_eur is not None else ""
    pdf.cell(0, 8, f"{PDF_FIELD_PRICE_EUR}: {price_eur_str}", ln=True)
    pdf.ln(5)

    # Summary section
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 10, PDF_SECTION_SUMMARY, ln=True)
    pdf.set_font("DejaVu", "", 11)

    def add_row(name: str, value):
        pdf.cell(90, 8, name, border=1)
        pdf.cell(0, 8, str(value), border=1, ln=True)

    def rub_to_eur(value: float) -> float:
        return value / eur_rate if eur_rate else 0

    duty_rub = result.get("Duty (RUB)", 0)
    excise_rub = result.get("Excise (RUB)", 0)
    vat_rub = result.get("VAT (RUB)", 0)
    util_rub = result.get("Util Fee (RUB)", 0)
    fee_rub = result.get("Clearance Fee (RUB)", 0)
    recycling_rub = result.get("Recycling Fee (RUB)", 0)
    total_rub = result.get("Total Pay (RUB)")
    if total_rub is None:
        total_rub = duty_rub + excise_rub + vat_rub + util_rub + fee_rub + recycling_rub
    total_eur = rub_to_eur(total_rub)

    add_row(PDF_LABEL_EUR_RATE, f"{eur_rate}")
    add_row(PDF_LABEL_DUTY, f"{rub_to_eur(duty_rub)}")
    add_row(PDF_LABEL_EXCISE, f"{rub_to_eur(excise_rub)}")
    add_row(PDF_LABEL_VAT, f"{rub_to_eur(vat_rub)}")
    add_row(PDF_LABEL_UTIL, f"{rub_to_eur(util_rub)}")
    add_row(PDF_LABEL_CLEARANCE, f"{rub_to_eur(fee_rub)}")
    add_row(PDF_LABEL_TOTAL_EUR, f"{total_eur}")
    add_row(PDF_LABEL_TOTAL_RUB, f"{total_rub}")

    pdf.output(filename)
