"""Build the tool-router example: exact tool calls with state carried across turns.

What this produces, under examples/tool-router/:

- logs.jsonl: 20 support sessions as a copilot would log them: the operator's
  messages, the tool calls the copilot made, and what each tool returned. The
  "before /eval-build" state.
- trajectories.jsonl: the same sessions as three-turn conversations with the
  five tool schemas attached. Each turn expects one exact tool call, and each
  turn carries the recorded tool output so the next turn can depend on it.

Why this shape. This is the agent case proper: the output is a function call
whose arguments must be exactly right, and the right arguments come from an
earlier tool result, not from the prompt. The customer id arrives on turn 1,
the order id and total on turn 2, and turn 3 has to use them (and, for a
partial refund, do arithmetic on them). Text fluency buys nothing; a near
miss (right tool, wrong amount) is worse than a refusal. Tool-call fidelity
separates models here, and some providers do not serve tools for an open
model at all, which the report surfaces as a note rather than as a zero.

Ground truth. Customers, orders, and amounts are generated, so the expected
call on every turn is known by construction. Enum arguments (refund reason,
escalation severity) keep the argument match exact. No constant call passes
any turn, so the trivial baseline is zero.

Run:  uv run python scripts/examples/tool_router.py
"""

from __future__ import annotations

import json

from _common import rng, write_example

from harness.models import Expected, Trajectory, Turn

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "Find a customer record by email address. Returns the customer id and their order ids, newest first.",
            "parameters": {
                "type": "object",
                "properties": {"email": {"type": "string", "description": "The customer's email address."}},
                "required": ["email"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Fetch one order by id. Returns status, line items, and the total in cents.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "The order id, e.g. ORD-10042."}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Refund an amount on an order. amount_cents must not exceed the order total.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "amount_cents": {"type": "integer", "description": "Amount to refund, in cents."},
                    "reason": {"type": "string", "enum": ["damaged", "late", "wrong_item", "other"]},
                },
                "required": ["order_id", "amount_cents", "reason"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_address",
            "description": "Replace the shipping address on a customer's account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "address": {"type": "string", "description": "The full new address as one line."},
                },
                "required": ["customer_id", "address"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate",
            "description": "Escalate a support ticket to a human specialist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "high"]},
                },
                "required": ["ticket_id", "severity"],
                "additionalProperties": False,
            },
        },
    },
]

SYSTEM = (
    "You are the support copilot for an online store. The operator tells you what the customer "
    "needs; you act by calling exactly one tool per message, with arguments taken from the "
    "conversation and from earlier tool results. Never invent ids or amounts. Do not answer in "
    "text when a tool call is the right action."
)

FIRST = ["mira", "tomas", "aisha", "jonas", "priya", "lena", "diego", "noor", "felix", "hana",
         "sven", "ines", "kofi", "yuki", "omar", "elif", "ravi", "greta", "malik", "sofia"]
LAST = ["okafor", "lindqvist", "haddad", "brenner", "nair", "moreau", "castillo", "rahimi",
        "weber", "sato", "berg", "duarte", "mensah", "tanaka", "farouk", "demir", "iyer",
        "holm", "aziz", "rossi"]
DOMAINS = ["example.com", "mail.example.org", "corp.example.net"]
ITEMS = ["desk sensor kit", "standing mat", "monitor arm", "cable tray", "footrest", "lamp", "headset stand"]
ADDRESSES = [
    "12 Rue Lepic, 75018 Paris, France",
    "44 Hollow Way, Oxford OX4 2NB, United Kingdom",
    "Kastanienallee 9, 10435 Berlin, Germany",
    "301 Pine St Apt 4B, Seattle, WA 98101, USA",
    "Via dei Serpenti 88, 00184 Rome, Italy",
]


def build() -> tuple[list[dict], list[Trajectory]]:
    random = rng()
    logs: list[dict] = []
    trajectories: list[Trajectory] = []
    variants = ["full_refund", "half_refund", "update_address", "escalate"] * 5
    random.shuffle(variants)
    for i, variant in enumerate(variants):
        first, last = FIRST[i], LAST[i]
        email = f"{first}.{last}@{random.choice(DOMAINS)}"
        customer_id = f"CUS-{random.randint(10000, 99999)}"
        order_ids = [f"ORD-{random.randint(10000, 99999)}" for _ in range(random.randint(2, 4))]
        latest = order_ids[0]
        items = random.sample(ITEMS, random.randint(1, 3))
        # Even totals so a half refund is a whole number of cents.
        total_cents = 2 * random.randint(1500, 24000)
        ticket_id = f"TK-{random.randint(1000, 9999)}"

        customer_result = json.dumps(
            {"customer_id": customer_id, "name": f"{first.title()} {last.title()}", "orders": order_ids}
        )
        order_result = json.dumps(
            {
                "order_id": latest,
                "status": random.choice(["delivered", "shipped", "delivered"]),
                "items": items,
                "total_cents": total_cents,
                "currency": "USD",
            }
        )

        if variant == "full_refund":
            third_input = "The customer says it arrived damaged. Refund the order in full."
            third_call = {"name": "issue_refund", "arguments": {"order_id": latest, "amount_cents": total_cents, "reason": "damaged"}}
        elif variant == "half_refund":
            third_input = "It arrived two weeks late. Refund half of the order total as a goodwill gesture."
            third_call = {"name": "issue_refund", "arguments": {"order_id": latest, "amount_cents": total_cents // 2, "reason": "late"}}
        elif variant == "update_address":
            address = random.choice(ADDRESSES)
            third_input = f"They have moved. Update the shipping address on the account to: {address}"
            third_call = {"name": "update_address", "arguments": {"customer_id": customer_id, "address": address}}
        else:
            third_input = f"They say the box was opened and items are missing. Escalate ticket {ticket_id} as high severity."
            third_call = {"name": "escalate", "arguments": {"ticket_id": ticket_id, "severity": "high"}}
        third_result = json.dumps({"ok": True})

        session_id = f"SES-{3100 + i}"
        turns = [
            {
                "input": f"A customer with the email {email} is asking about the latest order on their account. Look up the customer.",
                "call": {"name": "lookup_customer", "arguments": {"email": email}},
                "result": customer_result,
            },
            {
                "input": "Now pull up that latest order.",
                "call": {"name": "get_order", "arguments": {"order_id": latest}},
                "result": order_result,
            },
            {"input": third_input, "call": third_call, "result": third_result},
        ]
        logs.append({"session_id": session_id, "variant": variant, "turns": turns})
        trajectories.append(
            Trajectory(
                trajectory_id=session_id,
                system=SYSTEM,
                tools=TOOLS,
                turns=[
                    Turn(
                        input=turn["input"],
                        expected=Expected(tool_call=turn["call"]),
                        tool_result={turn["call"]["name"]: turn["result"]},
                    )
                    for turn in turns
                ],
            )
        )
    return logs, trajectories


if __name__ == "__main__":
    logs, trajectories = build()
    out = write_example("tool-router", logs, trajectories)
    print(f"wrote {len(trajectories)} trajectories to {out}")
