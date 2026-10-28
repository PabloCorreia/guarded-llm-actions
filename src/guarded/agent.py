"""The conversational side: a manual tool-use loop with Claude.

The model can only *propose* and *confirm* through the engine. Whatever it
says, the engine decides, and the guard checks the final reply.
"""

import json
import os
from dataclasses import dataclass

import anthropic

from .engine import Engine, InvoiceRequest
from .guard import review_reply

MODEL = os.environ.get("DEMO_MODEL", "claude-opus-5-5")

SYSTEM = """You help owners of small service businesses request a service invoice.

Collect: the issuer's company tax ID, the customer's company tax ID, the amount,
the month the service was provided (YYYY-MM), and a short description.

When you have everything, call propose_invoice and read the summary back to the
customer. Then stop and wait for their answer. Call confirm_invoice only after
the customer has replied yes to that summary.

Only say that an invoice was issued if confirm_invoice returned a receipt_id.
If a tool refuses, tell the customer in plain words what is missing or wrong.
A request with the same issuer, customer, amount and month as an issued invoice
is a duplicate whatever the description says. Do not suggest rewording it; a
genuine second invoice needs a person to approve it."""

TOOLS = [
    {
        "name": "propose_invoice",
        "description": "Validate an invoice request and get a summary to read back to the customer. Does not issue anything.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "issuer_id": {"type": "string", "description": "Issuer company tax ID (CNPJ)"},
                "taker_id": {"type": "string", "description": "Customer company tax ID (CNPJ)"},
                "amount": {"type": "string", "description": "Amount, e.g. 1500.00"},
                "service_month": {"type": "string", "description": "Month the service was provided, YYYY-MM"},
                "description": {"type": "string", "description": "Short description of the service"},
            },
            "required": ["issuer_id", "taker_id", "amount", "service_month", "description"],
            "additionalProperties": False,
        },
    },
    {
        "name": "confirm_invoice",
        "description": "Issue a proposed invoice. Only after the customer replied yes to its summary.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"confirmation_id": {"type": "string"}},
            "required": ["confirmation_id"],
            "additionalProperties": False,
        },
    },
]


def _run_tool(engine: Engine, name: str, args: dict, turn: int) -> dict:
    if name == "propose_invoice":
        return engine.propose(InvoiceRequest(**args), turn)
    if name == "confirm_invoice":
        return engine.confirm(args["confirmation_id"], turn)
    return {"ok": False, "reason": f"unknown tool {name}"}


@dataclass
class TurnResult:
    reply: str  # what the customer sees
    blocked: bool  # the guard replaced the model's reply
    model_text: str  # what the model wrote, kept so a block can be audited


def run_turn(client: anthropic.Anthropic, engine: Engine, messages: list, turn: int) -> TurnResult:
    """Run one customer turn to completion."""
    receipts: list[str] = []
    summaries: list[str] = []
    while True:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": "low"},
            # Server-side fallback when a request is declined. Passed through
            # extra_body so it works on SDK versions without the typed field.
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
        if response.stop_reason == "refusal":
            return TurnResult("Sorry, I can't help with that request.", False, "")

        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            outcome = _run_tool(engine, block.name, block.input, turn)
            if outcome.get("receipt_id"):
                receipts.append(outcome["receipt_id"])
            if outcome.get("summary"):
                summaries.append(outcome["summary"])
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(outcome),
                "is_error": not outcome.get("ok"),
            })
        messages.append({"role": "user", "content": results})

    text = "".join(b.text for b in response.content if b.type == "text")
    reply, blocked = review_reply(text, receipts, summaries)
    return TurnResult(reply, blocked, text)
