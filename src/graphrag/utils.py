from __future__ import annotations

from datetime import datetime, timezone
from typing import TypeVar
from uuid import uuid4

T = TypeVar("T")


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Create a readable globally unique identifier.

    Args:
        prefix: Domain-specific prefix identifying the object type.

    Returns:
        A prefixed UUID4-based identifier.
    """

    return f"{prefix}_{uuid4().hex}"


def scalar_to_list(value: T | list[T] | None) -> list[T] | None:
    """Wrap a scalar value in a list while leaving lists and ``None`` unchanged.

    Args:
        value: Scalar, list, or ``None`` received before normal Pydantic
            validation.

    Returns:
        The original list or ``None``, or a one-item list containing the scalar.
    """

    return value if value is None or isinstance(value, list) else [value]
