"""Pure reporting policy and agenda calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Literal


ReportingMode = Literal["native", "legacy_mirror", "preprod_refresh"]


@dataclass(frozen=True, slots=True)
class ReportingPolicy:
    mode: ReportingMode
    write_enabled: bool
    authoritative_refresh: bool


def reporting_policy(raw_mode: object) -> ReportingPolicy:
    """Parse persisted configuration and fail closed for unknown values."""
    mode = str(raw_mode or "").strip()
    if mode == "native":
        return ReportingPolicy("native", True, False)
    if mode == "preprod_refresh":
        return ReportingPolicy("preprod_refresh", True, True)
    return ReportingPolicy("legacy_mirror", False, False)


def rounded_percentage_average(percentages: Iterable[float]) -> int:
    """Return the deterministic half-up average used by direction agendas."""
    values = tuple(Decimal(str(value)) for value in percentages)
    if not values:
        return 0
    average = sum(values, Decimal("0")) / Decimal(len(values))
    return int(average.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
