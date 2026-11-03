RATES = {"food": 0.0625}
DEFAULT = 0.0825


def rate_for(category):
    return RATES.get(category, DEFAULT)


def tax(amount, category):
    return round(amount * rate_for(category), 2)
