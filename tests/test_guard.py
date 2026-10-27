import unittest

from guarded.guard import SAFE_REPLY, review_reply

CLAIMS = [
    "Done! Your invoice has been issued.",
    "The invoice was sent to the customer.",
    "Invoice issued, number 123.",
    "Pronto, a nota foi emitida!",
    "Pedido enviado!",
]

NOT_CLAIMS = [
    "Here is the summary. Shall I issue it?",
    "Once you confirm, the invoice will be sent.",
    "Which month was the service provided?",
]


class GuardTest(unittest.TestCase):
    def test_claims_without_a_receipt_are_blocked(self):
        for text in CLAIMS:
            with self.subTest(text=text):
                self.assertEqual(review_reply(text, []), (SAFE_REPLY, True))

    def test_claims_with_a_receipt_pass(self):
        for text in CLAIMS:
            with self.subTest(text=text):
                self.assertEqual(review_reply(text, ["R-0001"]), (text, False))

    def test_ordinary_replies_pass(self):
        for text in NOT_CLAIMS:
            with self.subTest(text=text):
                self.assertEqual(review_reply(text, []), (text, False))


if __name__ == "__main__":
    unittest.main()
