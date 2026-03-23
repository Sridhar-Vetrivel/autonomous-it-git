from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any, List
from datetime import datetime


class ExecutionStepResult(BaseModel):
    """Result of a single execution step."""

    model_config = ConfigDict(extra="forbid")

    step_id: int
    status: str = Field(..., pattern="^(success|failure|partial|skipped)$")
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    output: Optional[Any] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    retry_count: int = 0


class ExecutionLog(BaseModel):
    """Complete execution record."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    plan_id: str
    execution_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    overall_status: str = Field(
        ..., pattern="^(in_progress|success|partial_failure|failure)$"
    )
    step_results: List[ExecutionStepResult]
    total_duration_seconds: float
    rollback_performed: bool = False
    notes: str = ""


class ValidationResult(BaseModel):
    """Outcome of post-execution validation checks."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    execution_id: str
    all_checks_passed: bool
    checks: List[dict] = Field(default_factory=list)
    user_confirmed: bool = False
    validation_notes: str = ""
    recommended_action: str = Field(
        ..., pattern="^(close|replan|escalate)$"
    )
