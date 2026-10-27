"""Last check on the model's reply: no completion claim without a receipt.

"Sent" must come from the engine's receipt, never from the model's sentence.
"""

import re

_CLAIM = re.compile(
    r"\b(has been|have been|was|were|is now)\s+(issued|sent|submitted)\b"
    r"|\binvoice\s+(issued|sent)\b"
    r"|\b(foi|foram)\s+(emitid|enviad)\w*"
    r"|\b(pedido|nota)\s+(enviad|emitid)\w*",
    re.IGNORECASE,
)

SAFE_REPLY = (
    "I haven't issued the invoice yet. Please check the summary above and reply "
    "'yes' to confirm, or tell me what to change."
)


def review_reply(text: str, receipts_this_turn: list[str]) -> tuple[str, bool]:
    """Return the reply to send and whether it was blocked."""
    if receipts_this_turn or not _CLAIM.search(text):
        return text, False
    return SAFE_REPLY, True
