def parse_rows(text):
    """Rows of fields from CSV text."""
    return [line.split(",") for line in text.splitlines()]
