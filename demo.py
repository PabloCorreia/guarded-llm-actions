"""Walk through the four guards with fictional data. No API key needed.

    python demo.py          # offline walkthrough
    python demo.py --live   # chat with Claude (needs Anthropic credentials; costs tokens)
"""

import re
import sys
from decimal import Decimal

sys.path.insert(0, "src")

from guarded import tax_id  # noqa: E402
from guarded.engine import Engine, InvoiceRequest  # noqa: E402
from guarded.guard import review_reply  # noqa: E402
from guarded.rates import Rate, RateSource, RateUnavailable  # noqa: E402

# Fictional IDs: check digits are computed at run time, never stored in the repo.
ISSUER = tax_id.complete("DEMO0ISSUER1")
CUSTOMER = tax_id.complete("DEMO0CLIENT1")


def demo_rates(issuer_id: str):
    if tax_id.normalize(issuer_id) == ISSUER:
        return Rate(ISSUER, Decimal("6.00"), "2026-09")
    return None


def header(title: str) -> None:
    print(f"\n=== {title} ===")


def tax_ids() -> None:
    header("1. Validate the shape, not the length")
    a, b = tax_id.complete("AB1234567890"), tax_id.complete("CD1234567890")

    def legacy_key(raw):  # the old rule: the digits of the 12-character body
        return re.sub(r"\D", "", raw[:12])

    print(f"two different IDs:         {a}  {b}")
    print(f"old digits-only key:       {legacy_key(a)}  {legacy_key(b)}"
          f"   same key: {legacy_key(a) == legacy_key(b)}")
    print(f"normalized (letters kept): {tax_id.normalize(a)}  {tax_id.normalize(b)}"
          f"   same key: {tax_id.normalize(a) == tax_id.normalize(b)}")

    name = "Acme Studio Ltda"
    squeezed = tax_id.normalize(name)
    print(f"\na company name, spaces removed: {squeezed!r} ({len(squeezed)} chars)")
    print(f"length check says ID?  {len(squeezed) == 14}")
    print(f"shape + check digits:  {tax_id.is_valid(name)}")


def silent_default() -> None:
    header("2. 'Nothing failed' is not 'it worked'")

    def broken_lookup(issuer_id):
        raise KeyError("sheet tab 'RATES' not found")

    def legacy_rate(issuer_id):  # the old fail-safe
        try:
            return broken_lookup(issuer_id)
        except Exception:
            return Decimal("6.00")

    print("old code, 12 requests:", {str(legacy_rate(ISSUER)) for _ in range(12)}, "- no error raised")

    source = RateSource(broken_lookup)
    for _ in range(12):
        try:
            source.rate_for(ISSUER, "2026-10")
        except RateUnavailable:
            pass
    print("new code:", source.counter)


def duplicates() -> None:
    header("3. Duplicates are matched on facts, not on wording")
    engine = Engine(RateSource(demo_rates))
    first = InvoiceRequest(ISSUER, CUSTOMER, "1500.00", "2026-10", "Bookkeeping services, October")
    proposed = engine.propose(first, turn=1)
    print("propose:", proposed["ok"], proposed.get("confirmation_id"))
    print("confirm next turn:", engine.confirm(proposed["confirmation_id"], turn=2))

    again = InvoiceRequest(ISSUER, CUSTOMER, "1500", "2026-10", "October bookkeeping")
    print("same invoice, paraphrased:", engine.propose(again, turn=3))


def no_receipt_no_sent() -> None:
    header("4. 'Sent' comes from a receipt, not from the model")
    engine = Engine(RateSource(demo_rates))
    req = InvoiceRequest(ISSUER, CUSTOMER, "800.00", "2026-10", "Consulting")
    cid = engine.propose(req, turn=1)["confirmation_id"]
    print("confirm in the same turn:", engine.confirm(cid, turn=1))

    summary = engine.propose(InvoiceRequest(ISSUER, CUSTOMER, "900.00", "2026-10", "Audit"), turn=1)["summary"]
    reply, blocked = review_reply("Done! Your invoice has been issued.", [], [summary])
    print(f"model says 'has been issued' with no receipt -> blocked={blocked}")
    print(f"customer sees: {reply}")


def live() -> None:
    import anthropic

    from guarded.agent import run_turn

    client = anthropic.Anthropic()
    engine = Engine(RateSource(demo_rates))
    messages: list = []
    print(f"Fictional issuer ID: {ISSUER}   fictional customer ID: {CUSTOMER}")
    print("Ask for an invoice. Empty line to quit.\n")
    turn = 0
    while True:
        text = input("you> ").strip()
        if not text:
            break
        turn += 1
        messages.append({"role": "user", "content": text})
        result = run_turn(client, engine, messages, turn)
        print(f"agent> {result.reply}")
        if result.blocked:
            print(f"   [guard replaced the model's reply, which was: {result.model_text!r}]")
    print("\naudit trail:")
    for event, result in engine.audit:
        print(f"  {event}: {result}")


if __name__ == "__main__":
    if "--live" in sys.argv:
        live()
    else:
        tax_ids()
        silent_default()
        duplicates()
        no_receipt_no_sent()
