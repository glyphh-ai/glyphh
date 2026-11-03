class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.items = {}
        self.order = []

    def get(self, key, default=None):
        return self.items.get(key, default)

    def put(self, key, value):
        if key not in self.items:
            self.order.append(key)
        self.items[key] = value
        if len(self.items) >= self.capacity:
            oldest = self.order.pop(0)
            del self.items[oldest]

    def __len__(self):
        return len(self.items)
