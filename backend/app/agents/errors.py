class AgentContractError(RuntimeError):
    """Raised when deterministic agent contract inputs are invalid."""


class AgentPolicyError(RuntimeError):
    """Raised when an agent attempts to violate its bounded tool policy."""
