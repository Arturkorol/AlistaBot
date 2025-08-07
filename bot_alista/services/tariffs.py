VAT_RATE = 0.20
FEE_EUR = 5

# Duty rates for vehicles between 3-5 years old (EUR per cm^3)
USED_DUTY_3_5 = [
    (1000, 1.5),
    (1500, 1.7),
    (1800, 2.5),
    (2300, 2.7),
    (3000, 3.0),
    (float('inf'), 3.6),
]

# Duty rates for vehicles older than 5 years (EUR per cm^3)
USED_DUTY_5_PLUS = [
    (1000, 3.0),
    (1500, 3.2),
    (1800, 3.5),
    (2300, 4.8),
    (3000, 5.0),
    (float('inf'), 5.7),
]

# New vehicle duty parameters
NEW_DUTY_PERCENT = 0.48
NEW_DUTY_MIN_PER_CC = 2.5

# Excise rate in rubles per horsepower for engines over 3000 cc
EXCISE_RATE_RUB_PER_HP = 511

# Utilisation fees in rubles by category and condition
UTILIZATION_FEES_RUB = {
    'M1': {
        True: 2000,   # new
        False: 3400,  # used
    }
}


def get_used_duty_rate(engine_cc: int, over_five: bool) -> float:
    table = USED_DUTY_5_PLUS if over_five else USED_DUTY_3_5
    for limit, rate in table:
        if engine_cc <= limit:
            return rate
    return table[-1][1]


def get_utilization_fee(category: str, is_new: bool, eco_class: str | None) -> float:
    fees = UTILIZATION_FEES_RUB.get(category, UTILIZATION_FEES_RUB['M1'])
    fee = fees[is_new]
    if eco_class and eco_class.lower() in {'euro5', 'euro6'}:
        fee *= 0.5
    return fee
