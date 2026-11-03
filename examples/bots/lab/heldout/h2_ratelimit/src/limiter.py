class TokenBucket:
    def __init__(self, rate, burst, clock):
        self.rate, self.burst, self.clock = rate, burst, clock
        self.tokens = 0
        self.last = clock()

    def _refill(self):
        now = self.clock()
        self.tokens += int((now - self.last) * self.rate)
        self.last = now

    def allow(self, n=1):
        self._refill()
        self.tokens -= n
        return self.tokens >= 0

    def retry_after(self, n=1):
        return max(0, (n - self.tokens) / self.rate)
