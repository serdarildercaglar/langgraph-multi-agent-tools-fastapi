"""Product tools — ürün arama, detay, öneri."""

from langchain.tools import tool


@tool
def search_products(query: str) -> str:
    """Search the product catalog by keyword.

    Args:
        query: Search keywords, e.g. 'wireless headphones', 'laptop under 1000'.
    """
    # TODO: gerçek ürün veritabanı / Elasticsearch bağlantısı
    return (
        f"Results for '{query}':\n"
        "1. Sony WH-1000XM5 — $299 — In stock\n"
        "2. Apple AirPods Pro 2 — $249 — In stock\n"
        "3. Bose QuietComfort Ultra — $329 — Low stock"
    )


@tool
def get_product_details(product_id: str) -> str:
    """Get detailed specs and availability for a specific product.

    Args:
        product_id: Product ID or SKU, e.g. 'SKU-12345'.
    """
    # TODO: gerçek ürün API'si
    return (
        f"Product {product_id}:\n"
        "Name: Sony WH-1000XM5\n"
        "Price: $299\n"
        "Stock: 42 units\n"
        "Rating: 4.7/5\n"
        "Features: ANC, 30h battery, multipoint bluetooth"
    )


@tool
def get_recommendations(category: str, budget: str = "") -> str:
    """Get product recommendations for a category and optional budget.

    Args:
        category: Product category, e.g. 'headphones', 'laptops'.
        budget: Optional budget range, e.g. 'under 300', '500-1000'.
    """
    # TODO: gerçek öneri motoru
    budget_info = f" (budget: {budget})" if budget else ""
    return (
        f"Top picks for {category}{budget_info}:\n"
        "1. Best overall: Sony WH-1000XM5 — $299\n"
        "2. Best value: Samsung Galaxy Buds3 — $179\n"
        "3. Premium: Apple AirPods Max — $549"
    )
