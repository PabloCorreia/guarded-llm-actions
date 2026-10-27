"""The issuing engine. The model proposes; the engine decides.

Every check here exists because a prompt instruction alone did not hold.
"""

import itertools
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable, Optional

from . import tax_id
from .rates import Rate, RateSource, RateUnavailable

_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


@dataclass(frozen=True)
class InvoiceRequest:
    issuer_id: str
    taker_id: str
    amount: str
    service_month: str  # "YYYY-MM"
    description: str

    def dedup_key(self) -> tuple:
        # The description is left out on purpose: a model paraphrases it, so the
        # same invoice asked for twice comes back in different words.
        return (
            tax_id.normalize(self.issuer_id),
            tax_id.normalize(self.taker_id),
            Decimal(self.amount),
            self.service_month,
        )


@dataclass
class _Pending:
    request: InvoiceRequest
    rate: Rate
    turn: int
    used: bool = False


def _refuse(reason: str) -> dict:
    return {"ok": False, "reason": reason}


class Engine:
    def __init__(self, rates: RateSource, issue: Optional[Callable[[InvoiceRequest, Rate], str]] = None):
        self._rates = rates
        self._issue = issue or self._fake_issue
        self._pending: dict[str, _Pending] = {}
        self._issued: dict[tuple, str] = {}  # dedup key -> receipt
        self._confirmation_ids = itertools.count(1)
        self._receipt_ids = itertools.count(1)
        self._invoice_numbers = itertools.count(1)
        self.audit: list[tuple] = []

    def propose(self, request: InvoiceRequest, turn: int) -> dict:
        problems = self._validate(request)
        if problems:
            return self._log("refused", _refuse("; ".join(problems)))

        receipt = self._issued.get(request.dedup_key())
        if receipt:
            return self._log("refused", _refuse(f"this invoice was already issued (receipt {receipt})"))

        try:
            rate = self._rates.rate_for(request.issuer_id, request.service_month)
        except RateUnavailable as exc:
            return self._log("refused", _refuse(str(exc)))

        confirmation_id = f"C-{next(self._confirmation_ids):04d}"
        self._pending[confirmation_id] = _Pending(request, rate, turn)
        summary = (
            f"Invoice from {request.issuer_id} to {request.taker_id}, "
            f"amount {request.amount}, for services in {request.service_month}: {request.description}. "
            f"Tax rate {rate.percent}% (from the {rate.period} tax filing)."
        )
        return self._log("proposed", {"ok": True, "confirmation_id": confirmation_id, "summary": summary})

    def confirm(self, confirmation_id: str, turn: int) -> dict:
        pending = self._pending.get(confirmation_id)
        if pending is None:
            return self._log("refused", _refuse("unknown confirmation id"))
        if pending.used:
            return self._log("refused", _refuse("this confirmation was already used"))
        if turn <= pending.turn:
            # The customer has not replied since the summary was proposed.
            # Proposing and confirming in the same turn is how a model ends up
            # announcing "sent" on its own.
            return self._log("refused", _refuse("the customer has not answered the summary yet"))

        key = pending.request.dedup_key()
        if key in self._issued:
            return self._log("refused", _refuse(f"this invoice was already issued (receipt {self._issued[key]})"))

        invoice_number = self._issue(pending.request, pending.rate)
        receipt = f"R-{next(self._receipt_ids):04d}"
        pending.used = True
        self._issued[key] = receipt
        return self._log("issued", {"ok": True, "receipt_id": receipt, "invoice_number": invoice_number})

    def _validate(self, request: InvoiceRequest) -> list[str]:
        problems = []
        if not tax_id.is_valid(request.issuer_id):
            problems.append("the issuer tax ID is not valid")
        if not tax_id.is_valid(request.taker_id):
            problems.append("the customer tax ID is not valid")
        try:
            amount = Decimal(request.amount)
            if amount <= 0 or amount != amount.quantize(Decimal("0.01")):
                problems.append("the amount must be positive, with at most 2 decimals")
        except InvalidOperation:
            problems.append("the amount is not a number")
        if not _MONTH.fullmatch(request.service_month):
            problems.append("the service month must look like 2026-09")
        return problems

    def _fake_issue(self, request: InvoiceRequest, rate: Rate) -> str:
        return f"DEMO-{next(self._invoice_numbers):06d}"

    def _log(self, event: str, result: dict) -> dict:
        self.audit.append((event, result))
        return result
