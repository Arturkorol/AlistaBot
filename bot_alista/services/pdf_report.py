"""PDF report generation utilities."""

from fpdf import FPDF


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


def generate_request_pdf(data: dict, filename: str):
    """Генерация PDF заявки на растаможку."""
    pdf = PDFReport()
    pdf.title = "Заявка на растаможку"
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
    pdf.title = "Отчёт по расчёту растаможки"
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, f"Тип авто: {user_info.get('car_type', '')}", ln=True)
    pdf.cell(0, 8, f"Год выпуска: {user_info.get('year', '')}", ln=True)
    pdf.cell(0, 8, f"Мощность: {user_info.get('power_hp', '')} л.с.", ln=True)
    pdf.cell(0, 8, f"Объём двигателя: {user_info.get('engine', '')} см³", ln=True)
    pdf.cell(0, 8, f"Масса: {user_info.get('weight', '')} кг", ln=True)
    pdf.cell(0, 8, f"Цена: {result.get('price_eur', '')} €", ln=True)
    pdf.ln(5)

    # Таблица расчёта
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 10, "Результаты расчёта", ln=True)
    pdf.set_font("DejaVu", "", 11)

    def add_row(name, value):
        pdf.cell(90, 8, name, border=1)
        pdf.cell(0, 8, str(value), border=1, ln=True)

    add_row("Курс EUR/RUB", f"{result.get('eur_rate', '')} ₽")
    add_row("Пошлина", f"{result.get('duty_eur', '')} €")
    add_row("Акциз", f"{result.get('excise_eur', '')} €")
    add_row("НДС", f"{result.get('vat_eur', '')} €")
    add_row("Утильсбор", f"{result.get('util_eur', '')} €")
    add_row("Сбор", f"{result.get('fee_eur', '')} €")
    add_row("ИТОГО (EUR)", f"{result.get('total_eur', '')} €")
    add_row("ИТОГО (RUB)", f"{result.get('total_rub', '')} ₽")

    pdf.output(filename)

