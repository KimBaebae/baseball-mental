from datetime import date


def month_date_range(year: int, month: int) -> dict[str, str]:
    """ISO date bounds include the first day and exclude the next month."""
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return {"$gte": start.isoformat(), "$lt": end.isoformat()}
