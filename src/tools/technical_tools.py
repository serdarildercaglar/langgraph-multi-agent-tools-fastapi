"""Technical support tools — network, diagnostics, trouble tickets."""

from langchain.tools import tool


@tool
def check_network_status(location: str) -> str:
    """Check network/coverage status for a specific area.

    Args:
        location: City, district or address, e.g. 'Istanbul Kadikoy', 'Ankara Cankaya'.
    """
    # TODO: gercek network monitoring API'si
    return (
        f"Network status for {location}:\n"
        "4G/LTE: Operational (signal strength: excellent)\n"
        "5G: Operational (limited coverage in this area)\n"
        "3G: Operational\n"
        "Known issues: None\n"
        "Last incident: 2026-02-28 — Resolved (fiber cut, 2h downtime)"
    )


@tool
def run_line_diagnostic(msisdn: str) -> str:
    """Run a diagnostic check on the customer's line.

    Args:
        msisdn: Customer phone number, e.g. '05321234567'.
    """
    # TODO: gercek hat diagnostik API'si
    return (
        f"Line diagnostic for {msisdn}:\n"
        "SIM status: Active\n"
        "Signal strength: -75 dBm (good)\n"
        "Network type: 4G LTE\n"
        "Data session: Active\n"
        "VoLTE: Enabled\n"
        "Last cell tower: IST-KDK-0142 (Kadikoy)\n"
        "Packet loss: 0.2% (normal)\n"
        "Latency: 28ms (normal)"
    )


@tool
def check_device_compatibility(imei: str) -> str:
    """Check device compatibility with network features (5G, VoLTE, etc.).

    Args:
        imei: Device IMEI number, e.g. '356938035643809'.
    """
    # TODO: gercek IMEI/TAC veritabani
    return (
        f"Device check for IMEI {imei}:\n"
        "Device: Samsung Galaxy S24 Ultra\n"
        "4G/LTE: Compatible\n"
        "5G: Compatible (SA + NSA)\n"
        "VoLTE: Compatible\n"
        "WiFi Calling: Compatible\n"
        "eSIM: Supported\n"
        "Status: Not blacklisted"
    )


@tool
def create_trouble_ticket(msisdn: str, issue_type: str, description: str) -> str:
    """Create a trouble ticket for unresolved technical issues.

    Args:
        msisdn: Customer phone number.
        issue_type: Issue category, e.g. 'no-signal', 'slow-data', 'call-drops', 'sms-failure'.
        description: Detailed description of the problem from the customer.
    """
    # TODO: gercek trouble ticket sistemi (Remedy, ServiceNow vb.)
    return (
        f"Trouble ticket created:\n"
        f"MSISDN: {msisdn}\n"
        f"Issue type: {issue_type}\n"
        f"Description: {description}\n"
        "Ticket ID: TT-2026-0315-4821\n"
        "Priority: Medium\n"
        "SLA: 24 hours\n"
        "A technician will investigate and you will receive an SMS update."
    )
