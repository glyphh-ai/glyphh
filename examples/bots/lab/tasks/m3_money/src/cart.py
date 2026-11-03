from tax import tax


class Cart:
    def __init__(self):
        self.lines = []

    def add(self, price, qty=1, category="general"):
        self.lines.append((float(price), qty, category))

    def total(self):
        total = 0.0
        for price, qty, category in self.lines:
            amount = price * qty
            total += amount + tax(amount, category)
        return round(total, 2)
