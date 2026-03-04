"""Subscription agent — tarife sorgulama, degistirme, paket yonetimi.

Bagimsiz agent. Hem main_agent hem billing_agent tarafindan tool olarak kullanilir.
"""

from langchain.agents import create_agent

from src.config.llm import llm
from src.config.settings import settings
from src.middleware.trim import trim_old_messages
from src.tools.subscription_tools import (
    add_package,
    change_plan,
    compare_plans,
    get_current_plan,
    search_plans,
)

_middleware = [trim_old_messages]
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import langfuse_prompt

    _middleware.insert(0, langfuse_prompt)

agent = create_agent(
    model=llm,
    tools=[get_current_plan, search_plans, compare_plans, change_plan, add_package],
    middleware=_middleware,
    system_prompt=(
        "You are a subscription and plan specialist for a telecom operator. "
        "Help customers check their current plan, search for better plans, "
        "compare options side by side, change plans, and add extra packages.\n\n"
        "Always mention contract end dates and any applicable fees when changing plans. "
        "Proactively suggest plan upgrades when usage patterns indicate frequent overages."
    ),
    name="subscription_agent",
)
