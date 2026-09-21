"""Build the contract-extract example: a long document, a short exact answer.

What this produces, under examples/contract-extract/:

- logs.jsonl: 20 signed services agreements as a procurement tool would store
  them, each with the fields a paralegal keyed in afterwards (fee, notice
  period, governing law, renewal term, retention clause, liability cap). The
  "before /eval-build" state.
- trajectories.jsonl: each agreement as a three-turn conversation. The whole
  contract is the system prompt; each turn asks for one keyed field and
  expects it on the first line of the answer.

Why this shape. Prefill dominates. A ~5K-token document and a ten-token answer
means the model spends its time reading, not writing, and TTFT is the whole
wait. This is where providers differ most (prefill throughput is a hardware
and batching story) and where small models start missing the needle among
the distractors. The verdict should turn on TTFT p95 and price per million
input tokens, not on decode speed.

Ground truth. Every agreement is assembled from the same clause templates
with six planted facts drawn per agreement, plus a dozen distractor numbers,
dates, and amounts in other clauses (a setup fee next to the annual fee, a
cure period next to the notice period, an insurance minimum next to the
liability cap). The answer is anchored to the first line of the reply, so a
model that lists every number in the contract does not pass by accident.

Run:  uv run python scripts/examples/contract_extract.py
"""

from __future__ import annotations

import re

from _common import rng, write_example

from harness.models import Expected, Trajectory, Turn

CUSTOMERS = [
    ("Halden Logistics GmbH", "Hamburg, Germany"),
    ("Pinecrest Health Systems, Inc.", "Denver, Colorado"),
    ("Orbital Media Ltd", "Manchester, United Kingdom"),
    ("Kestrel Financial Services LLC", "Charlotte, North Carolina"),
    ("Sable & Finch Architects", "Melbourne, Australia"),
    ("Nordvik Energy AS", "Stavanger, Norway"),
    ("Cobalt Ridge Mining Corp.", "Sudbury, Ontario"),
    ("Tamarind Hospitality Group", "Singapore"),
    ("Westmere Public Schools", "Albany, New York"),
    ("Lumen & Vale Publishing", "Dublin, Ireland"),
    ("Redwater Marine Insurance plc", "Southampton, United Kingdom"),
    ("Aster Biotech SA", "Lausanne, Switzerland"),
    ("Greyline Freight Co.", "Memphis, Tennessee"),
    ("Quillon Software Oy", "Helsinki, Finland"),
    ("Marrow Street Bakeries", "Portland, Oregon"),
    ("Ironhold Security Services", "Phoenix, Arizona"),
    ("Bluefern Cosmetics BV", "Rotterdam, Netherlands"),
    ("Cairnwood Estates Ltd", "Edinburgh, United Kingdom"),
    ("Vireo Analytics Pte Ltd", "Singapore"),
    ("Saltmarsh Brewing Company", "Austin, Texas"),
]

GOVERNING_LAW = ["Delaware", "New York", "California", "England and Wales", "Ireland", "Singapore"]
ANNUAL_FEES = [24000, 36500, 48500, 62000, 78000, 91500, 115000, 132500, 148000, 176000]
NOTICE_DAYS = [30, 45, 60, 90, 120, 180]
RENEWAL_MONTHS = [6, 12, 24, 36]
LIABILITY_CAPS = [100000, 150000, 250000, 400000, 500000, 750000, 1000000]

VENDOR = "Meridian Cloud Services, Inc."


def money(amount: int) -> str:
    return f"USD {amount:,}"


def agreement(random, customer: tuple[str, str], facts: dict) -> str:
    """Render one agreement. Section numbers are fixed except that the data
    protection section (and so the retention clause) moves, which is what
    makes the clause-number question a reading task rather than a memory."""
    name, city = customer
    setup_fee = random.choice([2500, 4000, 7500, 12000])
    seat_fee = random.choice([18, 24, 32, 45])
    cure_days = random.choice([d for d in [10, 14, 15, 20, 30] if d != facts["notice_days"]])
    audit_days = random.choice([d for d in [10, 15, 20, 30] if d not in (cure_days, facts["notice_days"])])
    insurance = random.choice([c for c in [1000000, 2000000, 5000000] if c != facts["liability_cap"]])
    uptime = random.choice(["99.5%", "99.9%", "99.95%"])
    credit = random.choice(["5%", "10%", "15%"])
    interest = random.choice(["1.0%", "1.5%", "2.0%"])
    initial_months = random.choice([m for m in [12, 24, 36] if m != facts["renewal_months"]])
    effective = f"{random.choice(['January', 'March', 'April', 'June', 'September', 'November'])} {random.randint(1, 28)}, {random.choice([2025, 2026])}"
    retention_years = random.choice([3, 5, 7])
    retention_days = random.choice([30, 60, 90])

    sections: list[tuple[str, list[str]]] = []
    sections.append(("DEFINITIONS AND INTERPRETATION", [
        f'"Agreement" means this Master Services Agreement together with each Order Form and Schedule executed under it. "Effective Date" means {effective}. "Customer" means {name}, a company having its principal place of business in {city}. "Provider" means {VENDOR}. Capitalised terms not defined in the body of this Agreement have the meanings given in Schedule A.',
        '"Services" means the hosted analytics platform, the associated application programming interfaces, the documentation, and any professional services described in an Order Form. "Customer Data" means all data, content, and materials submitted by or on behalf of Customer to the Services, including data derived from it that identifies Customer or its Users. "Users" means the employees, contractors, and agents of Customer who are authorised by Customer to use the Services.',
        "Headings are for convenience only and do not affect interpretation. Words in the singular include the plural and vice versa. References to a statute include that statute as amended, re-enacted, or replaced from time to time. Where this Agreement and an Order Form conflict, the Order Form prevails for the Services it describes and this Agreement prevails in every other respect.",
    ]))
    sections.append(("PROVISION OF THE SERVICES", [
        "Provider shall make the Services available to Customer in accordance with this Agreement, the applicable Order Form, and the Documentation. Provider shall provide the Services in a professional and workmanlike manner consistent with generally accepted industry standards, using personnel with appropriate skill and experience.",
        "Provider may modify the Services from time to time provided that no modification materially reduces the functionality of the Services purchased by Customer during the then-current Subscription Term. Provider shall give Customer at least twenty (20) days' notice of any modification that changes the manner in which Customer Data is processed.",
        "Provider shall provide the support services described in Schedule B. Support requests are classified by severity on receipt, and the response targets in Schedule B apply from the time a request is acknowledged. Support is provided in English during Provider's business hours, with severity one incidents handled around the clock.",
    ]))
    sections.append(("CUSTOMER OBLIGATIONS", [
        "Customer is responsible for all activities that occur under its Users' accounts and shall ensure that Users comply with the terms of this Agreement. Customer shall use commercially reasonable efforts to prevent unauthorised access to or use of the Services and shall notify Provider promptly of any such unauthorised access or use.",
        "Customer shall not, and shall not permit any third party to, sell, resell, license, sublicense, distribute, or otherwise make the Services available to anyone other than Users; use the Services to store or transmit infringing, libellous, or otherwise unlawful material; interfere with or disrupt the integrity or performance of the Services; or attempt to gain unauthorised access to the Services or their related systems or networks.",
        "Customer shall obtain and maintain all licences, consents, and permissions necessary for Provider to process Customer Data in accordance with this Agreement. Customer represents that it has the right to submit Customer Data to the Services and that doing so does not violate any applicable law or the rights of any third party.",
    ]))
    sections.append(("FEES AND PAYMENT", [
        f"In consideration of the Services, Customer shall pay Provider an annual subscription fee of {money(facts['annual_fee'])} (the \"Annual Fee\"), invoiced annually in advance on the Effective Date and on each anniversary of it. Additional Users beyond the number stated in the Order Form are charged at {money(seat_fee)} per User per month, invoiced quarterly in arrears.",
        f"A one-time implementation fee of {money(setup_fee)} is payable on the Effective Date and is non-refundable. Professional services not covered by the implementation fee are charged at the daily rates set out in the Order Form and invoiced monthly in arrears against approved timesheets.",
        f"All invoices are payable within thirty (30) days of the invoice date. Overdue amounts accrue interest at {interest} per month or the maximum rate permitted by law, whichever is lower. Fees are exclusive of all taxes, levies, and duties, which Customer shall pay in addition unless Customer provides a valid exemption certificate.",
        "Provider may increase the Annual Fee for any Renewal Term by giving Customer written notice at least sixty (60) days before the start of that Renewal Term, provided that no single increase exceeds seven percent (7%) of the Annual Fee for the preceding Subscription Term.",
    ]))
    sections.append(("TERM AND TERMINATION", [
        f"This Agreement commences on the Effective Date and continues for an initial term of {initial_months} months (the \"Initial Term\"). Upon expiry of the Initial Term, this Agreement renews automatically for successive renewal terms of {facts['renewal_months']} months each (each a \"Renewal Term\") unless either party gives notice of non-renewal in accordance with this Section.",
        f"Either party may terminate this Agreement for convenience, effective at the end of the then-current Subscription Term, by giving the other party at least {facts['notice_days']} days' written notice before the end of that Subscription Term. Notice of non-renewal given later than that is effective at the end of the following Subscription Term.",
        f"Either party may terminate this Agreement immediately on written notice if the other party materially breaches this Agreement and, where the breach is capable of remedy, fails to remedy it within {cure_days} days after receiving written notice describing the breach in reasonable detail. Either party may also terminate immediately if the other party becomes insolvent, makes an assignment for the benefit of creditors, or has a receiver appointed over any of its assets.",
        f"On termination or expiry, Customer's right to use the Services ceases, all unpaid fees for the remainder of the Subscription Term become due where Customer terminated for convenience, and Provider shall make Customer Data available for export for {retention_days} days as described in the Data Protection section, after which Provider may delete it.",
    ]))
    data_protection = ("DATA PROTECTION AND SECURITY", [
        "Each party shall comply with the data protection laws applicable to it in connection with this Agreement. Where Provider processes personal data on behalf of Customer, the Data Processing Addendum in Schedule C applies and forms part of this Agreement. Provider shall process Customer Data only on Customer's documented instructions and only to the extent necessary to provide the Services.",
        "Provider shall maintain an information security programme that includes administrative, physical, and technical safeguards appropriate to the nature of Customer Data, including encryption of Customer Data in transit and at rest, role-based access controls, logging of administrative access, and annual independent testing of the Services. Provider shall notify Customer without undue delay, and in any event within seventy-two (72) hours, after becoming aware of a security incident affecting Customer Data.",
        f"Retention. Provider shall retain Customer Data for the duration of the Subscription Term and for {retention_days} days after termination or expiry to permit export, after which Provider shall delete or de-identify Customer Data within a further thirty (30) days, except that Provider may retain Customer Data in routine backups for up to {retention_years} years where deletion is not technically practicable, provided such backups remain subject to the security obligations in this Section and are not restored except as required by law.",
    ])
    sections.append(("CONFIDENTIALITY", [
        "Each party (the \"Recipient\") shall keep confidential all information disclosed by the other party (the \"Discloser\") that is marked as confidential or that a reasonable person would understand to be confidential, shall use it only for the purposes of this Agreement, and shall disclose it only to those of its employees, contractors, and advisers who need to know it and are bound by obligations no less protective than these.",
        "Confidential information does not include information that is or becomes publicly available through no fault of the Recipient, was known to the Recipient without restriction before disclosure, is independently developed by the Recipient without use of the Discloser's information, or is rightfully received from a third party without restriction. The Recipient may disclose confidential information to the extent required by law, provided it gives the Discloser prompt notice and reasonable assistance in seeking protective treatment.",
        "The obligations in this Section survive for five (5) years after termination or expiry of this Agreement, except that obligations relating to trade secrets survive for as long as the information remains a trade secret under applicable law.",
    ]))
    sections.append(("INTELLECTUAL PROPERTY", [
        "As between the parties, Provider owns all right, title, and interest in and to the Services, the Documentation, and all improvements, modifications, and derivative works of them, including any suggestions, enhancement requests, or feedback provided by Customer. No rights are granted to Customer except as expressly set out in this Agreement.",
        "As between the parties, Customer owns all right, title, and interest in and to Customer Data. Customer grants Provider a non-exclusive, worldwide, royalty-free licence to host, copy, transmit, display, and process Customer Data solely as necessary to provide the Services and as otherwise permitted by this Agreement.",
        "Provider may compile aggregated and de-identified statistics about the use and performance of the Services, provided that such statistics do not identify Customer or any User and cannot reasonably be used to do so. Provider owns such statistics and may use them for any lawful purpose during and after the term of this Agreement.",
    ]))
    sections.append(("WARRANTIES AND DISCLAIMERS", [
        f"Provider warrants that the Services will perform materially in accordance with the Documentation and that Provider will not materially decrease the overall security of the Services during a Subscription Term. Provider further warrants that the Services will achieve the monthly uptime commitment of {uptime} set out in Schedule B, and Customer's sole remedy for a failure to do so is the service credit of {credit} of the monthly portion of the Annual Fee described there.",
        "Each party warrants that it has the authority to enter into this Agreement and that doing so does not conflict with any other agreement to which it is a party. Customer warrants that it will not use the Services in any manner that violates applicable law.",
        "EXCEPT AS EXPRESSLY PROVIDED IN THIS AGREEMENT, EACH PARTY DISCLAIMS ALL WARRANTIES, WHETHER EXPRESS, IMPLIED, STATUTORY, OR OTHERWISE, INCLUDING ANY WARRANTY OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT, TO THE MAXIMUM EXTENT PERMITTED BY LAW.",
    ]))
    sections.append(("INDEMNIFICATION", [
        "Provider shall defend Customer against any claim by a third party alleging that the Services, as provided by Provider and used in accordance with this Agreement, infringe that third party's intellectual property rights, and shall pay any damages finally awarded or agreed in settlement. If the Services become, or in Provider's opinion are likely to become, the subject of such a claim, Provider may procure the right for Customer to continue using them, modify them so they are non-infringing, or terminate the affected Services and refund any prepaid fees for the unexpired portion of the Subscription Term.",
        "Customer shall defend Provider against any claim by a third party arising from Customer Data or from Customer's use of the Services in breach of this Agreement, and shall pay any damages finally awarded or agreed in settlement.",
        f"The indemnified party shall give the indemnifying party prompt written notice of the claim, sole control of the defence and settlement, and reasonable cooperation at the indemnifying party's expense. Each party shall maintain commercial general liability and professional liability insurance with limits of not less than {money(insurance)} per occurrence for the term of this Agreement and shall provide certificates of insurance on request.",
    ]))
    sections.append(("LIMITATION OF LIABILITY", [
        f"EXCEPT FOR A PARTY'S INDEMNIFICATION OBLIGATIONS, ITS BREACH OF THE CONFIDENTIALITY SECTION, OR ITS GROSS NEGLIGENCE OR WILFUL MISCONDUCT, IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT EXCEED {money(facts['liability_cap'])}. THE FOREGOING LIMITATION APPLIES WHETHER AN ACTION IS IN CONTRACT OR TORT AND REGARDLESS OF THE THEORY OF LIABILITY.",
        "IN NO EVENT SHALL EITHER PARTY HAVE ANY LIABILITY TO THE OTHER PARTY FOR ANY LOST PROFITS, LOSS OF BUSINESS, LOSS OF DATA, OR FOR ANY INDIRECT, SPECIAL, INCIDENTAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES HOWEVER CAUSED, EVEN IF A PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.",
        "The parties agree that the limitations in this Section are an essential basis of the bargain between them and that, absent these limitations, the fees and other terms of this Agreement would be substantially different.",
    ]))
    sections.append(("AUDIT AND COMPLIANCE", [
        f"Not more than once in any twelve-month period, and on at least {audit_days} days' written notice, Customer may audit Provider's compliance with the Data Protection section, either directly or through an independent auditor bound by confidentiality obligations. Audits are conducted during business hours, may not unreasonably interfere with Provider's operations, and are at Customer's expense unless they reveal a material breach.",
        "Provider shall make available, on request and not more than once per year, its most recent third-party audit report covering the Services, together with a summary of any material findings and the remediation status of each.",
        "Each party shall comply with all applicable anti-corruption, export control, and sanctions laws in connection with this Agreement and shall not cause the other party to be in breach of them.",
    ]))
    sections.append(("GOVERNING LAW AND DISPUTES", [
        f"This Agreement and any dispute or claim arising out of or in connection with it are governed by the laws of {facts['governing_law']}, without regard to its conflict of laws principles. The United Nations Convention on Contracts for the International Sale of Goods does not apply.",
        "The parties shall attempt in good faith to resolve any dispute through negotiation between senior executives before commencing proceedings. If the dispute is not resolved within thirty (30) days after one party notifies the other of it, either party may commence proceedings in the courts having jurisdiction under the governing law stated above, and each party submits to the exclusive jurisdiction of those courts.",
        "Nothing in this Section prevents either party from seeking injunctive or other equitable relief in any court of competent jurisdiction to protect its intellectual property or confidential information.",
    ]))
    sections.append(("GENERAL", [
        "Neither party may assign this Agreement without the other party's prior written consent, not to be unreasonably withheld, except that either party may assign it in its entirety to an affiliate or to a successor in connection with a merger, acquisition, or sale of all or substantially all of its assets, on written notice to the other party.",
        "Notices under this Agreement must be in writing and delivered by hand, by courier, or by email with confirmation of receipt to the addresses stated in the Order Form. Notices are effective on receipt.",
        "Neither party is liable for any failure or delay in performance caused by events beyond its reasonable control, including natural disasters, acts of government, labour disputes, and failures of third-party networks, provided it uses reasonable efforts to mitigate the effect. This Agreement, together with its Schedules and Order Forms, is the entire agreement between the parties on its subject matter and supersedes all prior agreements and understandings. It may be amended only in writing signed by both parties.",
    ]))

    # Move data protection to a varying position so its clause number is a reading task.
    position = random.randint(4, 9)
    sections.insert(position, data_protection)
    facts["retention_clause"] = f"{position + 1}.3"

    lines = [
        "MASTER SERVICES AGREEMENT",
        "",
        f"This Master Services Agreement is entered into as of {effective} between {VENDOR} (\"Provider\") and {name} (\"Customer\").",
        "",
    ]
    for number, (title, clauses) in enumerate(sections, start=1):
        lines.append(f"{number}. {title}")
        for sub, clause in enumerate(clauses, start=1):
            lines.append(f"{number}.{sub} {clause}")
        lines.append("")
    lines += [
        "SCHEDULE A: SERVICE DESCRIPTION",
        "A.1 The Services comprise the Meridian analytics platform (workspace, dashboards, scheduled reports), the Meridian API (REST and streaming endpoints, rate-limited at 600 requests per minute per workspace), and the connector library for third-party data sources listed in the Documentation.",
        "A.2 The Order Form states the number of Users, the data volume tier (Standard up to 2 TB, Extended up to 10 TB, Unlimited), and the region in which Customer Data is hosted. Changes to any of these take effect on the next invoice date.",
        "A.3 Professional services are described in a statement of work. Unless the statement of work says otherwise, professional services are provided remotely, on business days, and any travel is charged at cost with Customer's prior approval.",
        "",
        "SCHEDULE B: SUPPORT AND SERVICE LEVELS",
        f"B.1 Monthly Uptime Commitment: {uptime}, measured per calendar month and excluding scheduled maintenance (not more than eight (8) hours per month, notified at least forty-eight (48) hours in advance) and events outside Provider's reasonable control.",
        f"B.2 Service Credit: if the Monthly Uptime Commitment is not met, Customer is entitled to a credit of {credit} of the monthly portion of the Annual Fee for that month, applied against the next invoice. Credits must be claimed within thirty (30) days of the end of the month in which the failure occurred and are Customer's sole remedy for a failure to meet the commitment.",
        "B.3 Support severities and response targets: Severity 1 (Services unavailable for all Users): response within one (1) hour, updates every four (4) hours. Severity 2 (major function unavailable, no workaround): response within four (4) hours. Severity 3 (minor function affected, workaround available): response within one (1) business day. Severity 4 (question or request): response within three (3) business days.",
        "",
        "IN WITNESS WHEREOF, the parties have executed this Agreement by their duly authorised representatives as of the Effective Date.",
    ]
    return "\n".join(lines)


QUESTIONS = {
    "annual_fee": (
        "What is the annual subscription fee in USD? Reply with the number only, no currency symbol.",
        lambda v: rf"^\s*[^\n]*\b{v // 1000},?{v % 1000:03d}\b",
    ),
    "notice_days": (
        "How many days' written notice are required to terminate this Agreement for convenience? Number only.",
        lambda v: rf"^\s*[^\n]*\b{v}\b",
    ),
    "governing_law": (
        "Which law governs this Agreement? Reply with the jurisdiction name only.",
        lambda v: rf"^\s*[^\n]*\b{v}\b",
    ),
    "renewal_months": (
        "How many months long is each Renewal Term? Number only.",
        lambda v: rf"^\s*[^\n]*\b{v}\b",
    ),
    "retention_clause": (
        "Which clause number sets out the retention period for Customer Data? Reply with the clause number only, in the form 7.2.",
        lambda v: r"^\s*[^\n]*\b" + re.escape(v) + r"\b",
    ),
    "liability_cap": (
        "What is the cap on either party's aggregate liability in USD? Reply with the number only, no currency symbol.",
        lambda v: rf"^\s*[^\n]*\b{v // 1000},?{v % 1000:03d}\b",
    ),
}

SYSTEM_PREFIX = (
    "You answer questions about the signed agreement below for a procurement analyst. "
    "Answer from the document only. Put the answer alone on the first line, with nothing before it; "
    "you may add one sentence of explanation on a second line.\n\n"
)


def build() -> tuple[list[dict], list[Trajectory]]:
    random = rng()
    logs: list[dict] = []
    trajectories: list[Trajectory] = []
    keys = list(QUESTIONS)
    for i, customer in enumerate(CUSTOMERS):
        facts = {
            "annual_fee": random.choice(ANNUAL_FEES),
            "notice_days": random.choice(NOTICE_DAYS),
            "governing_law": random.choice(GOVERNING_LAW),
            "renewal_months": random.choice(RENEWAL_MONTHS),
            "liability_cap": random.choice(LIABILITY_CAPS),
        }
        text = agreement(random, customer, facts)  # sets facts["retention_clause"]
        asked = [keys[(i + k) % len(keys)] for k in (0, 2, 4)]
        random.shuffle(asked)
        contract_id = f"MSA-{2600 + i}"
        logs.append({"contract_id": contract_id, "customer": customer[0], "text": text, "keyed_fields": facts})
        trajectories.append(
            Trajectory(
                trajectory_id=contract_id,
                system=SYSTEM_PREFIX + text,
                turns=[
                    Turn(input=QUESTIONS[key][0], expected=Expected(pattern=QUESTIONS[key][1](facts[key])))
                    for key in asked
                ],
            )
        )
    return logs, trajectories


if __name__ == "__main__":
    logs, trajectories = build()
    out = write_example("contract-extract", logs, trajectories)
    sizes = sorted(len(t.system) for t in trajectories)
    print(f"wrote {len(trajectories)} trajectories to {out}; document chars p50 {sizes[len(sizes) // 2]}")
