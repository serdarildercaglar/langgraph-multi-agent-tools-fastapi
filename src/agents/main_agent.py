"""Main agent — müşteri destek supervisor'ı.

Kullanıcıyla konuşur. Ürün sorusu → product_agent, sipariş sorusu → order_agent.
Basit sorulara (selamlama, genel bilgi) doğrudan cevap verir.
"""

from langchain.agents import create_agent
from langchain.tools import tool

from src.agents.order_agent import agent as order_agent
from src.agents.product_agent import agent as product_agent
from src.config.llm import llm
from src.memory.checkpointer import get_checkpointer


# --- Sub-agent'ları tool olarak tanımla ----------------------------------


@tool
def ask_product_specialist(question: str) -> str:
    """Delegate product-related questions to the product specialist.
    Use for: product search, availability, specs, comparisons, recommendations.

    Args:
        question: The product-related question from the customer.
    """
    result = product_agent.invoke(
        {"messages": [{"role": "user", "content": question}]}
    )
    return result["messages"][-1].content


@tool
def ask_order_specialist(question: str) -> str:
    """Delegate order-related questions to the order specialist.
    Use for: order tracking, returns, refunds, exchanges.

    Args:
        question: The order-related question from the customer.
    """
    result = order_agent.invoke(
        {"messages": [{"role": "user", "content": question}]}
    )
    return result["messages"][-1].content


# --- Supervisor -----------------------------------------------------------

agent = create_agent(
    model=llm,
    tools=[ask_product_specialist, ask_order_specialist],
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
    checkpointer=get_checkpointer(),
)
