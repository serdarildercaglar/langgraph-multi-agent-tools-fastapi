"""Billing tools — fatura sorgulama, odeme gecmisi, taksitlendirme."""

from langchain.tools import tool


@tool
def get_invoice(msisdn: str, period: str = "") -> str:
    """Get the invoice for a specific billing period.

    Args:
        msisdn: Customer phone number, e.g. '05321234567'.
        period: Billing period, e.g. '2026-02', 'last'. Defaults to current period.
    """
    # TODO: gercek fatura API'si
    period_info = period if period else "2026-02 (current)"
    return (
        f"Invoice for {msisdn} — Period: {period_info}\n"
        "Plan charge: 449.00 TL\n"
        "Data overage (3.2 GB): 64.00 TL\n"
        "International calls: 28.50 TL\n"
        "Extra package (10 GB): 79.00 TL\n"
        "Tax (VAT 20%): 124.10 TL\n"
        "─────────────────────────\n"
        "Total: 744.60 TL\n"
        "Due date: 2026-03-15\n"
        "Status: Unpaid"
    )


@tool
def get_payment_history(msisdn: str) -> str:
    """Get the payment history for a customer.

    Args:
        msisdn: Customer phone number.
    """
    # TODO: gercek odeme gecmisi API'si
    return (
        f"Payment history for {msisdn}:\n"
        "2026-02-14 — 512.30 TL — Paid (Credit card)\n"
        "2026-01-16 — 449.00 TL — Paid (Credit card)\n"
        "2025-12-15 — 449.00 TL — Paid (Auto-pay)\n"
        "2025-11-17 — 527.80 TL — Paid (Credit card)\n"
        "2025-10-14 — 449.00 TL — Paid (Auto-pay)"
    )


@tool
def explain_charges(msisdn: str, period: str = "") -> str:
    """Explain invoice charges in detail (overages, extra services, etc.).

    Args:
        msisdn: Customer phone number.
        period: Billing period to explain, e.g. '2026-02'.
    """
    # TODO: gercek fatura detay API'si
    period_info = period if period else "2026-02 (current)"
    return (
        f"Charge breakdown for {msisdn} — {period_info}:\n\n"
        "1. Plan charge (Platinum 50 GB): 449.00 TL — Monthly subscription fee\n"
        "2. Data overage: 64.00 TL — You used 53.2 GB (3.2 GB over your 50 GB limit, 20 TL/GB)\n"
        "3. International calls: 28.50 TL — 12 min to Germany (2.00 TL/min) + 3 min to UK (1.50 TL/min)\n"
        "4. Extra package: 79.00 TL — 10 GB extra data package added on Feb 10\n"
        "5. Tax: 124.10 TL — 20% VAT on total charges\n\n"
        "Tip: Your data overage suggests upgrading to Diamond 100 GB could save you money."
    )


@tool
def initiate_payment_plan(msisdn: str, amount: str) -> str:
    """Start an installment payment plan for outstanding balance.

    Args:
        msisdn: Customer phone number.
        amount: Outstanding amount to split, e.g. '744.60'.
    """
    # TODO: gercek taksitlendirme API'si
    return (
        f"Payment plan created for {msisdn}:\n"
        f"Total amount: {amount} TL\n"
        "Installments: 3 months\n"
        "Monthly payment: {:.2f} TL\n".format(float(amount) / 3) +
        "First payment: 2026-03-15\n"
        "Plan ID: PAY-2026-33091\n"
        "Note: No interest applied for 3-month plans."
    )
