import yaml
from typing import Dict, Any


class CustomsCalculator:
    """Simple customs calculator using fixed rates from config."""

    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.vehicle_data: Dict[str, Any] = {}

    def set_vehicle_data(self, data: Dict[str, Any]) -> "CustomsCalculator":
        self.vehicle_data = data
        return self

    # internal helpers
    def _price_in_rub(self) -> float:
        price = self.vehicle_data['price']
        currency = self.vehicle_data['currency'].upper()
        rate = self.config['currency_rates'][currency]
        return price * rate

    def _duty(self) -> float:
        age = self.vehicle_data['age']
        engine_type = self.vehicle_data['engine_type']
        capacity = self.vehicle_data['engine_capacity']
        age_key = 'under_3' if age in ('new', '1-3') else age
        rate = self.config['fixed_rates'][age_key][engine_type]['rate_per_cc']
        return rate * capacity

    def _clearance_fee(self, price_rub: float) -> float:
        for limit, fee in self.config['clearance_fee_ranges']:
            if price_rub <= limit:
                return fee
        return self.config['clearance_fee_ranges'][-1][1]

    def calculate_tariff(self) -> Dict[str, float]:
        price_rub = float(self._price_in_rub())
        duty = float(self._duty())
        clearance = float(self._clearance_fee(price_rub))
        owner_type = self.vehicle_data.get('owner_type', 'individual')
        if owner_type == 'individual':
            vat = 0.0
            util_fee = 3400.0
        else:
            vat = 0.2 * (price_rub + duty + clearance)
            util_fee = 0.0
        total = duty + clearance + vat + util_fee
        return {
            'price_rub': price_rub,
            'duty': duty,
            'clearance': clearance,
            'vat': vat,
            'util_fee': util_fee,
            'total': total,
        }
