from __future__ import annotations

from backend.app.agents.errors import AgentPolicyError
from backend.app.agents.schemas import AgentRole, AgentToolPolicy
from backend.app.tool_gateway.registry import READ_TOOLS, WRITE_TOOLS


_ALLOWED_READ_TOOLS: dict[AgentRole, tuple[str, ...]] = {
    "supervisor": (),
    "discovery": (
        "search_poi",
        "get_poi_detail",
        "check_opening_hours",
        "check_queue",
        "check_ticket_availability",
        "check_route",
    ),
    "dining": (
        "search_poi",
        "get_poi_detail",
        "check_opening_hours",
        "check_queue",
        "check_table_availability",
        "check_route",
    ),
    "itinerary_planner": (),
    "validator_recovery": (),
}


def default_agent_policy(role: AgentRole) -> AgentToolPolicy:
    return AgentToolPolicy(
        role=role,
        allowed_read_tools=list(_ALLOWED_READ_TOOLS[role]),
        allowed_write_tools=[],
        may_execute_write_tools=False,
    )


def default_agent_policies() -> dict[AgentRole, AgentToolPolicy]:
    return {
        role: default_agent_policy(role)
        for role in _ALLOWED_READ_TOOLS
    }


def validate_agent_tool_usage(role: AgentRole, tool_names: list[str]) -> None:
    policy = default_agent_policy(role)
    allowed_read_tools = set(policy.allowed_read_tools)
    read_tools = set(READ_TOOLS)
    write_tools = set(WRITE_TOOLS)

    for tool_name in tool_names:
        if tool_name in write_tools:
            raise AgentPolicyError(f"{role} agents may not execute or reference write tool {tool_name!r}.")
        if tool_name not in read_tools:
            raise AgentPolicyError(f"{role} agents referenced unknown tool {tool_name!r}.")
        if tool_name not in allowed_read_tools:
            raise AgentPolicyError(f"{role} agents may not reference read tool {tool_name!r}.")
