from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict


class UserProfile(BaseModel):
    """Enriched user information."""

    model_config = ConfigDict(extra="forbid")

    email: str
    display_name: str
    department: str
    manager: Optional[str] = None
    active: bool = True
    mfa_enabled: bool = False
    recent_tickets: List[str] = Field(default_factory=list)


class RelatedTicket(BaseModel):
    """Similar/related ticket reference."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    category: str
    status: str
    resolution: Optional[str] = None
    resolution_time_hours: Optional[float] = None


class EnrichmentResult(BaseModel):
    """Enriched ticket context."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    user_profile: UserProfile
    related_tickets: List[RelatedTicket] = Field(default_factory=list)
    service_owner: str
    service_owner_team: str
    knowledge_base_articles: List[Dict[str, str]] = Field(default_factory=list)
    previous_similar_resolutions: int = Field(default=0)
    estimated_resolution_complexity: str = Field(
        ..., pattern="^(simple|moderate|complex)$"
    )
    required_approvals: List[str] = Field(default_factory=list)
    additional_context: Dict[str, str] = Field(default_factory=dict)
