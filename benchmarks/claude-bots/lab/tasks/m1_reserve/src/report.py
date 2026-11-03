def summary(inv):
    lines, out = [], []
    for sku in inv.skus():
        n = inv.stock[sku]
        lines.append(f"{sku}: {n} in stock")
        if n == 0:
            out.append(sku)
    if out:
        lines.append("Out: " + ", ".join(out))
    return "\n".join(lines)
