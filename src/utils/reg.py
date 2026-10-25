def extract_and_remove_prefixes(s, prefixes):
    if s is None:
        return s, []
    found = []
    for p in prefixes or []:
        if isinstance(s, str) and s.startswith(p):
            found.append(p)
            s = s[len(p):]
    return s, found
