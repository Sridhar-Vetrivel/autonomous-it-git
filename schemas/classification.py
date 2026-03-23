from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List


class ClassificationResult(BaseModel):
    """Classification decision output."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    ticket_type: str = Field(
        ..., description="incident, request, change, problem"
    )
    category: str = Field(
        ..., description="vpn_access, software_install, hardware_request, etc."
    )
    sub_category: Optional[str] = None
    priority: str = Field(..., pattern="^(critical|high|medium|low)$")
    severity: str = Field(..., pattern="^(1|2|3|4)$")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in classification (0.0-1.0)"
    )
    reasoning: str = Field(..., max_length=1000)
    requires_human_review: bool = Field(
        ..., description="True if confidence < threshold"
    )
    suggested_assignment_group: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "ticket_id": "SCTASK0802841",
                "ticket_type": "request",
                "category": "vpn_access",
                "priority": "high",
                "severity": "2",
                "confidence_score": 0.92,
                "reasoning": "Clear VPN access request with high priority",
                "requires_human_review": False,
                "suggested_assignment_group": "Network & Access",
            }
        },
    )
