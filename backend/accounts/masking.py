def mask_username(name):
    """Public display form of a username: 'alice99' -> 'al***9'."""
    name = name or ''
    return name[:2] + '***' + name[-1:] if len(name) > 3 else name[:1] + '***'
