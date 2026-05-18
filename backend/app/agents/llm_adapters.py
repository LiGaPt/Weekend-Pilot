from __future__ import annotations

import json
from typing import Any, Sequence
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError

from backend.app.agents.deterministic import (
    DeterministicDiningAgent,
    DeterministicDiscoveryAgent,
    DeterministicItineraryPlannerAgent,
    sanitize_agent_metadata,
)
from backend.app.agents.errors import AgentPolicyError
from backend.app.agents.policies import validate_agent_tool_usage
from backend.app.agents.schemas import AgentInvocationContext, AgentResult
from backend.app.llm import LLMCallMetadata, LLMChatMessage, LLMError, LLMUsage
from backend.app.planning import CandidateCollectionResult, CandidateEnrichmentResult, ItineraryDraftResult, QueryPlan


class _CandidateLLMOutput(BaseModel):
    summary: str
    candidate_ids: list[str]
    tool_names_used: list[str] = Field(default_factory=list)
    risk_codes: list[str] = Field(default_factory=list)


class _ItineraryLLMOutput(BaseModel):
    summary: str
    draft_ids: list[str]


class LLMDiscoveryAgent:
    adapter_version = "llm_discovery_v0"
    role = "discovery"

    def __init__(
        self,
        *,
        client: Any | None,
        deterministic: DeterministicDiscoveryAgent | None = None,
        model_id: str | None = None,
        base_url: str | None = None,
        missing_config_reason: str = "llm_config_incomplete",
    ) -> None:
        self._client = client
        self._deterministic = deterministic or DeterministicDiscoveryAgent()
        self._model_id = model_id
        self._base_url_host = _base_url_host(base_url)
        self._missing_config_reason = missing_config_reason

    def summarize(
        self,
        plan: QueryPlan,
        collection: CandidateCollectionResult,
        enrichment: CandidateEnrichmentResult,
        context: AgentInvocationContext | None = None,
    ) -> AgentResult:
        deterministic = self._deterministic.summarize(plan, collection, enrichment, context=context)
        if self._client is None:
            return _with_llm_metadata(
                deterministic,
                _fallback_metadata(
                    self._missing_config_reason,
                    model_id=self._model_id,
                    base_url_host=self._base_url_host,
                ),
            )
        try:
            completion = self._client.chat_json(
                messages=_candidate_messages(
                    role="discovery",
                    user_input=plan.intent.raw_text,
                    candidates=[
                        {
                            "candidate_id": item.candidate.candidate_id,
                            "name": item.candidate.name,
                            "category": item.candidate.category,
                            "tags": list(item.candidate.tags),
                        }
                        for item in enrichment.enriched_activity_candidates
                    ],
                ),
                temperature=0.2,
                max_tokens=400,
            )
            output = _CandidateLLMOutput.model_validate(completion.content_json)
            validate_agent_tool_usage("discovery", output.tool_names_used)
            allowed_ids = {item.candidate.candidate_id for item in enrichment.enriched_activity_candidates}
            if not set(output.candidate_ids) <= allowed_ids:
                return _with_llm_metadata(
                    deterministic,
                    _fallback_metadata(
                        "invalid_candidate_ids",
                        model_id=self._model_id,
                        base_url_host=self._base_url_host,
                    ),
                )
        except AgentPolicyError:
            return _with_llm_metadata(
                deterministic,
                _fallback_metadata(
                    "agent_policy_mismatch",
                    model_id=self._model_id,
                    base_url_host=self._base_url_host,
                    error_type="AgentPolicyError",
                ),
            )
        except ValidationError:
            return _with_llm_metadata(
                deterministic,
                _fallback_metadata(
                    "llm_schema_mismatch",
                    model_id=self._model_id,
                    base_url_host=self._base_url_host,
                    error_type="ValidationError",
                ),
            )
        except Exception as exc:
            return _with_llm_metadata(deterministic, _fallback_metadata_from_exception(exc, self._model_id, self._base_url_host))

        return AgentResult(
            role="discovery",
            status="completed",
            summary=output.summary,
            adapter_version=self.adapter_version,
            tool_names_used=list(output.tool_names_used),
            output_json=sanitize_agent_metadata(
                {
                    "candidate_count": len(output.candidate_ids),
                    "candidate_ids": output.candidate_ids,
                    "risk_codes": output.risk_codes,
                    "llm": completion.metadata.model_dump(mode="json"),
                }
            ),
        )


class LLMDiningAgent:
    adapter_version = "llm_dining_v0"
    role = "dining"

    def __init__(
        self,
        *,
        client: Any | None,
        deterministic: DeterministicDiningAgent | None = None,
        model_id: str | None = None,
        base_url: str | None = None,
        missing_config_reason: str = "llm_config_incomplete",
    ) -> None:
        self._client = client
        self._deterministic = deterministic or DeterministicDiningAgent()
        self._model_id = model_id
        self._base_url_host = _base_url_host(base_url)
        self._missing_config_reason = missing_config_reason

    def summarize(
        self,
        plan: QueryPlan,
        collection: CandidateCollectionResult,
        enrichment: CandidateEnrichmentResult,
        context: AgentInvocationContext | None = None,
    ) -> AgentResult:
        deterministic = self._deterministic.summarize(plan, collection, enrichment, context=context)
        if self._client is None:
            return _with_llm_metadata(
                deterministic,
                _fallback_metadata(
                    self._missing_config_reason,
                    model_id=self._model_id,
                    base_url_host=self._base_url_host,
                ),
            )
        try:
            completion = self._client.chat_json(
                messages=_candidate_messages(
                    role="dining",
                    user_input=plan.intent.raw_text,
                    candidates=[
                        {
                            "candidate_id": item.candidate.candidate_id,
                            "name": item.candidate.name,
                            "category": item.candidate.category,
                            "tags": list(item.candidate.tags),
                            "queue": _safe_evidence(item.queue),
                            "table_availability": _safe_evidence(item.table_availability),
                        }
                        for item in enrichment.enriched_dining_candidates
                    ],
                ),
                temperature=0.2,
                max_tokens=400,
            )
            output = _CandidateLLMOutput.model_validate(completion.content_json)
            validate_agent_tool_usage("dining", output.tool_names_used)
            allowed_ids = {item.candidate.candidate_id for item in enrichment.enriched_dining_candidates}
            if not set(output.candidate_ids) <= allowed_ids:
                return _with_llm_metadata(
                    deterministic,
                    _fallback_metadata(
                        "invalid_candidate_ids",
                        model_id=self._model_id,
                        base_url_host=self._base_url_host,
                    ),
                )
        except AgentPolicyError:
            return _with_llm_metadata(
                deterministic,
                _fallback_metadata(
                    "agent_policy_mismatch",
                    model_id=self._model_id,
                    base_url_host=self._base_url_host,
                    error_type="AgentPolicyError",
                ),
            )
        except ValidationError:
            return _with_llm_metadata(
                deterministic,
                _fallback_metadata(
                    "llm_schema_mismatch",
                    model_id=self._model_id,
                    base_url_host=self._base_url_host,
                    error_type="ValidationError",
                ),
            )
        except Exception as exc:
            return _with_llm_metadata(deterministic, _fallback_metadata_from_exception(exc, self._model_id, self._base_url_host))

        return AgentResult(
            role="dining",
            status="completed",
            summary=output.summary,
            adapter_version=self.adapter_version,
            tool_names_used=list(output.tool_names_used),
            output_json=sanitize_agent_metadata(
                {
                    "candidate_count": len(output.candidate_ids),
                    "candidate_ids": output.candidate_ids,
                    "risk_codes": output.risk_codes,
                    "llm": completion.metadata.model_dump(mode="json"),
                }
            ),
        )


class LLMItineraryPlannerAgent:
    adapter_version = "llm_itinerary_planner_v0"
    role = "itinerary_planner"

    def __init__(
        self,
        *,
        client: Any | None,
        deterministic: DeterministicItineraryPlannerAgent | None = None,
        model_id: str | None = None,
        base_url: str | None = None,
        missing_config_reason: str = "llm_config_incomplete",
    ) -> None:
        self._client = client
        self._deterministic = deterministic or DeterministicItineraryPlannerAgent()
        self._model_id = model_id
        self._base_url_host = _base_url_host(base_url)
        self._missing_config_reason = missing_config_reason

    def generate(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
        context: AgentInvocationContext | None = None,
    ) -> tuple[AgentResult, ItineraryDraftResult]:
        deterministic_result, drafts = self._deterministic.generate(plan, enrichment, context=context)
        if not drafts.drafts:
            return (
                _with_llm_metadata(
                    deterministic_result,
                    _fallback_metadata(
                        "no_deterministic_drafts",
                        model_id=self._model_id,
                        base_url_host=self._base_url_host,
                    ),
                ),
                drafts,
            )
        if self._client is None:
            return (
                _with_llm_metadata(
                    deterministic_result,
                    _fallback_metadata(
                        self._missing_config_reason,
                        model_id=self._model_id,
                        base_url_host=self._base_url_host,
                    ),
                ),
                drafts,
            )
        try:
            completion = self._client.chat_json(
                messages=[
                    LLMChatMessage(
                        role="system",
                        content=(
                            "Return JSON with summary and draft_ids. "
                            "Only choose from existing draft IDs."
                        ),
                    ),
                    LLMChatMessage(
                        role="user",
                        content=json.dumps(
                            {
                                "user_input": plan.intent.raw_text,
                                "drafts": [
                                    {
                                        "draft_id": draft.draft_id,
                                        "title": draft.title,
                                        "summary": draft.summary,
                                        "total_duration_minutes": draft.feasibility.total_duration_minutes,
                                        "warnings": draft.feasibility.warnings,
                                    }
                                    for draft in drafts.drafts
                                ],
                            },
                            ensure_ascii=False,
                        ),
                    ),
                ],
                temperature=0.2,
                max_tokens=400,
            )
            output = _ItineraryLLMOutput.model_validate(completion.content_json)
            draft_by_id = {draft.draft_id: draft for draft in drafts.drafts}
            if (
                not output.draft_ids
                or len(output.draft_ids) != len(set(output.draft_ids))
                or not set(output.draft_ids) <= set(draft_by_id)
            ):
                return (
                    _with_llm_metadata(
                        deterministic_result,
                        _fallback_metadata(
                            "invalid_draft_ids",
                            model_id=self._model_id,
                            base_url_host=self._base_url_host,
                        ),
                    ),
                    drafts,
                )
        except ValidationError:
            return (
                _with_llm_metadata(
                    deterministic_result,
                    _fallback_metadata(
                        "llm_schema_mismatch",
                        model_id=self._model_id,
                        base_url_host=self._base_url_host,
                        error_type="ValidationError",
                    ),
                ),
                drafts,
            )
        except Exception as exc:
            return (
                _with_llm_metadata(deterministic_result, _fallback_metadata_from_exception(exc, self._model_id, self._base_url_host)),
                drafts,
            )

        reordered = [draft_by_id[draft_id] for draft_id in output.draft_ids]
        reordered_result = drafts.model_copy(update={"drafts": reordered})
        return (
            AgentResult(
                role="itinerary_planner",
                status="completed",
                summary=output.summary,
                adapter_version=self.adapter_version,
                output_json=sanitize_agent_metadata(
                    {
                        "draft_count": len(reordered),
                        "draft_ids": output.draft_ids,
                        "generator_version": drafts.generator_version,
                        "llm": completion.metadata.model_dump(mode="json"),
                    }
                ),
            ),
            reordered_result,
        )


def _candidate_messages(*, role: str, user_input: str, candidates: Sequence[dict[str, Any]]) -> list[LLMChatMessage]:
    return [
        LLMChatMessage(
            role="system",
            content=(
                "Return JSON with summary, candidate_ids, tool_names_used, and risk_codes. "
                "Only reference provided candidate IDs and allowed read tools."
            ),
        ),
        LLMChatMessage(
            role="user",
            content=json.dumps(
                {"role": role, "user_input": user_input, "candidates": list(candidates)},
                ensure_ascii=False,
            ),
        ),
    ]


def _with_llm_metadata(result: AgentResult, metadata: dict[str, Any]) -> AgentResult:
    output = dict(result.output_json)
    output["llm"] = metadata
    return result.model_copy(update={"output_json": sanitize_agent_metadata(output)})


def _fallback_metadata(
    fallback_reason: str,
    *,
    model_id: str | None = None,
    base_url_host: str | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    return LLMCallMetadata(
        provider_kind="openai_compatible",
        model_id=model_id,
        base_url_host=base_url_host,
        latency_ms=None,
        usage=LLMUsage(),
        status="fallback",
        fallback_reason=fallback_reason,
        error_type=error_type,
    ).model_dump(mode="json")


def _fallback_metadata_from_exception(
    exc: Exception,
    model_id: str | None,
    base_url_host: str | None,
) -> dict[str, Any]:
    fallback_reason = getattr(exc, "fallback_reason", "llm_provider_error")
    if fallback_reason not in {
        "llm_timeout",
        "llm_provider_error",
        "llm_bad_json",
        "llm_schema_mismatch",
        "agent_policy_mismatch",
        "invalid_candidate_ids",
        "invalid_draft_ids",
        "llm_config_incomplete",
    }:
        fallback_reason = "llm_provider_error"
    return _fallback_metadata(
        fallback_reason,
        model_id=model_id,
        base_url_host=base_url_host,
        error_type=type(exc).__name__ if isinstance(exc, LLMError) else type(exc).__name__,
    )


def _base_url_host(base_url: str | None) -> str | None:
    if not base_url:
        return None
    return urlparse(base_url).hostname


def _safe_evidence(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return sanitize_agent_metadata(value)
