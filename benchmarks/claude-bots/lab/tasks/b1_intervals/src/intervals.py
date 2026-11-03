def merge(intervals):
    """Merge overlapping intervals, given as [start, end] lists."""
    out = []
    for start, end in intervals:
        if out and start < out[-1][1]:
            out[-1][1] = end
        else:
            out.append([start, end])
    return out
