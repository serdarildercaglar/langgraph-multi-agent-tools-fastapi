"""Product agent — ürün arama, stok kontrolü, öneri.

Bağımsız agent. Hem main_agent hem order_agent tarafından tool olarak kullanılır.
"""

from langchain.agents import create_agent

from src.config.llm import llm
from src.config.settings import settings
from src.middleware.trim import trim_old_messages
from src.tools.product_tools import get_product_details, get_recommendations, search_products

_middleware = [trim_old_messages]
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import langfuse_prompt

    _middleware.insert(0, langfuse_prompt)

agent = create_agent(
    model=llm,
    tools=[search_products, get_product_details, get_recommendations],
    middleware=_middleware,
    system_prompt=(
        "You are a product specialist for an e-commerce store. "
        "Help customers find products, check availability, compare options, "
        "and get personalized recommendations. "
        "Always include price and stock info in your responses."
    ),
    name="product_agent",
)
