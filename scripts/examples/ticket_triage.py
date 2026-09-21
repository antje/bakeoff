"""Build the ticket-triage example: short classification, high volume.

What this produces, under examples/ticket-triage/:

- logs.jsonl: 32 support tickets the way a help desk would export them, each
  with the queue a human eventually resolved it to and the plan tier the CRM
  had on file. The "before /eval-build" state.
- trajectories.jsonl: the same 32 tickets as two-turn conversations. Turn 1
  asks for the queue, turn 2 for the plan tier named in the ticket. Both are
  labels from a closed set.

Why this shape. It is the most common inference workload there is: a short
prompt, a one-word answer, thousands of times a day. Nobody waits on one call;
the bill and the misroute rate are what a team feels. Every capable model
should score near the ceiling here, so the verdict should come down to price,
and the point of running it is to see that a large model buys nothing.

Ground truth. Each ticket is assembled from one queue-specific cue, one
queue-specific detail, one neutral distractor, and one plan mention, so the
queue and the plan are known by construction and are independent of each
other (every queue has one ticket per plan). Eight queues, four plans, so the
trivial baselines are 12.5% and 25%.

Run:  uv run python scripts/examples/ticket_triage.py
"""

from __future__ import annotations

from _common import rng, write_example

from harness.models import Expected, Trajectory, Turn

PRODUCT = "Loopwire"

POLICY = f"""You triage inbound support tickets for {PRODUCT}, a team analytics product that also ships a desk sensor kit. Route each ticket to exactly one queue:

- billing: questions about an invoice, a charge, tax, or a receipt, where the customer is not asking for money back
- refunds: the customer asks for money back
- shipping: delivery, tracking, or transit damage of the sensor kit
- access: cannot sign in, password reset, two-factor lockout, SSO problems
- bug: something in the product is broken or shows an error
- feature: a request for something the product does not do today
- security: a suspected account compromise, phishing, or a vulnerability report
- cancel: the customer wants to close their subscription or account

Answer each question with exactly one word from the set offered, on the first line, with no preamble."""

QUEUES = ["billing", "refunds", "shipping", "access", "bug", "feature", "security", "cancel"]
PLANS = ["free", "pro", "team", "enterprise"]

# (subject, cue sentence, detail sentence) x 4 per queue. Cues name the situation
# without using another queue's word, so the label is decidable from the policy.
TICKETS: dict[str, list[tuple[str, str, str]]] = {
    "billing": [
        ("Invoice for September looks wrong", "The invoice we received this morning shows 14 seats but we only have 11 active users.", "Could you reissue it with the correct seat count and our VAT id, DE811223344?"),
        ("Receipt needed for last payment", "Our finance team needs a proper receipt for the payment that went through on the 3rd.", "The card statement just says LOOPWIRE and they will not accept that."),
        ("Charged in USD instead of EUR", "We were charged in dollars this month even though our account is set to euros.", "The amount is right, it is only the currency that changed, and it makes reconciliation painful."),
        ("Question about proration", "We added three people mid-month and I want to understand how the prorated line on the invoice was calculated.", "It does not match what the pricing page suggested."),
    ],
    "refunds": [
        ("Please refund the duplicate charge", "We were charged twice on the 12th, once for 240 and once for 240 again, and I would like the second one refunded.", "The bank reference for the duplicate is LW-88213."),
        ("Money back for unused seats", "We paid for a year up front and then shrank the team, so I am asking for a refund on the six seats nobody used.", "Happy to provide the usage export if that helps."),
        ("Refund request after outage", "The service was down for most of Tuesday and we would like that day refunded as your SLA promises.", "Our account manager said to send the request here."),
        ("Return the sensor kit and refund it", "The sensor kit turned out to be the wrong fit for our office, so I want to send it back and get the purchase refunded.", "It is unopened and still in the original box."),
    ],
    "shipping": [
        ("Sensor kit has not arrived", "We ordered the desk sensor kit three weeks ago and the tracking page has not updated since it left the warehouse.", "The order number is LW-ORD-5521."),
        ("Kit arrived with a cracked housing", "The sensor kit was delivered today and two of the sensors have cracked housings from the transit.", "The outer box was also crushed on one corner."),
        ("Wrong delivery address on the kit", "The kit is on its way to our old office; we moved last month and I need the delivery redirected.", "The courier says only the sender can change the address."),
        ("Customs hold on our kit", "The sensor kit shipment is being held at customs in Zurich and they are asking for a commercial invoice from you.", "Can you send one so it gets released?"),
    ],
    "access": [
        ("Locked out after phone change", "I got a new phone and my two-factor codes no longer work, so I cannot get into my account at all.", "I do not have the backup codes anywhere."),
        ("Password reset email never arrives", "I have requested a password reset four times and nothing shows up, not even in spam.", "Other emails from you reach me fine."),
        ("SSO login loops back to the sign-in page", "Since this morning our Okta sign-in just sends everyone back to the login page without an error.", "Nothing changed on our side as far as we know."),
        ("Cannot sign in on the desktop app", "The web app works but the desktop app rejects my credentials every time.", "I have reinstalled it once already."),
    ],
    "bug": [
        ("Dashboard shows an error on load", "Since the update yesterday the team dashboard shows 'Something went wrong (code 500)' every time we open it.", "It happens in Chrome and Safari for everyone on the team."),
        ("Export produces an empty CSV", "Exporting the weekly report gives a CSV with only the header row, no data.", "The same report renders fine on screen."),
        ("Timezone wrong in the activity chart", "The activity chart is shifted by two hours for our whole team since the clocks changed.", "Our workspace timezone is set correctly."),
        ("Notifications fire twice", "Every alert now arrives twice, once by email and once again a minute later.", "It started about a week ago."),
    ],
    "feature": [
        ("Could you add a Slack digest?", "It would help us a lot if the weekly summary could be posted to a Slack channel instead of only email.", "Right now someone copies it over by hand."),
        ("Request: custom fields on teams", "We would like to tag teams with a cost centre so the reports can be grouped by it.", "Is that something you are considering?"),
        ("API endpoint for sensor data", "We want to pull the raw sensor readings into our own warehouse and there is no endpoint for that today.", "Even a nightly export would do."),
        ("Dark mode for the dashboard", "Half the office runs dark themes everywhere and the dashboard is the one bright window left.", "A dark theme would be very welcome."),
    ],
    "security": [
        ("Suspicious login from another country", "I received an alert about a sign-in to my account from a city I have never been to.", "I have changed my password but want you to check what was accessed."),
        ("Phishing email impersonating you", "Several of our staff got an email pretending to be from your billing team with a link to a fake login page.", "I have attached the headers."),
        ("Possible vulnerability in the share links", "I noticed that report share links can be guessed by incrementing the id, which looks like an access control gap.", "Happy to walk your team through it."),
        ("API key leaked in a public repo", "One of our developers accidentally committed our API key to a public repository.", "Please revoke it and tell us what it was used for."),
    ],
    "cancel": [
        ("Close our account at the end of the month", "We are consolidating tools and will not be renewing, so please close our account when the current period ends.", "We would like an export of our data before that."),
        ("Cancel the subscription", "The team that used this has been disbanded and nobody is using it any more, so please cancel our subscription.", "There is nothing wrong with the product."),
        ("Stop the renewal", "Our contract renews on the 1st and we do not want it to; please stop the auto-renewal.", "We may come back next year."),
        ("Downgrading to closing the account", "We tried the smaller plan for a month and it is not worth keeping, so please close the account entirely.", "Confirm once it is done."),
    ],
}

DISTRACTORS = [
    "Thanks for the quick help last time, by the way.",
    "We are based in Berlin if that matters for time zones.",
    "I have attached a screenshot.",
    "Our admin is on leave this week so I am writing instead.",
    "Sorry if this is the wrong place to ask.",
    "We have been customers since 2024.",
    "Let me know if you need anything else from us.",
    "I am writing from my personal email because the work one is down.",
]

PLAN_MENTIONS = {
    "free": ["We are on the free plan.", "Plan: Free.", "We have not upgraded from the free tier yet.", "Account type: free."],
    "pro": ["We are on the Pro plan.", "Plan: Pro.", "We pay for Pro monthly.", "Account type: pro."],
    "team": ["We are on the Team plan.", "Plan: Team.", "We are a Team plan customer.", "Account type: team."],
    "enterprise": ["We are on the Enterprise plan.", "Plan: Enterprise.", "We have an Enterprise agreement with you.", "Account type: enterprise."],
}

NAMES = ["Mira", "Tomas", "Aisha", "Jonas", "Priya", "Lena", "Diego", "Noor", "Felix", "Hana"]


def build() -> tuple[list[dict], list[Trajectory]]:
    random = rng()
    logs: list[dict] = []
    trajectories: list[Trajectory] = []
    index = 0
    for queue in QUEUES:
        plans = list(PLANS)
        random.shuffle(plans)
        for (subject, cue, detail), plan in zip(TICKETS[queue], plans, strict=True):
            index += 1
            sentences = [cue, detail, random.choice(DISTRACTORS), random.choice(PLAN_MENTIONS[plan])]
            # The plan mention and the distractor move around so position carries no signal.
            tail = sentences[2:]
            random.shuffle(tail)
            body = " ".join([f"Hi {PRODUCT} team,", *sentences[:2], *tail, f"Thanks, {random.choice(NAMES)}"])
            ticket_id = f"TK-{4000 + index}"
            logs.append(
                {
                    "ticket_id": ticket_id,
                    "subject": subject,
                    "body": body,
                    "resolved_queue": queue,
                    "crm_plan": plan,
                }
            )
            trajectories.append(
                Trajectory(
                    trajectory_id=ticket_id,
                    system=POLICY,
                    turns=[
                        Turn(
                            input=f"Subject: {subject}\n\n{body}\n\nWhich queue? Reply with the queue name only.",
                            expected=Expected(label=queue),
                        ),
                        Turn(
                            input="Which plan is this customer on: free, pro, team, enterprise. One word.",
                            expected=Expected(label=plan),
                        ),
                    ],
                )
            )
    random.shuffle(trajectories)
    order = {t.trajectory_id: i for i, t in enumerate(trajectories)}
    logs.sort(key=lambda line: order[line["ticket_id"]])
    return logs, trajectories


if __name__ == "__main__":
    logs, trajectories = build()
    out = write_example("ticket-triage", logs, trajectories)
    print(f"wrote {len(trajectories)} trajectories to {out}")
