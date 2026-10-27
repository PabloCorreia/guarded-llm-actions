"""Brazilian company tax ID (CNPJ) validation, including the alphanumeric format.

Since July 2026 a CNPJ may carry letters in its first 12 positions; the last two
characters are still numeric check digits. The rule this module encodes:
validate the shape and the check digits, never just the length.
"""

import re

_SEPARATORS = re.compile(r"[.\-/\s]")
_SHAPE = re.compile(r"[0-9A-Z]{12}[0-9]{2}")
_WEIGHTS_1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_2 = (6,) + _WEIGHTS_1


def _value(char: str) -> int:
    # '0'..'9' -> 0..9 and 'A'..'Z' -> 17..42, as the tax authority specifies.
    return ord(char) - 48


def _check_digit(body: str, weights: tuple) -> int:
    remainder = sum(_value(c) * w for c, w in zip(body, weights)) % 11
    return 0 if remainder < 2 else 11 - remainder


def normalize(raw: str) -> str:
    """Remove formatting only. Letters are kept: dropping them is the bug."""
    return _SEPARATORS.sub("", raw).upper()


def complete(body: str) -> str:
    """Append the two check digits to a 12-character body."""
    body = normalize(body)
    if not re.fullmatch(r"[0-9A-Z]{12}", body):
        raise ValueError("a CNPJ body has 12 characters, digits or uppercase letters")
    first = _check_digit(body, _WEIGHTS_1)
    second = _check_digit(body + str(first), _WEIGHTS_2)
    return f"{body}{first}{second}"


def is_valid(raw: str) -> bool:
    cnpj = normalize(raw)
    if not _SHAPE.fullmatch(cnpj):
        return False
    if len(set(cnpj)) == 1:  # e.g. fourteen zeros: right digits, not a real ID
        return False
    return complete(cnpj[:12]) == cnpj
