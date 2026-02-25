"""Order agent — sipariş takibi, iade, değişim.

İade veya değişim senaryosunda product_agent'ı tool olarak çağırarak
müşteriye alternatif ürün önerir (agent-as-tool pattern).
"""

from langchain.agents import create_agent
from langchain.tools import tool

from src.agents.product_agent import agent as product_agent
from src.config.llm import llm
from src.memory.checkpointer import get_checkpointer
from src.tools.order_tools import initiate_exchange, initiate_return, track_order


# --- product_agent'ı tool olarak kullan (agent-as-tool) ------------------


@tool
def find_alternative(category: str, budget: str = "") -> str:
    """Find alternative products for a return/exchange scenario.
    Delegates to the product specialist agent.

    Args:
        category: Product category to search alternatives in.
        budget: Optional budget constraint.
    """
    result = product_agent.invoke(
        {"messages": [{"role": "user", "content": f"Recommend {category} products{' ' + budget if budget else ''}. Customer is exchanging, show top 3 options with prices."}]}
    )
    return result["messages"][-1].content


# --- Agent ----------------------------------------------------------------

agent = create_agent(
    model=llm,
    tools=[track_order, initiate_return, initiate_exchange, find_alternative],
    system_prompt=(
        "You are an order specialist for an e-commerce store. "
        "Help customers track orders, process returns, and handle exchanges.\n\n"
        "When a customer wants to exchange a product, ALWAYS use find_alternative "
        "to suggest replacement options before finalizing the exchange."
    ),
    name="order_agent",
    checkpointer=get_checkpointer(),
)
