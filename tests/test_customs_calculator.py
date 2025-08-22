import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services.customs_calculator import CustomsCalculator


def test_tariffs_loaded_match_constants():
    tariffs = CustomsCalculator.get_tariffs()
    assert tariffs["duty"]["fl"]["under_3"][0][1]["pct"] == 0.54
    assert tariffs["duty"]["fl"]["3_5"][-1][1] == 3.6
    assert tariffs["duty"]["ul"]["over_7"][-1][1] == 7.5
    assert tariffs["excise"]["hp"][2][1] == 583
    assert tariffs["utilization"]["ul"]["coeffs"]["5_7"] == 0.43
    assert tariffs["processing_fee"][3][1] == 11746
