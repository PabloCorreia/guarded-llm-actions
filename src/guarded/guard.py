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

# A claim right after a negation is a denial: "Nothing has been issued yet".
# Found in a live run, where the guard blocked a true sentence.
_NEGATION_BEFORE = re.compile(r"(\b(not|nothing|never|no)\b|n't|\b(não|nada|nenhum\w*)\b)\W*(\w+\W+){0,2}$", re.IGNORECASE)

NOT_ISSUED = "I haven't issued the invoice yet."


def _claims_completion(text: str) -> bool:
    return any(not _NEGATION_BEFORE.search(text[:m.start()]) for m in _CLAIM.finditer(text))


def safe_reply(summaries: list[str]) -> str:
    # The replacement must carry what the customer needs to answer: the model's
    # reply is gone, so a "see the summary above" would point at nothing.
    if not summaries:
        return f"{NOT_ISSUED} Tell me the details and I'll prepare a summary for you to check."
    return f"{NOT_ISSUED} Here is what I have:\n\n{summaries[-1]}\n\nReply 'yes' to issue it, or tell me what to change."


def review_reply(text: str, receipts_this_turn: list[str], summaries_this_turn: list[str] = ()) -> tuple[str, bool]:
    """Return the reply to send and whether it was blocked."""
    if receipts_this_turn or not _claims_completion(text):
        return text, False
    return safe_reply(list(summaries_this_turn)), True
