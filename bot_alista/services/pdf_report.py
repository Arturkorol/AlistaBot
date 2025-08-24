"""PDF report generation utilities."""

from fpdf import FPDF
import re


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
        self.cell(0, 10, _sanitize(f"Стр. {self.page_no()}", strip_currency=False), align="C")


_EMOJI_RE = re.compile("[\U00010000-\U0010FFFF]")


def _sanitize(text: str, *, strip_currency: bool = True) -> str:
    """Remove characters unsupported by FPDF.

    FPDF internally encodes page content using ``latin-1``. Characters
    outside of the Basic Multilingual Plane (such as many emoji) or some
    currency symbols can therefore trigger ``UnicodeEncodeError`` during
    ``pdf.output``.  To prevent the bot from crashing when users include
    such characters, we strip them or replace them with ASCII fallbacks.

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
    # Remove characters outside the BMP (e.g. emoji)
    return _EMOJI_RE.sub("", text)


def generate_request_pdf(data: dict, filename: str):
    """Генерация PDF заявки на растаможку."""
    pdf = PDFReport()
    pdf.title = _sanitize("Заявка на растаможку", strip_currency=False)
    pdf.add_page()

    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, _sanitize(f"ФИО: {data.get('name', '')}"), ln=True)
    pdf.cell(0, 8, _sanitize(f"Авто: {data.get('car', '')}"), ln=True)
    pdf.cell(0, 8, _sanitize(f"Контакты: {data.get('contact', '')}"), ln=True)
    pdf.cell(0, 8, _sanitize(f"Стоимость: {data.get('price', '')} €"), ln=True)
    pdf.multi_cell(0, 8, _sanitize(f"Комментарий: {data.get('comment', '')}"))

    pdf.output(filename)


def generate_calculation_pdf(result: dict, user_info: dict, filename: str):
    """Генерация PDF отчёта по расчёту растаможки."""
    pdf = PDFReport()
    pdf.title = _sanitize("Отчёт по расчёту растаможки", strip_currency=False)
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, _sanitize(f"Тип авто: {user_info.get('car_type', '')}"), ln=True)
    pdf.cell(0, 8, _sanitize(f"Год выпуска: {user_info.get('year', '')}"), ln=True)
    pdf.cell(0, 8, _sanitize(f"Мощность: {user_info.get('power_hp', '')} л.с."), ln=True)
    pdf.cell(0, 8, _sanitize(f"Объём двигателя: {user_info.get('engine', '')} см³"), ln=True)
    pdf.cell(0, 8, _sanitize(f"Масса: {user_info.get('weight', '')} кг"), ln=True)
    # some calculators may provide price under different keys
    price_eur = result.get("price_eur") or result.get("vehicle_price_eur", "")
    pdf.cell(0, 8, _sanitize(f"Цена: {price_eur} €"), ln=True)
    pdf.ln(5)

    # Таблица расчёта
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 10, _sanitize("Результаты расчёта", strip_currency=False), ln=True)
    pdf.set_font("DejaVu", "", 11)

    def add_row(name, value):
        pdf.cell(90, 8, _sanitize(name, strip_currency=False), border=1)
        pdf.cell(0, 8, _sanitize(str(value)), border=1, ln=True)

    eur_rate = result.get("eur_rate", 0)
    total_eur = result.get("total_eur", 0)
    total_rub = result.get("total_rub")
    if total_rub is None and eur_rate:
        total_rub = total_eur * eur_rate

    add_row("Курс EUR/RUB", f"{eur_rate} ₽")
    add_row("Пошлина", f"{result.get('duty_eur', '')} €")
    add_row("Акциз", f"{result.get('excise_eur', '')} €")
    add_row("НДС", f"{result.get('vat_eur', '')} €")
    add_row("Утильсбор", f"{result.get('util_eur', '')} €")
    add_row("Сбор", f"{result.get('fee_eur', '')} €")
    add_row("ИТОГО (EUR)", f"{total_eur} €")
    add_row("ИТОГО (RUB)", f"{total_rub} ₽")

    pdf.output(filename)