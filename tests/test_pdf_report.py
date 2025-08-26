import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT = ROOT / "bot_alista"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

pdf_report = pytest.importorskip("services.pdf_report")
generate_calculation_pdf = pdf_report.generate_calculation_pdf
generate_request_pdf = pdf_report.generate_request_pdf


def test_generate_calculation_pdf_handles_missing_fields(tmp_path):
    result = {"total_eur": 100, "eur_rate": 90}
    user_info = {"car_type": "gasoline"}
    filename = tmp_path / "out.pdf"
    generate_calculation_pdf(result, user_info, str(filename))
    assert filename.exists() and filename.stat().st_size > 0


def test_generate_calculation_pdf_accepts_cyrillic(tmp_path):
    result = {"total_eur": 100, "eur_rate": 90}
    user_info = {"car_type": "бензин"}
    filename = tmp_path / "cyrillic.pdf"
    generate_calculation_pdf(result, user_info, str(filename))
    assert filename.exists() and filename.stat().st_size > 0


def test_generate_calculation_pdf_ignores_emojis(tmp_path):
    """PDF generation should succeed even if text contains emoji."""
    result = {"total_eur": 100, "eur_rate": 90}
    user_info = {"car_type": "gasoline 🚗"}
    filename = tmp_path / "emoji.pdf"
    generate_calculation_pdf(result, user_info, str(filename))
    assert filename.exists() and filename.stat().st_size > 0


def test_generate_request_pdf_strips_problematic_symbols(tmp_path):
    data = {
        "name": "Иван 🚀",
        "car": "Лада™",
        "contact": "test@example.com",
        "price": "1000",
        "comment": "Примечание с эмодзи 😎 и нотами 𝄞",
    }
    filename = tmp_path / "symbols.pdf"
    generate_request_pdf(data, str(filename))
    assert filename.exists() and filename.stat().st_size > 0
