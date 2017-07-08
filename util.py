def fmt_time(s, minimal=True):
    """
    Args:
        s: time in seconds (float for fractional)
        minimal: Flag, if true, only return strings for times > 0, leave rest outs
    Returns: String formatted 99h 59min 59.9s, where elements < 1 are left out optionally.
    """
    ms = s - int(s)
    s = int(s)
    if s < 60 and minimal:
        return "{s:02.3f}s".format(s=s + ms)

    m, s = divmod(s, 60)
    if m < 60 and minimal:
        return "{m:02d}min {s:02.3f}s".format(m=m, s=s + ms)

    h, m = divmod(m, 60)
    return "{h:02d}h {m:02d}min {s:02.3f}s".format(h=h, m=m, s=s + ms)