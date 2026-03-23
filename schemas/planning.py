from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional


class ExecutionStep(BaseModel):
    """Single step in a resolution plan."""

    model_config = ConfigDict(extra="forbid")

    step_id: int
    action: str
    skill_or_tool: str
    parameters: dict = Field(default_factory=dict)
    expected_duration_minutes: int
    required_permissions: List[str] = Field(default_factory=list)
    rollback_instruction: Optional[str] = None
    skip_on_error: bool = False


class ResolutionPlan(BaseModel):
    """Complete resolution strategy."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    plan_id: str = Field(..., description="Unique plan identifier")
    steps: List[ExecutionStep]
    total_estimated_minutes: int
    risk_level: str = Field(..., pattern="^(low|medium|high)$")
    risk_description: str
    requires_approval: bool
    approval_justification: Optional[str] = None
    rollback_procedure: str
    success_criteria: List[str]
    dependencies: List[str] = Field(default_factory=list)
    alternative_approaches: int = Field(default=0)
