import re


def slugify(title, max_len=60):
    s = title.lower()
    s = re.sub(r"[^a-z0-9]", "-", s)
    return s[:max_len]
