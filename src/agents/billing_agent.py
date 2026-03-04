"""Billing agent — fatura sorgulama, odeme, taksitlendirme.

Fatura asim tespitinde subscription_agent'i tool olarak cagirarak
musteriye uygun tarife onerisi yapar (agent-as-tool pattern).
"""

import uuid

from langchain.agents import create_agent
from langchain.tools import tool

from src.agents.subscription_agent import agent as subscription_agent
from src.config.llm import llm
from src.config.settings import settings
from src.middleware.trim import trim_old_messages
from src.tools.billing_tools import (
    explain_charges,
    get_invoice,
    get_payment_history,
    initiate_payment_plan,
)


# --- subscription_agent'i tool olarak kullan (agent-as-tool) ----------------


@tool
async def suggest_plan_change(msisdn: str) -> str:
    """Suggest a better plan when the customer has frequent overages.
    Delegates to the subscription specialist agent.

    Args:
        msisdn: Customer phone number.
    """
    result = await subscription_agent.ainvoke(
        {"messages": [{"role": "user", "content": f"Customer {msisdn} has frequent data overages. Compare their current plan with higher-tier options and recommend the best upgrade."}]},
        config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
    )
    return result["messages"][-1].content


# --- Agent ----------------------------------------------------------------

_middleware = [trim_old_messages]
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import langfuse_prompt

    _middleware.insert(0, langfuse_prompt)

agent = create_agent(
    model=llm,
    tools=[get_invoice, get_payment_history, explain_charges, initiate_payment_plan, suggest_plan_change],
    middleware=_middleware,
    system_prompt=(
        "You are a billing specialist for a telecom operator. "
        "Help customers view invoices, understand charges, check payment history, "
        "and set up installment payment plans.\n\n"
        "When you notice data overages or extra charges that recur, ALWAYS use "
        "suggest_plan_change to recommend a more suitable plan to the customer. "
        "Be transparent about all charges and explain any fees clearly."
    ),
    name="billing_agent",
)
