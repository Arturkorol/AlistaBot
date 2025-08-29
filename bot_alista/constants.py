from typing import Literal

# Button labels
BTN_CALC = "📊 Рассчитать стоимость очистки"
BTN_BACK = "⬅ Назад"
BTN_MAIN_MENU = "🏠 Главное меню"
BTN_EXIT = "❌ Выход"
BTN_FAQ = "ℹ️ FAQ"
BTN_LEAD = "📞 Заявка"
BTN_LAST = "🧾 Последний расчёт"
BTN_NEW = "🔁 Новый расчёт"
BTN_SEND = "📩 Отправить менеджеру"
BTN_AGE_OVER3_YES = "Да"
BTN_AGE_OVER3_NO = "Нет"

# Type aliases
PersonType = Literal["физическое лицо", "юридическое лицо"]
UsageType = Literal["личное", "коммерческое"]
FuelType = Literal["бензин", "дизель", "гибрид", "электро"]
VehicleKind = Literal["легковой", "грузовой", "мототехника"]

# Validation ranges
# Engine capacity may be any positive number for non‑electric vehicles.
# ``ENGINE_CC_MIN`` is therefore 1 and ``ENGINE_CC_MAX`` is kept generous
# only for UI validation purposes.
ENGINE_CC_MIN = 1
ENGINE_CC_MAX = 10000
HP_MIN = 40
HP_MAX = 1200
AGE_MAX = 30

# Currency codes
# ``RUB`` is included for user input but is treated as a fixed 1:1 rate and
# therefore never requested from the CBR service.
CURRENCY_CODES = ("EUR", "USD", "JPY", "CNY", "KRW", "RUB")

# Prompts and error messages
PROMPT_PERSON = "Выберите тип лица:"
ERROR_PERSON = "Пожалуйста, выберите тип лица кнопкой."
PROMPT_USAGE = "Выберите тип использования:"
ERROR_USAGE = "Пожалуйста, выберите тип использования кнопкой."
PROMPT_TYPE = "Выберите тип авто:"
ERROR_TYPE = "Пожалуйста, выберите тип авто кнопкой."
PROMPT_CURRENCY = "Выберите валюту стоимости:"
ERROR_CURRENCY = "Пожалуйста, выберите валюту кнопкой."
PROMPT_AMOUNT = "Введите стоимость авто в выбранной валюте:"
ERROR_AMOUNT = "Введите корректную стоимость."
PROMPT_ENGINE = "Введите объём двигателя (см³):"
ERROR_ENGINE = "Введите корректный объём двигателя в см³."
PROMPT_POWER = "Введите мощность двигателя (л.с. или кВт):"
ERROR_POWER = "Введите корректную мощность (пример: 150 или 110 кВт)."
PROMPT_YEAR = "Введите год выпуска авто:"
ERROR_YEAR = "Введите корректный год выпуска."
PROMPT_AGE_OVER3 = "Авто старше 3-х лет?"
PROMPT_EMAIL = "Введите ваш e‑mail для получения PDF‑отчёта:"
ERROR_EMAIL = "❌ Пожалуйста, введите корректный email."
PROMPT_EMAIL_CONFIRM = "📧 Хотите получить PDF‑отчёт на e‑mail?"
ERROR_EMAIL_CONFIRM = "Пожалуйста, выберите ответ: 'Да' или 'Нет'."
PROMPT_REQ_NAME = "Введите ФИО владельца:"
PROMPT_REQ_CAR = "Введите марку и модель авто:"
PROMPT_REQ_CONTACT = "Введите контактные данные (телефон, e‑mail):"
PROMPT_REQ_PRICE = "Введите ориентировочную стоимость авто (€):"
ERROR_REQ_PRICE = "Введите корректную цену в евро."
PROMPT_REQ_COMMENT = "Введите дополнительный комментарий (или напишите 'нет'):"
BTN_METHOD_ETC = "📘 ETC (фикс. ставки)"
BTN_METHOD_CTP = "📙 CTP (стоимость авто)"
# Allow automatic comparison of ETC and CTP results
BTN_METHOD_AUTO = "🤖 Авто выбор"
PROMPT_METHOD = "Шаг 1/10: Выберите метод расчёта:"
ERROR_METHOD = "❌ Пожалуйста, выберите один из предложенных методов расчёта."
