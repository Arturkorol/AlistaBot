from pathlib import Path

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services.pdf_report import generate_calculation_pdf


def test_generate_calculation_pdf_handles_missing_fields(tmp_path):
    result = {"total_eur": 100, "eur_rate": 90}
    user_info = {"car_type": "gasoline"}
    filename = tmp_path / "out.pdf"
    generate_calculation_pdf(result, user_info, str(filename))
    assert filename.exists() and filename.stat().st_size > 0


def test_generate_calculation_pdf_ignores_emojis(tmp_path):
    """PDF generation should succeed even if text contains emoji."""
    result = {"total_eur": 100, "eur_rate": 90}
    user_info = {"car_type": "gasoline 🚗"}
    filename = tmp_path / "emoji.pdf"
    generate_calculation_pdf(result, user_info, str(filename))
    assert filename.exists() and filename.stat().st_size > 0