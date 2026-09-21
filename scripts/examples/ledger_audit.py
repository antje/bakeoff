"""Build the ledger-audit example: six dependent turns of state and arithmetic.

What this produces, under examples/ledger-audit/:

- logs.jsonl: 20 review sessions from a finance assistant, each a sequence of
  posted batches with the position the ledger system computed after each
  one. The "before /eval-build" state.
- trajectories.jsonl: each session as a six-turn conversation. Every turn
  posts a batch of transactions (transfers, fees, deposits, and reversals of
  earlier entries by id) and asks one exact question about the running state.

Why this shape. Nothing here is hard on any single turn; what is hard is
turn six, which is only right if turns one to five were carried correctly.
The context grows every turn, a reversal on turn four reaches back to turn
two, and a slip anywhere poisons everything after it. This is the workload
where small models' accuracy collapses and a reasoning budget earns its
tokens, so the verdict should land on the model that is right, whatever it
costs per call, because cost per *correct* call is what the harness ranks.
Consistency across runs matters here more than anywhere else.

Ground truth. The generator posts every batch to its own ledger and writes
down the answer, so every expected value is exact. Answers vary per session
and per turn, so no constant passes and the trivial baseline is zero.

Run:  uv run python scripts/examples/ledger_audit.py
"""

from __future__ import annotations

from _common import rng, write_example

from harness.models import Expected, Trajectory, Turn

ACCOUNTS = ["OPS", "PAY", "RES"]

SYSTEM_TEMPLATE = """You are the ledger assistant for a small company's month-end review. Three accounts exist: OPS (operating), PAY (payroll), RES (reserve). Opening balances: OPS {ops}, PAY {pay}, RES {res}. All amounts are whole units of one currency.

Each message posts a batch of transactions, one per line, in the form:
  <id> DEPOSIT <amount> TO <account>
  <id> FEE <amount> ON <account>
  <id> TRANSFER <amount> FROM <account> TO <account>
  <id> REVERSE <earlier id>
A REVERSE entry undoes the named earlier transaction exactly (a reversed transfer moves the amount back; a reversed fee or deposit is cancelled). A transaction can be reversed at most once, and REVERSE entries themselves cannot be reversed.

Every batch ends with one question. Answer it with the number alone on the first line, no currency, no separators, no words before it. You may add one line of working after it."""


class Ledger:
    """The reference implementation the model is being compared against."""

    def __init__(self, opening: dict[str, int]):
        self.balances = dict(opening)
        self.posted: dict[str, tuple[str, int, str | None, str | None]] = {}
        self.reversed: set[str] = set()
        self.large_count = 0  # non-reversal entries with amount above 500

    def apply(self, kind: str, amount: int, src: str | None, dst: str | None, sign: int) -> None:
        if kind == "DEPOSIT":
            self.balances[dst] += sign * amount
        elif kind == "FEE":
            self.balances[src] -= sign * amount
        else:
            self.balances[src] -= sign * amount
            self.balances[dst] += sign * amount

    def post(self, txn_id: str, line: tuple) -> str:
        kind = line[0]
        if kind == "REVERSE":
            target = line[1]
            k, amount, src, dst = self.posted[target]
            self.apply(k, amount, src, dst, sign=-1)
            self.reversed.add(target)
            return f"{txn_id} REVERSE {target}"
        _, amount, src, dst = line
        self.apply(kind, amount, src, dst, sign=+1)
        self.posted[txn_id] = (kind, amount, src, dst)
        if amount > 500:
            self.large_count += 1
        if kind == "DEPOSIT":
            return f"{txn_id} DEPOSIT {amount} TO {dst}"
        if kind == "FEE":
            return f"{txn_id} FEE {amount} ON {src}"
        return f"{txn_id} TRANSFER {amount} FROM {src} TO {dst}"


def number_pattern(value: int) -> str:
    """The answer alone on the first line; a thousands separator is tolerated."""
    if abs(value) >= 1000:
        head, tail = divmod(abs(value), 1000)
        digits = rf"{head},?{tail:03d}"
    else:
        digits = str(abs(value))
    sign = "" if value >= 0 else "-"
    return rf"^\s*[^\n]*(?<![\d,-]){sign}{digits}(?![\d,])"


def build() -> tuple[list[dict], list[Trajectory]]:
    random = rng()
    logs: list[dict] = []
    trajectories: list[Trajectory] = []
    for i in range(20):
        opening = {a: random.randint(6000, 24000) for a in ACCOUNTS}
        ledger = Ledger(opening)
        counter = 0
        batches: list[dict] = []
        turns: list[Turn] = []
        reversible: list[str] = []
        for turn_index in range(6):
            lines: list[str] = []
            for _ in range(random.randint(4, 6)):
                counter += 1
                txn_id = f"T{counter:02d}"
                can_reverse = [t for t in reversible if t not in ledger.reversed]
                roll = random.random()
                if turn_index >= 1 and can_reverse and roll < 0.22:
                    entry: tuple = ("REVERSE", random.choice(can_reverse))
                elif roll < 0.45:
                    src, dst = random.sample(ACCOUNTS, 2)
                    entry = ("TRANSFER", random.randint(1, 30) * 50, src, dst)
                elif roll < 0.75:
                    entry = ("FEE", random.randint(1, 12) * 25, random.choice(ACCOUNTS), None)
                else:
                    entry = ("DEPOSIT", random.randint(2, 40) * 50, None, random.choice(ACCOUNTS))
                lines.append(ledger.post(txn_id, entry))
                if entry[0] != "REVERSE":
                    reversible.append(txn_id)
            # Questions: balances mostly, one count and one net change per session.
            if turn_index == 2:
                question = "How many non-REVERSE transactions posted so far have an amount above 500?"
                answer = ledger.large_count
            elif turn_index == 4:
                account = random.choice(ACCOUNTS)
                question = f"What is the net change of {account} since the opening balance? Negative if it went down."
                answer = ledger.balances[account] - opening[account]
            else:
                account = random.choice(ACCOUNTS)
                question = f"What is the balance of {account} now?"
                answer = ledger.balances[account]
            batches.append({"lines": lines, "question": question, "answer": answer, "balances": dict(ledger.balances)})
            turns.append(
                Turn(
                    input="\n".join(lines) + f"\n\n{question}",
                    expected=Expected(pattern=number_pattern(answer)),
                )
            )
        session_id = f"LED-{7200 + i}"
        logs.append({"session_id": session_id, "opening": opening, "batches": batches})
        trajectories.append(
            Trajectory(
                trajectory_id=session_id,
                system=SYSTEM_TEMPLATE.format(ops=opening["OPS"], pay=opening["PAY"], res=opening["RES"]),
                turns=turns,
            )
        )
    return logs, trajectories


if __name__ == "__main__":
    logs, trajectories = build()
    out = write_example("ledger-audit", logs, trajectories)
    print(f"wrote {len(trajectories)} trajectories to {out}")
