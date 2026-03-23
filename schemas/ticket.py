from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


class TicketData(BaseModel):
    """Raw ticket data from ServiceNow."""

    model_config = ConfigDict(extra="forbid")

    number: str = Field(..., description="ServiceNow ticket ID (e.g., SCTASK0802841)")
    short_description: str = Field(..., max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    requested_for: str = Field(..., description="User email or ID")
    requested_item: str = Field(..., description="Item/service requested")
    priority: str = Field(..., pattern="^(critical|high|medium|low)$")
    state: str = Field(..., description="Current ticket state")
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None
    opened: str = Field(..., description="ISO timestamp")
    updated: str = Field(..., description="ISO timestamp")
    opened_by: str = Field(...)
    work_notes: Optional[str] = None
    attachments: List[str] = Field(
        default_factory=list, description="Attachment URLs"
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "number": "SCTASK0802841",
                "short_description": "VPN Access Required",
                "description": "User needs VPN access for remote work",
                "requested_for": "john.doe@company.com",
                "requested_item": "VPN License",
                "priority": "high",
                "state": "new",
                "assignment_group": "IT Support",
                "opened": "2025-03-18T09:00:00Z",
                "updated": "2025-03-18T09:00:00Z",
                "opened_by": "admin",
            }
        },
    )


class NormalizedTicket(BaseModel):
    """Internal normalized ticket representation."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    title: str
    description: str
    requester_email: str
    requester_name: Optional[str] = None
    service_type: str  # vpn, software, hardware, access, general
    priority: str = Field(..., pattern="^(critical|high|medium|low)$")
    urgency: str = Field(..., pattern="^(immediate|urgent|normal|low)$")
    impact: str = Field(..., pattern="^(high|medium|low)$")
    received_at: datetime
    metadata: dict = Field(default_factory=dict)
