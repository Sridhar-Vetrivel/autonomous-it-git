# Autonomous IT Service Management Agent - Architecture Documentation

## Executive Summary

The **Autonomous IT Service Management Agent** is an end-to-end ticket resolution pipeline built on AgentField that orchestrates a multi-agent workflow for ServiceNow ticket management. The system autonomously ingests, classifies, enriches, plans, executes, validates, and learns from IT service requests with minimal human intervention.

---

## 1. System Overview

### Core Design Principles
- **Multi-Agent Orchestration**: Nine specialized agents collaborate through a control plane
- **Deterministic + Non-Deterministic Processing**: Skills handle structured operations; Reasoners handle AI-driven decisions
- **Human-in-the-Loop**: Strategic intervention points for low-confidence decisions
- **Continuous Learning**: Feedback loop captures resolution patterns and improves agent performance
- **End-to-End Traceability**: Every action, decision, and state change is logged as a DAG

### Architecture Layers
```
┌─────────────────────────────────────────────────────────────────┐
│                      ServiceNow Platform                         │
│              (CURL trigger → Ingestion Agent)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    AgentField Control Plane                      │
│  (DAG orchestration, memory fabric, multi-agent routing)        │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                  Agent Execution Layer                           │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Phase 1    │  │   Phase 2    │  │   Phase 3    │           │
│  │  Ingestion   │  │ Classification│  │  Enrichment  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Phase 4    │  │   Phase 5    │  │   Phase 6    │           │
│  │  Decision &  │  │  Execution   │  │  Validation  │           │
│  │  Planning    │  │              │  │              │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Phase 7    │  │   Phase 8    │  │   Phase 9    │           │
│  │Communication │  │  Learning &  │  │  Feedback    │           │
│  │              │  │  Improvement │  │  Integration │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│              Memory Fabric & State Management                    │
│  (Session, Agent, Global scope with vector embeddings)         │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│           External Systems & Callbacks                           │
│  (ServiceNow updates, Webhooks, Knowledge Repositories)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Nine-Agent Workflow Pipeline

### Phase 1: Ingestion Agent
**Purpose**: Parse incoming ServiceNow tickets and normalize data

**Type**: Primarily Skills-based
- **Skills**:
  - `batch_ticket_from_servicenow()`: Parse ticket JSON from ServiceNow CURL trigger
  - `normalize_ticket_fields()`: Map and validate ServiceNow fields to internal schema
  - `extract_attachments()`: Extract ticket metadata (attachments, related items)
  - `store_to_memory()`: Persist ticket in session/agent memory

**Reasoners**:
- `parse_ticket_content()`: Handle malformed tickets, validate required fields

**Output**: Normalized ticket object stored in `session.current_ticket`

**Key Functions**:
```python
@app.skill()
async def batch_ticket_from_servicenow(arguments) -> TicketData:
    """Extract ticket JSON from ServiceNow payload"""
    
@app.skill()
async def normalize_ticket_fields(arguments) -> NormalizedTicket:
    """Map ServiceNow fields to internal schema"""
    
@app.reasoner()
async def parse_ticket_content(arguments) -> TicketValidationResult:
    """Use AI to handle edge cases and validation"""
```

**Memory State**:
- `session.current_ticket`: Raw ticket data
- `session.ticket_history`: List of processed tickets

---

### Phase 2: Classification Agent
**Purpose**: Categorize tickets by type and assess initial priority/complexity

**Type**: Reasoner-driven (non-deterministic)
- **Reasoners**:
  - `classify_ticket_type()`: Determine ticket category (incident, request, change, etc.)
  - `assess_priority_and_severity()`: Evaluate urgency and impact
  - `escalate_to_human_review()`: Route low-confidence classifications to human

**Pydantic Schema**:
```python
class TicketClassification(BaseModel):
    ticket_type: str  # incident, request, change, problem
    priority: str     # critical, high, medium, low
    severity: str     # 1, 2, 3, 4
    confidence: float # 0.0 - 1.0
    reasoning: str
    requires_human_review: bool
```

**Decision Logic**:
- If confidence < 0.7 → trigger `Human Review` step
- Else → proceed to Enrichment Agent

**Memory State**:
- `session.classification_result`: Classification object
- `agent.classification_patterns`: Learned patterns per category

---

### Phase 3: Enrichment Agent
**Purpose**: Gather contextual information to inform resolution

**Type**: Skills + Reasoners
- **Skills**:
  - `lookup_user_profile()`: Search knowledge base for user context
  - `search_knowledge_base()`: Find related history and prior resolutions
  - `fetch_related_incidents()`: Query ServiceNow for similar tickets
  - `identify_related_incidents()`: Match patterns

**Reasoners**:
- `summarize_context()`: AI-driven enrichment synthesis
- `identify_service_owner()`: Determine responsible team

**Output**: Enriched ticket with context stored in `session.enriched_ticket`

**Memory State**:
- `session.related_tickets`: Array of similar resolutions
- `session.user_context`: User profile and history
- `session.service_owner`: Assignment recommendation

---

### Phase 4: Decision & Planning Agent
**Purpose**: Devise optimal resolution strategy

**Type**: Reasoner-driven
- **Reasoners**:
  - `generate_resolution_plan()`: Create step-by-step action plan
  - `assess_risk_and_impact()`: Evaluate potential issues
  - `recommend_execution_path()`: Suggest best approach

**Pydantic Schema**:
```python
class ResolutionPlan(BaseModel):
    plan_id: str
    steps: List[ExecutionStep]
    estimated_time_minutes: int
    risk_level: str  # low, medium, high
    rollback_procedure: str
    requires_approval: bool
    approval_justification: str
```

**Decision Points**:
- High risk → escalate to `Human Review`
- Requires approval → add to escalation queue
- Else → proceed to Execution Agent with plan

**Memory State**:
- `session.resolution_plan`: Full execution plan
- `session.decision_reasoning`: AI reasoning for plan selection
- `run.approvals_required`: Approval tracking

---

### Phase 5: Execution Agent
**Purpose**: Perform the actual work (scripts, provisioning, updates)

**Type**: Skills-based (deterministic)
- **Skills**:
  - `execute_plan_steps()`: Run resolution scripts
  - `handle_execution_errors()`: Catch and manage failures
  - `provision_resources()`: Create access, services, configurations
  - `log_execution_steps()`: Document each action
  - `log_execution_skipped()`: Track skipped tasks

**Error Handling**:
- Retry mechanism with exponential backoff
- Rollback on critical failure
- State persistence after each step

**Memory State**:
- `run.execution_log`: Timestamped action log
- `run.step_results`: Output from each execution step
- `run.errors`: Error records with context

---

### Phase 6: Validation & Closure Agent
**Purpose**: Verify resolution success and prepare closure

**Type**: Skills + Reasoners
- **Skills**:
  - `run_health_checks()`: Post-execution validation
  - `request_user_confirmation()`: Confirm resolution with requester
  - `close_ticket_in_servicenow()`: Update ServiceNow state

**Reasoners**:
- `evaluate_resolution_success()`: Assess if resolution met objectives

**Closure Logic**:
- If validation passes & user confirms → close ticket
- If issues remain → escalate back to Decision Agent or Human Review

**Memory State**:
- `session.validation_result`: Success/failure metrics
- `session.user_confirmation`: Requester feedback
- `session.closure_metadata`: Timestamp, resolver, notes

---

### Phase 7: Communication Agent
**Purpose**: Update ticket and notify stakeholders

**Type**: Skills-based
- **Skills**:
  - `compose_resolution_message()`: Generate clear communication
  - `send_email_notification()`: Notify requester
  - `update_servicenow_ticket()`: Post work notes and status
  - `send_team_notification()`: Alert assignment group

**Integration Points**:
- Webhooks to external notification systems
- ServiceNow work notes updates
- Email templates with ticket resolution details

**Memory State**:
- `session.communications_sent`: Record of all outbound messages
- `agent.notification_templates`: Reusable message templates

---

### Phase 8: Learning Agent
**Purpose**: Extract insights and improve agent behavior

**Type**: Reasoners + Vector operations
- **Reasoners**:
  - `analyze_resolution_effectiveness()`: Assess quality and efficiency
  - `extract_resolution_patterns()`: Identify patterns across tickets
  - `recommend_prompt_improvements()`: Suggest AI prompt refinements
  - `generate_knowledge_artifact()`: Create new knowledge base entry

**Vector Operations**:
- `app.memory.set_vector()`: Store ticket resolution as embedding
- `app.memory.similarity_search()`: Find related resolutions for future tickets

**Memory State**:
- `agent.learned_patterns`: Classification patterns
- `global.knowledge_embeddings`: Vector store of resolutions
- `agent.prompt_improvements`: Suggested LLM prompt updates

---

### Phase 9: Human Review (Conditional)
**Purpose**: Human intervention for low-confidence or escalated items

**Type**: Manual workflow
- **Trigger Points**:
  - Classification confidence < 0.7
  - Risk assessment marked as high
  - Execution errors requiring review
  - Validation failure

**Workflow**:
1. Ticket flagged and moved to human queue
2. Analyst reviews classification/plan
3. Analyst approves plan or provides corrections
4. System resumes with updated context

**Memory State**:
- `session.human_review_comments`: Analyst feedback
- `session.human_decision`: Override or approval decision

---

## 3. Data Flow & State Management

### State Lifecycle

```
TICKET INGESTION
       ↓
[session.current_ticket]
       ↓
CLASSIFICATION
       ↓
[session.classification_result]
       ↓
ENRICHMENT
       ↓
[session.enriched_ticket]
       ↓
DECISION & PLANNING
       ↓
[session.resolution_plan]
       ↓
EXECUTION
       ↓
[run.execution_log] + [run.step_results]
       ↓
VALIDATION
       ↓
[session.validation_result]
       ↓
COMMUNICATION
       ↓
[session.communications_sent]
       ↓
LEARNING
       ↓
[agent.learned_patterns] + [global.knowledge_embeddings]
```

### Memory Scopes

| Scope | Lifetime | Use Case |
|-------|----------|----------|
| **Session** | Single multi-turn conversation | Current ticket context, user session data |
| **Agent** | Across all sessions | Classification patterns, learned templates |
| **Run** | Single execution/workflow | Execution logs, temporary state |
| **Global** | System lifetime | Knowledge base, vector embeddings, org-wide patterns |

### Critical Memory Keys

```python
# Session scope - ticket-specific
session.current_ticket                 # Raw ticket data
session.classification_result          # Classification output
session.enriched_ticket               # Enriched context
session.resolution_plan               # Execution plan
session.validation_result             # Validation outcome
session.communications_sent           # Outbound messages
session.human_review_comments         # Human feedback (if applicable)

# Run scope - execution-specific
run.execution_log                     # Timestamped actions
run.step_results                      # Step outputs
run.errors                            # Error records
run.approvals_required                # Approval tracking

# Agent scope - learned knowledge
agent.learned_patterns                # Classification patterns
agent.notification_templates          # Message templates
agent.prompt_improvements             # LLM refinements

# Global scope - organization-wide
global.knowledge_embeddings           # Vector store of resolutions
global.service_owners                 # Service mappings
global.integration_configs            # External system configs
```

---

## 4. Integration Points

### ServiceNow Integration
**Trigger**: CURL request to AgentField control plane
```bash
curl -X POST http://[control_plane_url]/api/v1/execute/ingestion_agent.batch_ticket_from_servicenow \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "ticket": {
        "number": "SCTASK0802841",
        "short_description": "VPN Access Required",
        "priority": "high",
        "requested_for": "user@company.com",
        ...
      }
    }
  }'
```

**Callback**: Webhooks to ServiceNow for updates
- Ticket status updates
- Work notes addition
- Assignment changes

### External Systems
- **Knowledge Management**: Search for similar resolutions
- **User Directory**: User profile lookups
- **Asset Management**: Service/resource availability
- **Notification Service**: Email/Slack integration
- **Audit/Compliance**: Logging and compliance checks

---

## 5. Error Handling & Resilience

### Retry Logic
- **Transient Failures**: Exponential backoff (1s, 2s, 4s, 8s, 16s)
- **Permanent Failures**: Log error and escalate to human review
- **Timeout Handling**: Move to async queue with webhook callback

### Escalation Paths
```
Low Confidence (< 0.7)
        ↓
    Human Review Queue
        ↓
    Manual Analyst Review
        ↓
    Resume or Override

High Risk / Requires Approval
        ↓
    Approval Queue
        ↓
    Manager Approval
        ↓
    Execution or Return for Planning

Execution Failure
        ↓
    Error Analysis
        ↓
    Rollback (if applicable)
        ↓
    Escalate to Human Review
```

---

## 6. Performance & Optimization

### Async Processing
- Long-running tasks (> 30s) use webhooks with async_config
- Backpressure handling for downstream service delays
- Parallel processing where possible (enrichment tasks)

### Caching Strategy
- Classification patterns cached in agent memory
- Knowledge embeddings in vector store
- User/service mappings in global memory

### Observability
- Every call tracked through control plane DAG
- Memory change events trigger listeners
- Execution logs provide full audit trail

---

## 7. Deployment Architecture

### Components
1. **AgentField Control Plane**: Central orchestration
2. **Agent Runtime Nodes**: Execution environments (9 agents)
3. **Memory Fabric**: Persistent state and embeddings
4. **ServiceNow Instance**: Ticket source and destination
5. **Knowledge Base**: Vector store and resolution database

### Scaling Considerations
- Horizontal scaling of agent nodes
- Distributed memory with replication
- Load balancing across multiple instances
- Event-driven architecture for parallelism

---

## 8. Configuration & Customization

### Environment Variables
```bash
AGENTFIELD_SERVER=http://[control_plane_url]:8080
AI_MODEL=anthropic/claude-opus-4  # or OpenRouter model
SERVICENOW_INSTANCE=https://dev123456.service-now.com
SERVICENOW_API_KEY=xxx
KNOWLEDGE_BASE_URL=https://kb.company.com
NOTIFICATION_WEBHOOK=https://company.slack.com/hooks/xxx
```

### Tunable Parameters
- Classification confidence threshold (default: 0.7)
- Risk assessment thresholds
- Retry attempt limits
- Timeout durations per agent
- Vector similarity thresholds (for knowledge search)

---

## 9. Security Considerations

### Authentication & Authorization
- ServiceNow API key encrypted and stored securely
- Agent-to-agent calls validated through control plane
- Memory access scoped by role/agent

### Audit & Compliance
- All actions logged with timestamps and actor ID
- Sensitive data (passwords, tokens) masked in logs
- Compliance callbacks for regulated operations

### Data Privacy
- PII handling in tickets (user info, email)
- GDPR compliance for data retention
- Secure credential management

---

## 10. Monitoring & Alerting

### Key Metrics
- **Throughput**: Tickets processed per hour
- **Success Rate**: % of tickets fully auto-resolved
- **Human Escalation Rate**: % requiring human review
- **Average Resolution Time**: Time from ingestion to closure
- **Classification Accuracy**: % correct classifications vs. human review
- **Plan Execution Success**: % of plans executed without error

### Alerts
- High escalation rate (> 20%)
- Execution failures exceeding threshold
- Memory usage anomalies
- External service unavailability

---

## 11. Development Phases

### Phase 1 (MVP)
- Core 5 agents (Ingestion → Classification → Enrichment → Decision → Execution)
- ServiceNow integration
- Basic memory management

### Phase 2 (Enhancement)
- Add Validation & Communication agents
- Human review workflow
- Vector search integration

### Phase 3 (Intelligence)
- Learning Agent implementation
- Pattern extraction and prompt optimization
- Advanced analytics

### Phase 4 (Scale)
- Multi-tenant support
- Advanced monitoring and observability
- Performance optimization

---

## 12. Testing Strategy

### Unit Tests
- Individual skill and reasoner logic
- Pydantic schema validation
- Memory operations

### Integration Tests
- Multi-agent workflows
- ServiceNow API mocking
- State transitions

### End-to-End Tests
- Full pipeline execution with sample tickets
- Human review flow simulation
- Escalation path validation

---

## Appendix: Component Relationships

```
Ingestion Agent
    ↓ (normalized ticket)
Classification Agent
    ↓ (classification + routing decision)
    ├─→ Human Review (if confidence < 0.7)
    │   ↓ (approved with feedback)
    └─→ Enrichment Agent
        ↓ (enriched context)
        Decision & Planning Agent
            ↓ (resolution plan)
            ├─→ Human Review (if high risk)
            │   ↓ (approval)
            └─→ Execution Agent
                ↓ (execution results)
                Validation & Closure Agent
                    ↓ (validation status)
                    Communication Agent
                        ↓ (notifications sent)
                        Learning Agent
                            ↓ (patterns extracted)
                            Memory Fabric (vector embeddings stored)
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-03-18  
**Status**: Ready for Implementation
