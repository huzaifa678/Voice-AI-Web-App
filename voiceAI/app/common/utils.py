from datetime import timedelta
import re

def parse_timedelta(duration_str: str) -> timedelta:
    """
    Convert strings like '24h', '7d', '30m', '15s' to timedelta
    """
    pattern = r"^(\d+)([smhd])$"
    match = re.match(pattern, duration_str.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration string: {duration_str}")

    value, unit = match.groups()
    value = int(value)

    if unit == "s":
        return timedelta(seconds=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    else:
        raise ValueError(f"Unknown time unit: {unit}")
