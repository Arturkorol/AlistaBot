"""PDF report generation utilities."""

from fpdf import FPDF
import unicodedata


# Paths to system fonts that support Cyrillic characters. Using existing
# DejaVu fonts avoids the need to ship binary font files with the project.
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


class PDFReport(FPDF):
    """FPDF subclass pre-configured with Unicode fonts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Register DejaVu fonts once per document. These fonts support
        # Cyrillic text which is required for the bot's PDF reports.
        self.add_font("DejaVu", "", FONT_REGULAR, uni=True)
        self.add_font("DejaVu", "B", FONT_BOLD, uni=True)

    def header(self):
        self.set_font("DejaVu", "B", 14)
        self.cell(0, 10, self.title, ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.cell(0, 10, f"Стр. {self.page_no()}", align="C")

    # --- Sanitized text helpers -------------------------------------------------

    def cell(self, *args, **kwargs):  # type: ignore[override]
        """Wrapper around :meth:`fpdf.FPDF.cell` applying :func:`_sanitize`."""
        if len(args) >= 3:
            args = list(args)
            args[2] = _sanitize(args[2])
        elif "txt" in kwargs:
            kwargs["txt"] = _sanitize(kwargs["txt"])
        return super().cell(*args, **kwargs)

    def multi_cell(self, *args, **kwargs):  # type: ignore[override]
        """Wrapper around :meth:`fpdf.FPDF.multi_cell` applying :func:`_sanitize`."""
        if len(args) >= 3:
            args = list(args)
            args[2] = _sanitize(args[2])
        elif "txt" in kwargs:
            kwargs["txt"] = _sanitize(kwargs["txt"])
        return super().multi_cell(*args, **kwargs)


def _sanitize(text: str, *, strip_currency: bool = True) -> str:
    """Remove or replace characters unsupported by FPDF.

    Even with TrueType Unicode fonts FPDF cannot handle characters outside
    of the Basic Multilingual Plane or control characters.  This helper
    normalises the text and strips such glyphs so ``pdf.output`` will not
    raise ``UnicodeEncodeError``.

    Args:
        text: Original text that may contain unsupported characters.
        strip_currency: Replace the euro and rouble signs with textual
            representations to keep the information while avoiding
            encoding issues.
    """
    if not isinstance(text, str):
        text = str(text)
    if strip_currency:
        text = text.replace("€", " EUR").replace("₽", " RUB")

    normalized = unicodedata.normalize("NFKC", text)
    sanitized: list[str] = []
    for char in normalized:
        code = ord(char)
        # Drop non-BMP or characters outside Latin-1 range, as FPDF
        # writes buffers using ``latin-1`` encoding
        if code > 0xFFFF or code > 0xFF:
            continue
        if unicodedata.category(char).startswith("C"):
            continue
        sanitized.append(char)
    return "".join(sanitized)


def generate_request_pdf(data: dict, filename: str):
    """Генерация PDF заявки на растаможку."""
    pdf = PDFReport()
    pdf.title = _sanitize("Заявка на растаможку", strip_currency=False)
    pdf.add_page()

    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, f"ФИО: {data.get('name', '')}", ln=True)
    pdf.cell(0, 8, f"Авто: {data.get('car', '')}", ln=True)
    pdf.cell(0, 8, f"Контакты: {data.get('contact', '')}", ln=True)
    pdf.cell(0, 8, f"Стоимость: {data.get('price', '')} €", ln=True)
    pdf.multi_cell(0, 8, f"Комментарий: {data.get('comment', '')}")

    pdf.output(filename)


def generate_calculation_pdf(result: dict, user_info: dict, filename: str):
    """Генерация PDF отчёта по расчёту растаможки."""
    pdf = PDFReport()
    pdf.set_compression(False)
    pdf.title = _sanitize("Отчёт по расчёту растаможки", strip_currency=False)
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, f"Тип авто: {user_info.get('car_type', '')}", ln=True)
    pdf.cell(0, 8, f"Год выпуска: {user_info.get('year', '')}", ln=True)
    pdf.cell(0, 8, f"Мощность: {user_info.get('power_hp', '')} л.с.", ln=True)
    pdf.cell(0, 8, f"Объём двигателя: {user_info.get('engine', '')} см³", ln=True)
    pdf.cell(0, 8, f"Масса: {user_info.get('weight', '')} кг", ln=True)
    # some calculators may provide price under different keys or only in RUB
    eur_rate = result.get("eur_rate") or 1
    price_eur = result.get("price_eur") or result.get("vehicle_price_eur")
    if price_eur is None:
        rub_price = result.get("Price (RUB)")
        if rub_price is not None:
            price_eur = rub_price / eur_rate
    price_eur_str = price_eur if price_eur is not None else ""
    pdf.cell(0, 8, f"Цена: {price_eur_str} €", ln=True)
    pdf.ln(5)

    # Таблица расчёта
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 10, "Результаты расчёта", ln=True)
    pdf.set_font("DejaVu", "", 11)

    def add_row(name, value):
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

    add_row("Курс EUR/RUB", f"{eur_rate} ₽")
    add_row("Пошлина", f"{rub_to_eur(duty_rub)} €")
    add_row("Акциз", f"{rub_to_eur(excise_rub)} €")
    add_row("НДС", f"{rub_to_eur(vat_rub)} €")
    add_row("Утильсбор", f"{rub_to_eur(util_rub)} €")
    add_row("Сбор", f"{rub_to_eur(fee_rub)} €")
    add_row("ИТОГО (EUR)", f"{total_eur} €")
    add_row("ИТОГО (RUB)", f"{total_rub} ₽")

    pdf.output(filename)
