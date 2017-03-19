def dash_to_studly(s):
    l = list(s)
    l[0] = l[0].upper()
    delims = "-_"
    for i, c in enumerate(l):
        if c in delims:
            if (i+1) < len(l):
                l[i+1] = l[i+1].upper()
    out = "".join(l)
    for d in delims:
        out = out.replace(d, "")
    return out
