from datetime import UTC, datetime


def utc_now() -> datetime:
    """MySQL DATETIME stores naive UTC; add a zone only at API boundaries."""
    return datetime.now(UTC).replace(tzinfo=None)
