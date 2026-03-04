"""Subscription tools — tarife sorgulama, degistirme, paket ekleme."""

from langchain.tools import tool


@tool
def get_current_plan(msisdn: str) -> str:
    """Get the customer's current subscription plan details.

    Args:
        msisdn: Customer phone number, e.g. '05321234567'.
    """
    # TODO: gercek CRM / BSS API baglantisi
    return (
        f"Current plan for {msisdn}:\n"
        "Plan: Platinum 50 GB\n"
        "Data: 50 GB (32 GB used)\n"
        "Voice: Unlimited domestic calls\n"
        "SMS: 1000 SMS\n"
        "Price: 449 TL/month\n"
        "Contract end: 2026-09-15"
    )


@tool
def search_plans(usage_type: str, budget: str = "") -> str:
    """Search available plans by usage type and optional budget.

    Args:
        usage_type: Usage profile, e.g. 'high-data', 'balanced', 'voice-heavy', 'budget'.
        budget: Optional max monthly price, e.g. 'under 300', '200-400'.
    """
    # TODO: gercek tarife katalogu API'si
    budget_info = f" (budget: {budget})" if budget else ""
    return (
        f"Available plans for '{usage_type}'{budget_info}:\n"
        "1. Gold 25 GB — 25 GB data, unlimited calls, 500 SMS — 299 TL/month\n"
        "2. Platinum 50 GB — 50 GB data, unlimited calls, 1000 SMS — 449 TL/month\n"
        "3. Diamond 100 GB — 100 GB data, unlimited calls, unlimited SMS — 649 TL/month"
    )


@tool
def compare_plans(plan_ids: str) -> str:
    """Compare two or more plans side by side.

    Args:
        plan_ids: Comma-separated plan IDs to compare, e.g. 'gold-25,platinum-50'.
    """
    # TODO: gercek tarife karsilastirma API'si
    return (
        f"Comparison for plans [{plan_ids}]:\n"
        "                | Gold 25 GB    | Platinum 50 GB\n"
        "Data            | 25 GB         | 50 GB\n"
        "Voice           | Unlimited     | Unlimited\n"
        "SMS             | 500           | 1000\n"
        "Price           | 299 TL/month  | 449 TL/month\n"
        "5G Access       | No            | Yes\n"
        "Roaming Package | Extra charge  | Included (5 GB)"
    )


@tool
def change_plan(msisdn: str, plan_id: str) -> str:
    """Initiate a plan change for the customer.

    Args:
        msisdn: Customer phone number.
        plan_id: Target plan ID, e.g. 'diamond-100'.
    """
    # TODO: gercek tarife degisiklik API'si
    return (
        f"Plan change initiated for {msisdn}:\n"
        f"New plan: {plan_id}\n"
        "Effective: Next billing cycle (2026-04-01)\n"
        "Change ID: CHG-2026-78432\n"
        "Note: No cancellation fee applies."
    )


@tool
def add_package(msisdn: str, package_type: str) -> str:
    """Add an extra package to the customer's line.

    Args:
        msisdn: Customer phone number.
        package_type: Package type, e.g. 'extra-data-10gb', 'international-calls', 'roaming-eu'.
    """
    # TODO: gercek paket ekleme API'si
    return (
        f"Package added for {msisdn}:\n"
        f"Package: {package_type}\n"
        "Price: 79 TL (one-time)\n"
        "Valid: 30 days from activation\n"
        "Activation ID: PKG-2026-91205"
    )
