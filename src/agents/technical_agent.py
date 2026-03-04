"""Technical support agent — network, diagnostics, trouble tickets.

Bagimsiz agent. main_agent tarafindan tool olarak kullanilir.
"""

from langchain.agents import create_agent

from src.config.llm import llm
from src.config.settings import settings
from src.middleware.trim import trim_old_messages
from src.tools.technical_tools import (
    check_device_compatibility,
    check_network_status,
    create_trouble_ticket,
    run_line_diagnostic,
)

_middleware = [trim_old_messages]
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import langfuse_prompt

    _middleware.insert(0, langfuse_prompt)

agent = create_agent(
    model=llm,
    tools=[check_network_status, run_line_diagnostic, check_device_compatibility, create_trouble_ticket],
    middleware=_middleware,
    system_prompt=(
        "You are a technical support specialist for a telecom operator. "
        "Help customers diagnose connectivity issues, check network status in their area, "
        "verify device compatibility, and create trouble tickets for unresolved problems.\n\n"
        "Always run diagnostics before creating a trouble ticket. "
        "If diagnostics show normal results, guide the customer through basic troubleshooting "
        "(restart device, toggle airplane mode, reset network settings) before escalating."
    ),
    name="technical_agent",
)
