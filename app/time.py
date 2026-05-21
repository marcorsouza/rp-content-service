"""Time helpers for persistence."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return UTC now as a naive datetime for Prisma/Postgres DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
