from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr

from backend.app.agents.deterministic import (
    DeterministicDiningAgent,
    DeterministicDiscoveryAgent,
    DeterministicItineraryPlannerAgent,
    DeterministicSupervisorAgent,
    DeterministicValidatorRecoveryAgent,
)
from backend.app.agents.llm_adapters import LLMDiningAgent, LLMDiscoveryAgent, LLMItineraryPlannerAgent
from backend.app.core.config import Settings
from backend.app.llm import OpenAICompatibleChatClient


@dataclass(frozen=True)
class AgentAdapterSet:
    supervisor: DeterministicSupervisorAgent
    discovery: DeterministicDiscoveryAgent | LLMDiscoveryAgent
    dining: DeterministicDiningAgent | LLMDiningAgent
    itinerary_planner: DeterministicItineraryPlannerAgent | LLMItineraryPlannerAgent
    validator_recovery: DeterministicValidatorRecoveryAgent


def build_agent_adapters(
    settings: Settings,
    *,
    llm_client: Any | None = None,
) -> AgentAdapterSet:
    supervisor = DeterministicSupervisorAgent()
    validator = DeterministicValidatorRecoveryAgent()

    if not settings.llm_enabled:
        return AgentAdapterSet(
            supervisor=supervisor,
            discovery=DeterministicDiscoveryAgent(),
            dining=DeterministicDiningAgent(),
            itinerary_planner=DeterministicItineraryPlannerAgent(),
            validator_recovery=validator,
        )

    client = llm_client
    config_complete = _llm_config_complete(settings)
    if client is None and config_complete:
        client = OpenAICompatibleChatClient(
            api_key=_secret_value(settings.llm_api_key),
            base_url=str(settings.llm_base_url),
            model_id=str(settings.llm_model_id),
            timeout=settings.llm_timeout,
        )

    return AgentAdapterSet(
        supervisor=supervisor,
        discovery=LLMDiscoveryAgent(
            client=client,
            model_id=settings.llm_model_id,
            base_url=settings.llm_base_url,
            missing_config_reason="llm_config_incomplete",
        ),
        dining=LLMDiningAgent(
            client=client,
            model_id=settings.llm_model_id,
            base_url=settings.llm_base_url,
            missing_config_reason="llm_config_incomplete",
        ),
        itinerary_planner=LLMItineraryPlannerAgent(
            client=client,
            model_id=settings.llm_model_id,
            base_url=settings.llm_base_url,
            missing_config_reason="llm_config_incomplete",
        ),
        validator_recovery=validator,
    )


def _llm_config_complete(settings: Settings) -> bool:
    return all(
        [
            _secret_value(settings.llm_api_key).strip(),
            (settings.llm_base_url or "").strip(),
            (settings.llm_model_id or "").strip(),
        ]
    )


def _secret_value(value: SecretStr | None) -> str:
    return value.get_secret_value() if value is not None else ""
