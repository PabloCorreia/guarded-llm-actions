import unittest
from decimal import Decimal

from guarded import tax_id
from guarded.engine import Engine, InvoiceRequest
from guarded.rates import Rate, RateSource

ISSUER = tax_id.complete("TEST0ISSUER1")
CUSTOMER = tax_id.complete("TEST0CLIENT1")


def rates_on_file(period="2026-09"):
    def lookup(issuer_id):
        if tax_id.normalize(issuer_id) == ISSUER:
            return Rate(ISSUER, Decimal("6.00"), period)
        return None
    return lookup


def request(**changes):
    fields = dict(issuer_id=ISSUER, taker_id=CUSTOMER, amount="1500.00",
                  service_month="2026-10", description="Bookkeeping, October")
    fields.update(changes)
    return InvoiceRequest(**fields)


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(RateSource(rates_on_file()))

    def test_happy_path_needs_a_later_turn(self):
        proposed = self.engine.propose(request(), turn=1)
        self.assertTrue(proposed["ok"])
        issued = self.engine.confirm(proposed["confirmation_id"], turn=2)
        self.assertTrue(issued["ok"])
        self.assertTrue(issued["receipt_id"].startswith("R-"))

    def test_confirm_in_the_same_turn_is_refused(self):
        cid = self.engine.propose(request(), turn=1)["confirmation_id"]
        result = self.engine.confirm(cid, turn=1)
        self.assertFalse(result["ok"])
        self.assertIn("not answered", result["reason"])

    def test_a_confirmation_is_used_once(self):
        cid = self.engine.propose(request(), turn=1)["confirmation_id"]
        self.assertTrue(self.engine.confirm(cid, turn=2)["ok"])
        self.assertFalse(self.engine.confirm(cid, turn=3)["ok"])

    def test_paraphrased_duplicate_is_refused(self):
        cid = self.engine.propose(request(), turn=1)["confirmation_id"]
        self.engine.confirm(cid, turn=2)
        again = self.engine.propose(request(amount="1500", description="October bookkeeping"), turn=3)
        self.assertFalse(again["ok"])
        self.assertIn("already issued", again["reason"])

    def test_two_proposals_cannot_both_issue(self):
        first = self.engine.propose(request(), turn=1)["confirmation_id"]
        second = self.engine.propose(request(description="other words"), turn=1)["confirmation_id"]
        self.assertTrue(self.engine.confirm(first, turn=2)["ok"])
        self.assertFalse(self.engine.confirm(second, turn=2)["ok"])

    def test_no_rate_means_no_invoice_and_the_counter_shows_it(self):
        source = RateSource(lambda issuer_id: None)
        engine = Engine(source)
        for turn in range(1, 13):
            self.assertFalse(engine.propose(request(), turn=turn)["ok"])
        self.assertEqual((source.counter.asked, source.counter.answered), (12, 0))

    def test_a_failing_lookup_is_refused_not_defaulted(self):
        def broken(issuer_id):
            raise KeyError("tab not found")
        engine = Engine(RateSource(broken))
        result = engine.propose(request(), turn=1)
        self.assertFalse(result["ok"])
        self.assertIn("lookup failed", result["reason"])

    def test_a_stale_rate_is_refused(self):
        engine = Engine(RateSource(rates_on_file(period="2026-03")))
        result = engine.propose(request(), turn=1)
        self.assertFalse(result["ok"])
        self.assertIn("too old", result["reason"])

    def test_bad_inputs_are_refused(self):
        wrong_digits = "01" if CUSTOMER.endswith("00") else "00"
        cases = [
            request(issuer_id="Acme Studio Ltda"),
            request(taker_id=CUSTOMER[:12] + wrong_digits),
            request(amount="-10"),
            request(amount="10.005"),
            request(amount="ten"),
            request(service_month="10/2026"),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertFalse(self.engine.propose(case, turn=1)["ok"])

    def test_every_decision_is_in_the_audit_trail(self):
        cid = self.engine.propose(request(), turn=1)["confirmation_id"]
        self.engine.confirm(cid, turn=1)
        self.engine.confirm(cid, turn=2)
        self.assertEqual([event for event, _ in self.engine.audit], ["proposed", "refused", "issued"])


if __name__ == "__main__":
    unittest.main()
