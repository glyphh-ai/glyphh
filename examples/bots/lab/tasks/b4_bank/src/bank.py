import itertools


class Ledger:
    def __init__(self):
        self.entries = []  # (transfer_id, account, cents)
        self.limits = {}
        self.keys = {}
        self.transfers = {}
        self.ids = itertools.count(1)

    def open(self, acct, overdraft=0):
        self.limits[acct] = overdraft

    def balance(self, acct):
        return sum(c for _, a, c in self.entries if a == acct)

    def transfer(self, src, dst, cents, key):
        if key in self.keys:
            return self.keys[key]
        tid = next(self.ids)
        self.entries.append((tid, src, -cents))
        if self.balance(src) < -self.limits[src]:
            raise ValueError("insufficient funds")
        self.entries.append((tid, dst, cents))
        self.keys[key] = tid
        self.transfers[tid] = (src, dst, cents)
        return tid

    def reverse(self, tid):
        src, dst, cents = self.transfers[tid]
        return self.transfer(dst, src, cents, f"reverse-{tid}")
