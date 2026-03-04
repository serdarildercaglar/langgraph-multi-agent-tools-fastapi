"""Main agent — telco musteri destek supervisor'i.

Kullaniciyla konusur. Tarife sorusu → subscription_agent, fatura sorusu → billing_agent,
teknik sorun → technical_agent. Basit sorulara (selamlama, genel bilgi) dogrudan cevap verir.
"""

import uuid

from langchain.agents import create_agent
from langchain.tools import tool

from src.agents.billing_agent import agent as billing_agent
from src.agents.subscription_agent import agent as subscription_agent
from src.agents.technical_agent import agent as technical_agent
from src.config.llm import llm
from src.config.settings import settings
from src.middleware.trim import trim_old_messages


# --- Sub-agent'lari tool olarak tanimla ----------------------------------


@tool
async def ask_subscription_specialist(question: str) -> str:
    """Delegate subscription and plan questions to the subscription specialist.
    Use for: current plan info, plan search, comparison, plan changes, extra packages.

    Args:
        question: The subscription-related question from the customer.
    """
    result = await subscription_agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
    )
    return result["messages"][-1].content


@tool
async def ask_billing_specialist(question: str) -> str:
    """Delegate billing and payment questions to the billing specialist.
    Use for: invoices, charge explanations, payment history, installment plans.

    Args:
        question: The billing-related question from the customer.
    """
    result = await billing_agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
    )
    return result["messages"][-1].content


@tool
async def ask_technical_specialist(question: str) -> str:
    """Delegate technical issues to the technical support specialist.
    Use for: network problems, connectivity issues, device compatibility, trouble tickets.

    Args:
        question: The technical issue description from the customer.
    """
    result = await technical_agent.ainvoke(
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
    tools=[ask_subscription_specialist, ask_billing_specialist, ask_technical_specialist],
    middleware=_middleware,
    system_prompt=(
        "You are a customer support manager for a telecom operator.\n\n"
        "Route customer questions to the right specialist:\n"
        "- Subscription questions (plan info, upgrades, packages) → ask_subscription_specialist\n"
        "- Billing questions (invoices, charges, payments) → ask_billing_specialist\n"
        "- Technical issues (signal, connectivity, device problems) → ask_technical_specialist\n"
        "- Greetings and general questions → answer directly\n\n"
        "Be friendly, concise, and always synthesize specialist responses "
        "into a clear answer for the customer."
    ),
    name="main_agent",
)
