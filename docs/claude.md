# Claude.md - Implementation Guide for Autonomous IT Service Management Agent

## Overview
This document provides step-by-step implementation guidance for building the Autonomous IT Service Management Agent using AgentField. It includes code templates, Pydantic schemas, memory operations, and best practices.

---

## Table of Contents
1. [Project Setup](#project-setup)
2. [Pydantic Schemas](#pydantic-schemas)
3. [Agent Implementation](#agent-implementation)
4. [Memory Management](#memory-management)
5. [Error Handling](#error-handling)
6. [Testing Patterns](#testing-patterns)
7. [Deployment](#deployment)

---

## Project Setup

### Prerequisites
- Python 3.10+
- AgentField SDK
- OpenRouter account (or direct Claude API)
- ServiceNow instance with API access

### Directory Structure
```
autonomous-it-agent/
├── main.py                 # Agent initialization
├── config.py              # Configuration and environment
├── schemas/               # Pydantic models
│   ├── ticket.py
│   ├── classification.py
│   ├── enrichment.py
│   ├── planning.py
│   └── execution.py
├── agents/                # Agent implementations
│   ├── ingestion_agent.py
│   ├── classification_agent.py
│   ├── enrichment_agent.py
│   ├── decision_planning_agent.py
│   ├── execution_agent.py
│   ├── validation_agent.py
│   ├── communication_agent.py
│   ├── learning_agent.py
│   └── human_review_agent.py
├── skills/                # Shared utility skills
│   ├── servicenow_integration.py
│   ├── knowledge_search.py
│   └── utils.py
├── tests/                 # Test suite
│   ├── test_agents.py
│   ├── test_schemas.py
│   └── test_workflows.py
├── requirements.txt       # Dependencies
└── .env                   # Environment variables
```

### Installation & Configuration

**requirements.txt**:
```
agentfield>=0.1.0
pydantic>=2.0
python-dotenv>=1.0
aiohttp>=3.9
openai>=1.3
```

**.env**:
```
# AgentField Configuration
AGENTFIELD_SERVER=http://localhost:8080
AI_MODEL=anthropic/claude-opus-4

# ServiceNow Configuration
SERVICENOW_INSTANCE=https://dev123456.service-now.com
SERVICENOW_API_KEY=your_api_key_here
SERVICENOW_TABLE=sc_task

# External Systems
KNOWLEDGE_BASE_URL=https://kb.company.com
NOTIFICATION_WEBHOOK_URL=https://company.webhook.com

# Execution Configuration
RETRY_ATTEMPTS=3
TIMEOUT_SECONDS=300
HUMAN_REVIEW_QUEUE_URL=http://localhost:3000/review
```

**config.py**:
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # AgentField
    AGENTFIELD_SERVER = os.getenv("AGENTFIELD_SERVER", "http://localhost:8080")
    AI_MODEL = os.getenv("AI_MODEL", "anthropic/claude-opus-4")
    
    # ServiceNow
    SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE")
    SERVICENOW_API_KEY = os.getenv("SERVICENOW_API_KEY")
    SERVICENOW_TABLE = os.getenv("SERVICENOW_TABLE", "sc_task")
    
    # Integration
    KNOWLEDGE_BASE_URL = os.getenv("KNOWLEDGE_BASE_URL")
    NOTIFICATION_WEBHOOK_URL = os.getenv("NOTIFICATION_WEBHOOK_URL")
    
    # Execution
    RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", 3))
    TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", 300))
    HUMAN_REVIEW_QUEUE_URL = os.getenv("HUMAN_REVIEW_QUEUE_URL")
    
    # Thresholds
    CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.7
    RISK_ESCALATION_THRESHOLD = 0.6
```

---

## Pydantic Schemas

### Base Schema: Ticket

**schemas/ticket.py**:
```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime

class TicketData(BaseModel):
    """Raw ticket data from ServiceNow"""
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
    attachments: List[str] = Field(default_factory=list, description="Attachment URLs")
    
    class Config:
        json_schema_extra = {
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
                "opened_by": "admin"
            }
        }


class NormalizedTicket(BaseModel):
    """Internal normalized ticket representation"""
    model_config = ConfigDict(extra="forbid")
    
    ticket_id: str
    title: str
    description: str
    requester_email: str
    requester_name: Optional[str] = None
    service_type: str  # vpn, software, hardware, access, etc.
    priority: str
    urgency: str  # immediate, urgent, normal, low
    impact: str    # high, medium, low
    received_at: datetime
    metadata: dict = Field(default_factory=dict)
```

### Schema: Classification

**schemas/classification.py**:
```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List

class ClassificationResult(BaseModel):
    """Classification decision output"""
    model_config = ConfigDict(extra="forbid")
    
    ticket_id: str
    ticket_type: str = Field(
        ..., 
        description="incident, request, change, problem"
    )
    category: str = Field(
        ...,
        description="vpn_access, software_install, hardware_request, etc."
    )
    sub_category: Optional[str] = None
    priority: str = Field(..., pattern="^(critical|high|medium|low)$")
    severity: str = Field(..., pattern="^(1|2|3|4)$")
    confidence_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Confidence in classification (0.0-1.0)"
    )
    reasoning: str = Field(..., max_length=1000)
    requires_human_review: bool = Field(
        ..., 
        description="True if confidence < threshold"
    )
    suggested_assignment_group: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticket_id": "SCTASK0802841",
                "ticket_type": "request",
                "category": "vpn_access",
                "priority": "high",
                "severity": "2",
                "confidence_score": 0.92,
                "reasoning": "Clear VPN access request with high priority",
                "requires_human_review": False,
                "suggested_assignment_group": "Network & Access"
            }
        }
```

### Schema: Enrichment

**schemas/enrichment.py**:
```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict

class UserProfile(BaseModel):
    """Enriched user information"""
    model_config = ConfigDict(extra="forbid")
    
    email: str
    display_name: str
    department: str
    manager: Optional[str] = None
    active: bool = True
    mfa_enabled: bool = False
    recent_tickets: List[str] = Field(default_factory=list)


class RelatedTicket(BaseModel):
    """Similar/related ticket reference"""
    model_config = ConfigDict(extra="forbid")
    
    ticket_id: str
    similarity_score: float  # 0.0-1.0
    category: str
    status: str
    resolution: Optional[str] = None
    resolution_time_hours: Optional[float] = None


class EnrichmentResult(BaseModel):
    """Enriched ticket context"""
    model_config = ConfigDict(extra="forbid")
    
    ticket_id: str
    user_profile: UserProfile
    related_tickets: List[RelatedTicket] = Field(default_factory=list)
    service_owner: str
    service_owner_team: str
    knowledge_base_articles: List[Dict[str, str]] = Field(default_factory=list)
    previous_similar_resolutions: int = Field(default=0)
    estimated_resolution_complexity: str = Field(
        ...,
        pattern="^(simple|moderate|complex)$"
    )
    required_approvals: List[str] = Field(default_factory=list)
    additional_context: Dict[str, str] = Field(default_factory=dict)
```

### Schema: Planning

**schemas/planning.py**:
```python
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

class ExecutionStep(BaseModel):
    """Single step in resolution plan"""
    model_config = ConfigDict(extra="forbid")
    
    step_id: int
    action: str  # describe what to do
    skill_or_tool: str  # which skill/tool to use
    parameters: dict = Field(default_factory=dict)
    expected_duration_minutes: int
    required_permissions: List[str] = Field(default_factory=list)
    rollback_instruction: Optional[str] = None
    skip_on_error: bool = False


class ResolutionPlan(BaseModel):
    """Complete resolution strategy"""
    model_config = ConfigDict(extra="forbid")
    
    ticket_id: str
    plan_id: str = Field(..., description="Unique plan identifier")
    steps: List[ExecutionStep]
    total_estimated_minutes: int
    risk_level: str = Field(..., pattern="^(low|medium|high)$")
    risk_description: str
    requires_approval: bool
    approval_justification: Optional[str] = None
    rollback_procedure: str = Field(...)
    success_criteria: List[str]
    dependencies: List[str] = Field(default_factory=list)
    alternative_approaches: int = Field(default=0)
```

### Schema: Execution

**schemas/execution.py**:
```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any
from datetime import datetime

class ExecutionStepResult(BaseModel):
    """Result of a single execution step"""
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
    """Complete execution record"""
    model_config = ConfigDict(extra="forbid")
    
    ticket_id: str
    plan_id: str
    execution_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    overall_status: str = Field(
        ..., 
        pattern="^(in_progress|success|partial_failure|failure)$"
    )
    step_results: list[ExecutionStepResult]
    total_duration_seconds: float
    rollback_performed: bool = False
    notes: str = ""
```

---

## Agent Implementation

### 1. Ingestion Agent

**agents/ingestion_agent.py**:
```python
import os
import asyncio
from typing import List, Dict
from agentfield import Agent, AIConfig, AsyncConfig
from datetime import datetime
from schemas.ticket import TicketData, NormalizedTicket
from config import Config

# Initialize agent
app = Agent(
    node_id="ingestion_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(
        model=Config.AI_MODEL
    ),
)

# ==================== SKILLS ====================

@app.skill()
async def batch_ticket_from_servicenow(arguments) -> TicketData:
    """
    Parse and validate incoming ServiceNow ticket.
    
    Input: ServiceNow JSON payload
    Output: TicketData object
    """
    payload = arguments.get("ticket_payload", {})
    
    try:
        ticket = TicketData(
            number=payload.get("number"),
            short_description=payload.get("short_description"),
            description=payload.get("description"),
            requested_for=payload.get("requested_for"),
            requested_item=payload.get("requested_item"),
            priority=payload.get("priority", "medium").lower(),
            state=payload.get("state", "new"),
            assignment_group=payload.get("assignment_group"),
            assigned_to=payload.get("assigned_to"),
            opened=payload.get("opened"),
            updated=payload.get("updated"),
            opened_by=payload.get("opened_by"),
            work_notes=payload.get("work_notes"),
            attachments=payload.get("attachments", [])
        )
        return ticket
    except Exception as e:
        raise ValueError(f"Failed to parse ServiceNow ticket: {str(e)}")


@app.skill()
async def normalize_ticket_fields(arguments) -> NormalizedTicket:
    """
    Normalize ServiceNow fields to internal schema.
    
    Input: TicketData
    Output: NormalizedTicket
    """
    ticket_data = arguments.get("ticket_data", {})
    
    # Map priority to internal format
    priority_map = {
        "critical": "high",
        "1": "high",
        "2": "high", 
        "high": "high",
        "medium": "medium",
        "3": "medium",
        "low": "low",
        "4": "low"
    }
    
    priority = priority_map.get(
        ticket_data.get("priority", "medium").lower(),
        "medium"
    )
    
    normalized = NormalizedTicket(
        ticket_id=ticket_data.get("number"),
        title=ticket_data.get("short_description"),
        description=ticket_data.get("description", ""),
        requester_email=ticket_data.get("requested_for"),
        requester_name=None,  # Enriched later
        service_type=categorize_service_type(
            ticket_data.get("requested_item", "")
        ),
        priority=priority,
        urgency="immediate" if priority == "high" else "normal",
        impact="high" if priority == "high" else "medium",
        received_at=datetime.fromisoformat(
            ticket_data.get("opened", datetime.now().isoformat())
        ),
        metadata={
            "servicenow_id": ticket_data.get("number"),
            "assignment_group": ticket_data.get("assignment_group"),
            "work_notes": ticket_data.get("work_notes")
        }
    )
    
    return normalized


@app.skill()
async def extract_attachments(arguments) -> Dict:
    """Extract and store attachment references."""
    ticket_data = arguments.get("ticket_data", {})
    attachments = ticket_data.get("attachments", [])
    
    return {
        "ticket_id": ticket_data.get("number"),
        "attachment_count": len(attachments),
        "attachments": attachments
    }


@app.skill()
async def store_to_memory(arguments) -> Dict:
    """Store normalized ticket in session memory."""
    ticket_id = arguments.get("ticket_id")
    normalized_ticket = arguments.get("normalized_ticket")
    
    # Store in session memory
    await app.memory.set(
        "session",
        "current_ticket",
        normalized_ticket
    )
    
    # Also store in history
    history = await app.memory.get("session", "ticket_history") or []
    if not isinstance(history, list):
        history = []
    history.append(ticket_id)
    await app.memory.set(
        "session",
        "ticket_history",
        history
    )
    
    return {
        "status": "stored",
        "ticket_id": ticket_id,
        "memory_key": f"session.current_ticket"
    }


# ==================== REASONER ====================

@app.reasoner()
async def parse_ticket_content(arguments) -> Dict:
    """
    Use AI to validate and handle edge cases in ticket parsing.
    """
    ticket_data = arguments.get("ticket_data", {})
    
    response = await app.ai(
        system="""You are a ticket validation expert. Analyze the ticket 
        for missing required fields, inconsistencies, or data quality issues.
        Return a structured validation result.""",
        user=f"""Please validate this ticket:
        
        Number: {ticket_data.get('number')}
        Title: {ticket_data.get('short_description')}
        Description: {ticket_data.get('description')}
        Requester: {ticket_data.get('requested_for')}
        Priority: {ticket_data.get('priority')}
        
        Identify any issues and provide recommendations.""",
        schema=TicketValidationResult
    )
    
    return response.model_dump()


# ==================== HELPER FUNCTIONS ====================

def categorize_service_type(requested_item: str) -> str:
    """Map requested item to service type."""
    item_lower = requested_item.lower()
    
    if any(x in item_lower for x in ["vpn", "network", "internet"]):
        return "vpn"
    elif any(x in item_lower for x in ["software", "license", "application"]):
        return "software"
    elif any(x in item_lower for x in ["hardware", "laptop", "printer", "monitor"]):
        return "hardware"
    elif any(x in item_lower for x in ["access", "permission", "role"]):
        return "access"
    else:
        return "general"


# ==================== MAIN ORCHESTRATOR ====================

async def process_incoming_ticket(ticket_payload: Dict):
    """
    Main orchestration function: Ingestion → Classification
    """
    try:
        # Step 1: Parse ticket
        ticket_data = await batch_ticket_from_servicenow(
            {"ticket_payload": ticket_payload}
        )
        
        # Step 2: Normalize
        normalized = await normalize_ticket_fields(
            {"ticket_data": ticket_data.model_dump()}
        )
        
        # Step 3: Extract attachments
        attachments = await extract_attachments(
            {"ticket_data": ticket_data.model_dump()}
        )
        
        # Step 4: Store in memory
        await store_to_memory({
            "ticket_id": ticket_data.number,
            "normalized_ticket": normalized.model_dump()
        })
        
        # Step 5: Call Classification Agent
        classification_result = await app.call(
            "classification_agent.classify_ticket_type",
            input={"ticket_id": ticket_data.number}
        )
        
        return {
            "status": "success",
            "ticket_id": ticket_data.number,
            "ingestion_status": "complete",
            "next_step": "classification_agent"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "next_step": "error_handling"
        }


if __name__ == "__main__":
    # Test with sample ticket
    sample_ticket = {
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
        "opened_by": "admin"
    }
    
    result = asyncio.run(process_incoming_ticket(sample_ticket))
    print(result)
```

### 2. Classification Agent

**agents/classification_agent.py**:
```python
from agentfield import Agent, AIConfig
from schemas.classification import ClassificationResult
from config import Config
import asyncio

app = Agent(
    node_id="classification_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(model=Config.AI_MODEL),
)

@app.reasoner()
async def classify_ticket_type(arguments) -> ClassificationResult:
    """
    Classify ticket into type, category, priority using AI.
    """
    ticket_id = arguments.get("ticket_id")
    
    # Retrieve ticket from memory
    ticket = await app.memory.get("session", "current_ticket")
    
    if not ticket:
        raise ValueError(f"Ticket {ticket_id} not found in memory")
    
    response = await app.ai(
        system="""You are an IT ticket classification expert. Analyze tickets 
        and assign:
        - ticket_type: incident, request, change, or problem
        - category: specific service category
        - priority: critical, high, medium, low
        - severity: 1 (critical), 2 (high), 3 (medium), 4 (low)
        - confidence_score: 0.0-1.0 based on clarity
        
        Be conservative: if unsure, lower the confidence score.""",
        user=f"""Classify this ticket:
        
        ID: {ticket.get('ticket_id')}
        Title: {ticket.get('title')}
        Description: {ticket.get('description')}
        Service Type: {ticket.get('service_type')}
        Priority: {ticket.get('priority')}
        Urgency: {ticket.get('urgency')}
        
        Provide classification with reasoning.""",
        schema=ClassificationResult
    )
    
    # Store classification in memory
    await app.memory.set(
        "session",
        "classification_result",
        response.model_dump()
    )
    
    # If low confidence, escalate to human review
    if response.confidence_score < Config.CLASSIFICATION_CONFIDENCE_THRESHOLD:
        await app.memory.set(
            "session",
            "requires_human_review",
            True
        )
        return await escalate_to_human_review(response)
    
    return response


@app.skill()
async def escalate_to_human_review(classification_result: ClassificationResult) -> ClassificationResult:
    """Route low-confidence classifications to human review."""
    # Update status
    classification_result.requires_human_review = True
    
    # Queue for review
    await app.memory.set(
        "session",
        "human_review_reason",
        f"Low classification confidence: {classification_result.confidence_score:.2f}"
    )
    
    return classification_result
```

---

## Memory Management

### Pattern: Session-Scoped Ticket Workflow

```python
# Store ticket in session memory
await app.memory.set("session", "current_ticket", ticket_data)

# Retrieve for next agent
ticket = await app.memory.get("session", "current_ticket")

# Store classification result in session
await app.memory.set("session", "classification_result", classification_data)

# Build workflow state
workflow_state = {
    "ticket": await app.memory.get("session", "current_ticket"),
    "classification": await app.memory.get("session", "classification_result"),
    "enrichment": await app.memory.get("session", "enriched_ticket"),
    "plan": await app.memory.get("session", "resolution_plan")
}
```

### Pattern: Learning from Resolutions

```python
# Store resolution as vector embedding
await app.memory.set_vector(
    ticket_id,
    embedding_vector,  # Claude embedding
    metadata={
        "ticket_type": classification.ticket_type,
        "category": classification.category,
        "resolution_time": resolution_time_minutes,
        "success": success_flag
    }
)

# Search similar resolutions
results = await app.memory.similarity_search(
    query_embedding,
    top_k=5
)

for result in results:
    print(f"Similar ticket: {result['key']}, Score: {result['score']}")
    print(f"Resolution: {result['text']}")
```

---

## Error Handling

### Retry Pattern with Exponential Backoff

```python
async def retry_operation(operation, max_attempts=3):
    """Retry an operation with exponential backoff."""
    import asyncio
    
    for attempt in range(max_attempts):
        try:
            return await operation()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise  # Final attempt failed
            
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            await asyncio.sleep(wait_time)
```

### Escalation Pattern

```python
async def escalate_ticket(ticket_id: str, reason: str):
    """Move ticket to human review queue."""
    await app.memory.set("session", "escalation_reason", reason)
    
    # Notify human reviewers via webhook
    import aiohttp
    async with aiohttp.ClientSession() as session:
        await session.post(
            Config.HUMAN_REVIEW_QUEUE_URL,
            json={
                "ticket_id": ticket_id,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
        )
```

---

## Testing Patterns

### Unit Test Example

```python
# tests/test_agents.py
import pytest
from agents.ingestion_agent import batch_ticket_from_servicenow
from schemas.ticket import TicketData

@pytest.mark.asyncio
async def test_batch_ticket_from_servicenow_happy_path():
    """Test successful ticket parsing."""
    payload = {
        "number": "SCTASK0802841",
        "short_description": "VPN Access",
        "priority": "high",
        # ... other fields
    }
    
    result = await batch_ticket_from_servicenow({"ticket_payload": payload})
    
    assert isinstance(result, TicketData)
    assert result.number == "SCTASK0802841"
    assert result.priority == "high"


@pytest.mark.asyncio
async def test_batch_ticket_invalid_priority():
    """Test handling of invalid priority."""
    payload = {
        "number": "SCTASK001",
        "priority": "invalid",  # Should fail
        # ... other fields
    }
    
    with pytest.raises(ValueError):
        await batch_ticket_from_servicenow({"ticket_payload": payload})
```

---

## Deployment

### Docker Compose Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  agentfield-control-plane:
    image: agentfield/control-plane:latest
    ports:
      - "8080:8080"
    environment:
      - LOG_LEVEL=info
      - DB_URL=postgres://db:5432/agentfield
    depends_on:
      - db

  ingestion-agent:
    build:
      context: .
      dockerfile: agents/ingestion_agent.Dockerfile
    environment:
      - AGENTFIELD_SERVER=http://agentfield-control-plane:8080
      - AI_MODEL=anthropic/claude-opus-4
    depends_on:
      - agentfield-control-plane

  classification-agent:
    build:
      context: .
      dockerfile: agents/classification_agent.Dockerfile
    environment:
      - AGENTFIELD_SERVER=http://agentfield-control-plane:8080
      - AI_MODEL=anthropic/claude-opus-4
    depends_on:
      - agentfield-control-plane

  # ... additional agents

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=agentfield
      - POSTGRES_PASSWORD=password
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-03-18
