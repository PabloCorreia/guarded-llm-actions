"""Where the tax rate comes from, and how we notice when it doesn't come.

There is deliberately no default rate. A default makes a broken lookup look
healthy: no error, a plausible number, and nobody finds out.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional


class RateUnavailable(Exception):
    """The engine refuses to issue rather than guess."""


@dataclass(frozen=True)
class Rate:
    issuer_id: str
    percent: Decimal
    period: str  # "YYYY-MM" of the tax filing the rate was read from


class CallCounter:
    """Counts what goes into a dependency and what comes back.

    Zero results is ambiguous. Twelve requests and zero answers is not.
    """

    def __init__(self, name: str):
        self.name = name
        self.asked = 0
        self.answered = 0

    @property
    def unanswered(self) -> int:
        return self.asked - self.answered

    def __str__(self) -> str:
        return f"{self.name}: asked={self.asked} answered={self.answered} unanswered={self.unanswered}"


def months_between(earlier: str, later: str) -> int:
    y1, m1 = map(int, earlier.split("-"))
    y2, m2 = map(int, later.split("-"))
    return (y2 - y1) * 12 + (m2 - m1)


class RateSource:
    def __init__(self, lookup: Callable[[str], Optional[Rate]], max_age_months: int = 2):
        self._lookup = lookup
        self._max_age = max_age_months
        self.counter = CallCounter("tax-rate lookup")

    def rate_for(self, issuer_id: str, service_month: str) -> Rate:
        self.counter.asked += 1
        try:
            rate = self._lookup(issuer_id)
        except Exception as exc:
            raise RateUnavailable(f"tax-rate lookup failed: {exc}") from exc
        if rate is None:
            raise RateUnavailable("no tax rate on file for this issuer")
        self.counter.answered += 1

        age = months_between(rate.period, service_month)
        if age > self._max_age:
            raise RateUnavailable(
                f"the latest tax filing on file is from {rate.period}, too old for {service_month}"
            )
        return rate
