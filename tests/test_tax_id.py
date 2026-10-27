import random
import string
import unittest

from guarded import tax_id

ALPHABET = string.digits + string.ascii_uppercase


def reference_check_digits(body: str) -> str:
    """Independent implementation, written separately from the module on purpose:
    a checker that shares code with what it checks does not check anything."""
    values = [ord(c) - ord("0") for c in body]
    digits = []
    for size in (12, 13):
        weights = []
        w = 2
        for _ in range(size):  # weights run 2..9 from the right, then wrap
            weights.append(w)
            w = 2 if w == 9 else w + 1
        total = sum(v * wt for v, wt in zip(values, reversed(weights)))
        r = total % 11
        dv = 0 if r < 2 else 11 - r
        digits.append(dv)
        values.append(dv)
    return f"{digits[0]}{digits[1]}"


def random_body(rng: random.Random) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(12))


class TaxIdTest(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(2026)

    def test_check_digits_match_independent_implementation(self):
        for _ in range(2000):
            body = random_body(self.rng)
            self.assertEqual(tax_id.complete(body), body + reference_check_digits(body))

    def test_every_wrong_check_digit_is_rejected(self):
        for _ in range(200):
            body = random_body(self.rng)
            good = body + reference_check_digits(body)
            if len(set(good)) == 1:
                continue
            self.assertTrue(tax_id.is_valid(good))
            for dv in range(100):
                candidate = f"{body}{dv:02d}"
                self.assertEqual(tax_id.is_valid(candidate), candidate == good)

    def test_formatting_is_accepted(self):
        cnpj = tax_id.complete("AB12CD34EF56")
        formatted = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
        self.assertTrue(tax_id.is_valid(formatted.lower()))

    def test_a_company_name_of_tax_id_length_is_rejected(self):
        name = "Acme Studio Ltda"
        self.assertEqual(len(tax_id.normalize(name)), 14)
        self.assertFalse(tax_id.is_valid(name))

    def test_letters_are_kept_so_distinct_ids_stay_distinct(self):
        a, b = tax_id.complete("AB1234567890"), tax_id.complete("CD1234567890")
        self.assertNotEqual(tax_id.normalize(a), tax_id.normalize(b))

    def test_repeated_characters_are_rejected(self):
        self.assertFalse(tax_id.is_valid("0" * 14))

    def test_letters_in_check_digits_are_rejected(self):
        body = random_body(self.rng)
        self.assertFalse(tax_id.is_valid(body + "A1"))


if __name__ == "__main__":
    unittest.main()
