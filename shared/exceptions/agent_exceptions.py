"""
Custom exception hierarchy for the Autonomous IT Agent pipeline.
"""


class AgentError(Exception):
    """Base exception for all agent errors."""


class AgentCommunicationError(AgentError):
    """Raised when an agent fails to communicate with another agent."""


class AgentProcessingError(AgentError):
    """Raised when an agent fails to process its assigned work."""


class AgentTimeoutError(AgentError):
    """Raised when an agent operation exceeds its time limit."""


class ValidationError(AgentError):
    """Raised when data fails schema or business-rule validation."""
