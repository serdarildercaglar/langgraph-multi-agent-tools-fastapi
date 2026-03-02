"""Main agent — müşteri destek supervisor'ı.

Kullanıcıyla konuşur. Ürün sorusu → product_agent, sipariş sorusu → order_agent.
Basit sorulara (selamlama, genel bilgi) doğrudan cevap verir.
"""

import uuid

from langchain.agents import create_agent
from langchain.tools import tool

from src.agents.order_agent import agent as order_agent
from src.agents.product_agent import agent as product_agent
from src.config.llm import llm
from src.config.settings import settings
from src.middleware.trim import trim_old_messages


# --- Sub-agent'ları tool olarak tanımla ----------------------------------


@tool
async def ask_product_specialist(question: str) -> str:
    """Delegate product-related questions to the product specialist.
    Use for: product search, availability, specs, comparisons, recommendations.

    Args:
        question: The product-related question from the customer.
    """
    result = await product_agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
    )
    return result["messages"][-1].content


@tool
async def ask_order_specialist(question: str) -> str:
    """Delegate order-related questions to the order specialist.
    Use for: order tracking, returns, refunds, exchanges.

    Args:
        question: The order-related question from the customer.
    """
    result = await order_agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
    )
    return result["messages"][-1].content


# --- Supervisor -----------------------------------------------------------

_middleware = [trim_old_messages]
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import langfuse_prompt

    _middleware.insert(0, langfuse_prompt)

agent = create_agent(
    model=llm,
    tools=[ask_product_specialist, ask_order_specialist],
    middleware=_middleware,
    system_prompt=(
        "You are a customer support manager for an e-commerce store.\n\n"
        "Route customer questions to the right specialist:\n"
        "- Product questions (search, specs, recommendations) → ask_product_specialist\n"
        "- Order questions (tracking, returns, exchanges) → ask_order_specialist\n"
        "- Greetings and general questions → answer directly\n\n"
        "Be friendly, concise, and always synthesize specialist responses "
        "into a clear answer for the customer."
    ),
    name="main_agent",
)
