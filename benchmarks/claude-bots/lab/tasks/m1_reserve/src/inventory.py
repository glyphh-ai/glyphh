class Inventory:
    def __init__(self):
        self.stock = {}

    def add(self, sku, n):
        if n <= 0:
            raise ValueError("add a positive amount")
        self.stock[sku] = self.stock.get(sku, 0) + n

    def remove(self, sku, n):
        if n > self.stock.get(sku, 0):
            raise ValueError("not enough stock")
        self.stock[sku] -= n

    def skus(self):
        return sorted(self.stock)
