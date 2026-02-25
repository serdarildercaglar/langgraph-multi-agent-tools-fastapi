"""Order tools — sipariş takip, iade, değişim."""

from langchain.tools import tool


@tool
def track_order(order_id: str) -> str:
    """Track the current status and location of an order.

    Args:
        order_id: Order number, e.g. 'ORD-78432'.
    """
    # TODO: gerçek sipariş takip API'si
    return (
        f"Order {order_id}:\n"
        "Status: In transit\n"
        "Carrier: FedEx — Tracking: FX928374651\n"
        "Shipped: Feb 23, 2026\n"
        "Estimated delivery: Feb 27, 2026\n"
        "Items: Sony WH-1000XM5 (x1)"
    )


@tool
def initiate_return(order_id: str, reason: str) -> str:
    """Start a return/refund process for an order.

    Args:
        order_id: Order number to return.
        reason: Reason for return, e.g. 'defective', 'wrong size', 'changed mind'.
    """
    # TODO: gerçek iade API'si
    return (
        f"Return initiated for {order_id}:\n"
        f"Reason: {reason}\n"
        "Return label: RET-2026-55891\n"
        "Refund will be processed within 3-5 business days after receiving the item.\n"
        "Please ship within 14 days."
    )


@tool
def initiate_exchange(order_id: str, reason: str) -> str:
    """Start an exchange process for an order.

    Args:
        order_id: Order number to exchange.
        reason: Reason for exchange, e.g. 'wrong color', 'want upgrade'.
    """
    # TODO: gerçek değişim API'si
    return (
        f"Exchange initiated for {order_id}:\n"
        f"Reason: {reason}\n"
        "Exchange ID: EXC-2026-44210\n"
        "Please use the find_alternative tool to help the customer pick a replacement."
    )
