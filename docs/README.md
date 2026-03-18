# Autonomous IT Service Management Agent

**End-to-End Ticket Resolution Pipeline Using AgentField**

An enterprise-grade, multi-agent orchestration system for automating IT service request fulfillment. Seamlessly integrates with ServiceNow to ingest, classify, plan, execute, validate, and continuously improve ticket resolution workflows.

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Agent Pipeline](#agent-pipeline)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Memory & State Management](#memory--state-management)
- [Human Review Workflow](#human-review-workflow)
- [Testing](#testing)
- [Monitoring & Observability](#monitoring--observability)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### ✨ Core Capabilities

- **Multi-Agent Orchestration**: 9 specialized agents working in concert
- **Autonomous Ticket Resolution**: End-to-end workflow from ingestion to closure
- **ServiceNow Integration**: Native CURL-triggered ingestion and real-time updates
- **Intelligent Classification**: AI-powered ticket categorization with confidence scoring
- **Context Enrichment**: Automatic user profiling, knowledge base search, and pattern matching
- **Smart Planning**: Risk-aware resolution planning with rollback procedures
- **Execution Management**: Deterministic skill execution with error handling and retries
- **Validation & Closure**: Automated success validation and ticket closure
- **Human-in-the-Loop**: Strategic escalation for low-confidence decisions
- **Continuous Learning**: Resolution pattern extraction and prompt optimization
- **Vector Search**: Semantic similarity search for knowledge reuse
- **Full Observability**: DAG-based execution tracking and audit trails

### 🎯 Business Benefits

- **Reduced Resolution Time**: 60-80% faster ticket resolution
- **Lower Escalation Rate**: Fewer high-confidence decisions escalated to humans
- **Consistent Quality**: Deterministic and auditable execution paths
- **Knowledge Capture**: Automated learning from successful resolutions
- **Scalability**: Horizontal scaling with distributed agent nodes
- **Cost Savings**: Reduced manual intervention and higher first-contact resolution rate

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Docker & Docker Compose (for local deployment)
- ServiceNow instance with REST API enabled
- OpenRouter account (for LLM access) or direct Claude API key
- ~4GB RAM minimum (development), 16GB+ recommended (production)

### 1. Clone & Setup

```bash
# Clone the repository
git clone https://github.com/your-org/autonomous-it-agent.git
cd autonomous-it-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy and edit environment file
cp .env.example .env

# Edit .env with your credentials
# AGENTFIELD_SERVER=http://localhost:8080
# AI_MODEL=anthropic/claude-opus-4
# SERVICENOW_INSTANCE=https://your-instance.service-now.com
# SERVICENOW_API_KEY=your_key_here
```

### 3. Start Services

```bash
# Start AgentField control plane and all agents
docker-compose up -d

# Verify services are running
docker-compose ps

# Check logs
docker-compose logs -f agentfield-control-plane
```

### 4. Send Your First Ticket

```bash
# Trigger ingestion with sample ticket
curl -X POST http://localhost:8080/api/v1/execute/ingestion_agent.batch_ticket_from_servicenow \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "ticket_payload": {
        "number": "SCTASK0802841",
        "short_description": "VPN Access Required",
        "description": "User needs VPN access for remote work",
        "requested_for": "john.doe@company.com",
        "requested_item": "VPN License",
        "priority": "high",
        "state": "new",
        "opened": "2025-03-18T09:00:00Z",
        "updated": "2025-03-18T09:00:00Z",
        "opened_by": "admin"
      }
    }
  }'
```

Expected response:
```json
{
  "status": "success",
  "ticket_id": "SCTASK0802841",
  "ingestion_status": "complete",
  "next_step": "classification_agent"
}
```

---

## Architecture Overview

### System Design

```
ServiceNow (CURL Trigger)
        ↓
Ingestion Agent (Parse & Normalize)
        ↓
Classification Agent (Categorize & Route)
        ↓ [Human Review if needed]
        ↓
Enrichment Agent (Context & History)
        ↓
Decision & Planning Agent (Strategy)
        ↓ [Approval Gate]
        ↓
Execution Agent (Do the Work)
        ↓
Validation & Closure Agent (Verify)
        ↓
Communication Agent (Notify)
        ↓
Learning Agent (Improve)
        ↓
Memory Fabric (Store Embeddings)
```

### Key Components

| Component | Role | Type |
|-----------|------|------|
| **Ingestion Agent** | Parse ServiceNow tickets | Skills-based |
| **Classification Agent** | AI-driven ticket categorization | Reasoner-based |
| **Enrichment Agent** | Gather context and history | Skills + Reasoners |
| **Decision & Planning** | Create resolution strategy | Reasoner-based |
| **Execution Agent** | Execute plans deterministically | Skills-based |
| **Validation & Closure** | Verify and close tickets | Skills + Reasoners |
| **Communication Agent** | Update ServiceNow + notify | Skills-based |
| **Learning Agent** | Extract patterns and improve | Reasoners + Vector ops |
| **Human Review** | Manual intervention workflow | Manual (conditional) |

---

## Agent Pipeline

### Phase 1: Ingestion
**Input**: ServiceNow CURL trigger  
**Output**: Normalized ticket in memory  
**Skills**: Parse, normalize, extract, store

```
ServiceNow CURL
    ↓
Parse ticket JSON
    ↓
Validate fields
    ↓
Normalize to internal schema
    ↓
Store in session.current_ticket
    ↓
→ Classification Agent
```

### Phase 2: Classification
**Input**: Normalized ticket  
**Output**: Classification with priority/category  
**Decision**: Escalate if confidence < 0.7

```
Current ticket
    ↓
AI: Classify ticket type, category, priority
    ↓
Generate confidence score
    ↓
[Confidence < 0.7?]
├─→ YES: Escalate to Human Review
└─→ NO: Store classification_result
    ↓
→ Enrichment Agent
```

### Phase 3: Enrichment
**Input**: Classified ticket  
**Output**: Enriched context (user profile, related tickets, KB articles)

```
Classification result
    ↓
Lookup user profile
    ↓
Search knowledge base
    ↓
Find related tickets
    ↓
Identify service owner
    ↓
Store enriched_ticket
    ↓
→ Decision & Planning Agent
```

### Phase 4: Decision & Planning
**Input**: Enriched ticket  
**Output**: Resolution plan with steps and rollback

```
Enriched ticket
    ↓
AI: Generate resolution plan
    ↓
Assess risk level
    ↓
[High risk OR requires approval?]
├─→ YES: Escalate to Human Review
└─→ NO: Store resolution_plan
    ↓
→ Execution Agent
```

### Phase 5: Execution
**Input**: Resolution plan  
**Output**: Execution log with step results

```
Resolution plan
    ↓
FOR EACH step:
  ├─→ Execute skill
  ├─→ Check success
  ├─→ Log result
  └─→ [Failed?] → Retry (3x) → Rollback
    ↓
Store execution_log
    ↓
→ Validation & Closure Agent
```

### Phase 6: Validation & Closure
**Input**: Execution results  
**Output**: Validation status & ticket closed

```
Execution results
    ↓
Run health checks
    ↓
[All passed?]
├─→ NO: Escalate or retry
└─→ YES: Request user confirmation
    ↓
[User confirms?]
├─→ NO: Re-escalate
└─→ YES: Close ticket in ServiceNow
    ↓
Store closure_metadata
    ↓
→ Communication Agent
```

### Phase 7: Communication
**Input**: Closed ticket details  
**Output**: Notifications sent

```
Closure metadata
    ↓
Compose resolution message
    ↓
Send email to requester
    ↓
Update ServiceNow work notes
    ↓
Send team notification
    ↓
Store communications_sent
    ↓
→ Learning Agent
```

### Phase 8: Learning
**Input**: Complete resolution record  
**Output**: Patterns extracted & stored

```
Resolution record
    ↓
Analyze effectiveness
    ↓
Extract resolution patterns
    ↓
Generate vector embedding
    ↓
Store in knowledge_embeddings
    ↓
Recommend prompt improvements
    ↓
→ Learning complete
```

---

## Installation

### Option A: Docker Compose (Recommended)

```bash
# Clone and configure
git clone https://github.com/your-org/autonomous-it-agent.git
cd autonomous-it-agent
cp .env.example .env
# Edit .env with your credentials

# Start all services
docker-compose up -d

# Verify
docker-compose ps
```

### Option B: Local Development

```bash
# Virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start AgentField control plane (separate terminal)
agentfield start

# Start ingestion agent
python agents/ingestion_agent.py

# Start classification agent
python agents/classification_agent.py

# ... start other agents similarly
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENTFIELD_SERVER` | ✓ | localhost:8080 | AgentField control plane URL |
| `AI_MODEL` | ✓ | anthropic/claude-opus-4 | LLM model identifier |
| `SERVICENOW_INSTANCE` | ✓ | - | ServiceNow instance URL |
| `SERVICENOW_API_KEY` | ✓ | - | ServiceNow API authentication |
| `SERVICENOW_TABLE` | ✓ | sc_task | ServiceNow table name |
| `KNOWLEDGE_BASE_URL` | - | - | Internal KB endpoint |
| `NOTIFICATION_WEBHOOK_URL` | - | - | Webhook for notifications |
| `RETRY_ATTEMPTS` | - | 3 | Max retry attempts |
| `TIMEOUT_SECONDS` | - | 300 | Operation timeout |
| `HUMAN_REVIEW_QUEUE_URL` | - | - | Human review system URL |

### Threshold Configuration

Edit `config.py` to adjust:

```python
CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.7      # Escalate if lower
RISK_ESCALATION_THRESHOLD = 0.6               # Escalate if higher
MAX_EXECUTION_RETRIES = 3
VECTOR_SIMILARITY_TOP_K = 5
```

---

## Usage

### 1. Trigger Ticket Ingestion (ServiceNow CURL)

ServiceNow webhook configuration:
```
POST http://your-agentfield-server:8080/api/v1/execute/ingestion_agent.batch_ticket_from_servicenow
Content-Type: application/json
```

Test with curl:
```bash
curl -X POST http://localhost:8080/api/v1/execute/ingestion_agent.batch_ticket_from_servicenow \
  -H "Content-Type: application/json" \
  -d @sample_ticket.json
```

### 2. Monitor Workflow Execution

View DAG execution in AgentField UI:
```
http://localhost:8080/workflows
```

### 3. Check Ticket Status

Query memory for ticket status:
```python
import asyncio
from agentfield import Agent, AIConfig
from config import Config

app = Agent(
    node_id="query_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(model=Config.AI_MODEL)
)

async def get_ticket_status(ticket_id):
    # Retrieve workflow state
    ticket = await app.memory.get("session", "current_ticket")
    classification = await app.memory.get("session", "classification_result")
    plan = await app.memory.get("session", "resolution_plan")
    execution = await app.memory.get("run", "execution_log")
    
    return {
        "ticket_id": ticket_id,
        "current_stage": "execution",
        "classification": classification,
        "plan": plan,
        "execution": execution
    }

result = asyncio.run(get_ticket_status("SCTASK0802841"))
print(result)
```

### 4. Handle Human Review

When a ticket requires human review:
1. It's moved to `session.requires_human_review = True`
2. Human reviewer accesses review queue
3. Reviewer provides feedback/override in `session.human_review_comments`
4. Workflow resumes from next agent

```python
# Resume workflow after human review
await app.call(
    "enrichment_agent.enrich_ticket",
    input={"ticket_id": "SCTASK0802841"}
)
```

---

## API Reference

### Core Endpoints

#### Ingestion
```
POST /api/v1/execute/ingestion_agent.batch_ticket_from_servicenow
Input: {"ticket_payload": {...}}
Output: {"status": "success", "ticket_id": "SCTASK..."}
```

#### Classification
```
POST /api/v1/execute/classification_agent.classify_ticket_type
Input: {"ticket_id": "SCTASK..."}
Output: {"ticket_type": "request", "category": "vpn_access", "confidence_score": 0.92}
```

#### Enrichment
```
POST /api/v1/execute/enrichment_agent.enrich_ticket
Input: {"ticket_id": "SCTASK..."}
Output: {"user_profile": {...}, "related_tickets": [...], "service_owner": "..."}
```

#### Decision & Planning
```
POST /api/v1/execute/decision_planning_agent.generate_resolution_plan
Input: {"ticket_id": "SCTASK..."}
Output: {"plan_id": "...", "steps": [...], "risk_level": "medium"}
```

#### Execution
```
POST /api/v1/execute/execution_agent.execute_plan
Input: {"ticket_id": "SCTASK...", "plan_id": "..."}
Output: {"execution_id": "...", "step_results": [...], "overall_status": "success"}
```

### Query Endpoints

```
GET /api/v1/memory/get?scope=session&key=current_ticket
GET /api/v1/workflow/dag?ticket_id=SCTASK0802841
GET /api/v1/memory/search/vector?query_embedding=[...]&top_k=5
```

---

## Memory & State Management

### Memory Scopes

```python
# Session: Current ticket workflow
await app.memory.set("session", "current_ticket", ticket_data)
ticket = await app.memory.get("session", "current_ticket")

# Agent: Learned patterns across sessions
await app.memory.set("agent", "classification_patterns", patterns)

# Run: Single execution state
await app.memory.set("run", "execution_log", log)

# Global: Organization-wide knowledge
await app.memory.set_vector("ticket_123", embedding, metadata={...})
results = await app.memory.similarity_search(query_embedding, top_k=5)
```

### Critical Memory Keys

```python
# Workflow state
session.current_ticket                  # Raw ticket
session.classification_result           # AI classification
session.enriched_ticket                 # Context
session.resolution_plan                 # Strategy
session.validation_result               # Validation output

# Execution tracking
run.execution_log                       # Complete log
run.step_results                        # Per-step outputs
run.errors                              # Error records

# Learning
agent.learned_patterns                  # Classification patterns
global.knowledge_embeddings             # Vector store of resolutions
```

### Listening to Memory Changes

```python
@app.on_change("session.resolution_plan")
async def on_plan_created(event):
    """Triggered when resolution plan is created"""
    print(f"Plan created: {event.data}")
    # Trigger notifications, logging, etc.

@app.on_change("run.execution_log")
async def on_execution_update(event):
    """Triggered on each execution step"""
    print(f"Execution update: {event.data}")
```

---

## Human Review Workflow

### Escalation Triggers

Tickets are escalated to human review when:

1. **Low Classification Confidence** (< 0.7)
2. **High Risk Assessment** (> 0.6)
3. **Execution Failure** (after retries)
4. **Validation Failure**
5. **Requires Approval** (policy-based)

### Human Review Process

```
1. Ticket flagged
   ├─→ Stored in session.requires_human_review = True
   └─→ Moved to human queue

2. Human analyst review
   ├─→ Reviews classification/plan
   ├─→ Provides feedback/corrections
   └─→ Stores in session.human_review_comments

3. Workflow resumes
   ├─→ System reads human feedback
   ├─→ Updates context if needed
   └─→ Continues from next agent
```

### Example: Low Confidence Escalation

```python
# In classification_agent.py
if response.confidence_score < Config.CLASSIFICATION_CONFIDENCE_THRESHOLD:
    # Escalate to human review
    await app.memory.set("session", "requires_human_review", True)
    await app.memory.set(
        "session",
        "escalation_reason",
        f"Low classification confidence: {response.confidence_score:.2f}"
    )
    
    # Notify human reviewers
    await notify_human_reviewers(ticket_id)
    
    # Return early
    return response
```

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_agents.py

# Run with coverage
pytest --cov=agents tests/
```

### Sample Tests

```python
# tests/test_ingestion_agent.py
import pytest
from agents.ingestion_agent import batch_ticket_from_servicenow

@pytest.mark.asyncio
async def test_parse_valid_ticket():
    payload = {"number": "SCTASK001", "short_description": "Test", ...}
    result = await batch_ticket_from_servicenow({"ticket_payload": payload})
    assert result.number == "SCTASK001"

@pytest.mark.asyncio
async def test_parse_invalid_ticket():
    payload = {"number": "SCTASK001"}  # Missing required fields
    with pytest.raises(ValueError):
        await batch_ticket_from_servicenow({"ticket_payload": payload})
```

### End-to-End Tests

```bash
# Run full pipeline test
pytest tests/test_e2e.py -v

# With sample tickets from Excel
python tests/load_excel_tickets.py Quanta_UARs.xlsx
```

---

## Monitoring & Observability

### View DAG Execution

```
http://localhost:8080/workflows
```

Shows:
- Ticket flow through agents
- Execution times per agent
- Memory state changes
- Error paths and escalations

### Metrics Dashboard

Key metrics to track:
- **Throughput**: Tickets/hour
- **Success Rate**: % auto-resolved
- **Escalation Rate**: % to human review
- **Avg Resolution Time**: Hours
- **Classification Accuracy**: vs. human review

### Logging

All operations logged:
```bash
# View logs
docker-compose logs -f ingestion-agent
docker-compose logs -f classification-agent

# Search logs
docker-compose logs | grep "SCTASK0802841"
```

### Alerts

Configure alerts for:
- Escalation rate > 20%
- Execution failures > 5%
- Memory usage spikes
- Agent unavailability

---

## Troubleshooting

### Common Issues

#### 1. Agent Not Responding
```bash
# Check if agent is running
docker-compose ps

# Check agent logs
docker-compose logs classification-agent

# Restart agent
docker-compose restart classification-agent
```

#### 2. Ticket Stuck in Memory
```python
# Check memory state
result = await app.memory.get("session", "current_ticket")
print(result)

# Clear if needed
await app.memory.delete("session", "current_ticket")
```

#### 3. ServiceNow Integration Issues
```bash
# Test ServiceNow connectivity
curl -X GET https://your-instance.service-now.com/api/now/table/sc_task/SCTASK0802841 \
  -H "Authorization: Basic $(echo -n 'user:pass' | base64)"

# Check API key
echo $SERVICENOW_API_KEY
```

#### 4. Low Classification Confidence
- Review ticket data quality
- Check if classification patterns are trained
- Increase training data in global.learned_patterns

### Debug Mode

Enable verbose logging:
```bash
export LOG_LEVEL=debug
docker-compose up
```

---

## Contributing

### Development Setup

```bash
# Fork repo and clone
git clone https://github.com/your-fork/autonomous-it-agent.git
cd autonomous-it-agent

# Create feature branch
git checkout -b feature/my-feature

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests before committing
pytest tests/
ruff format .
ruff check .

# Commit with proper attribution
git commit -m "Add my feature" -m "Co-Authored-By: Your Name <email@example.com>"
```

### Guidelines

- Follow PEP 8
- Use type hints
- Write tests for new features
- Update documentation
- Use async/await for I/O
- Follow SOLID principles

---

## Performance Optimization

### Scaling

**Horizontal Scaling**:
- Deploy multiple agent instances
- Use load balancer
- Distributed memory with replication

**Caching**:
- Cache classification patterns
- Pre-compute embeddings
- Reuse KB search results

**Async Processing**:
- Long operations (> 30s) use webhooks
- Parallel enrichment tasks
- Batch knowledge searches

### Benchmarks (Typical)

| Operation | Time | Notes |
|-----------|------|-------|
| Ingestion | 0.5s | Parse and normalize |
| Classification | 2-3s | AI reasoning |
| Enrichment | 1-2s | KB search + user lookup |
| Decision & Planning | 3-4s | AI planning |
| Execution | 5-60s | Depends on actions |
| Validation | 1-2s | Health checks |
| **Total (Auto)** | 13-72s | Varies by complexity |
| **Human Review** | 5-30 min | Manual analyst |

---

## Future Roadmap

### Phase 2 (Q2 2025)
- [ ] Advanced analytics dashboard
- [ ] Custom workflow builder UI
- [ ] Multi-tenant support
- [ ] Advanced escalation rules

### Phase 3 (Q3 2025)
- [ ] Model fine-tuning capabilities
- [ ] Advanced vector search options
- [ ] Workflow version control
- [ ] A/B testing framework

### Phase 4 (Q4 2025)
- [ ] ChatOps integration (Slack/Teams)
- [ ] ITSM-specific modules (change mgmt, incident response)
- [ ] Advanced compliance reporting
- [ ] Multi-cloud support

---

## Support & Resources

- **Documentation**: See `ARCHITECTURE.md` and `claude.md`
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: support@example.com
- **Slack**: #autonomous-it-agent

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

Built with:
- **AgentField**: Multi-agent orchestration framework
- **Claude**: Advanced LLM reasoning
- **ServiceNow**: Enterprise IT service management platform
- **OpenRouter**: LLM model routing

---

## Quick Reference Cheat Sheet

```bash
# Start all services
docker-compose up -d

# Send test ticket
curl -X POST http://localhost:8080/api/v1/execute/ingestion_agent.batch_ticket_from_servicenow \
  -H "Content-Type: application/json" \
  -d '{"input": {"ticket_payload": {...}}}'

# View logs
docker-compose logs -f ingestion-agent

# Run tests
pytest tests/

# Check status
docker-compose ps

# Stop services
docker-compose down

# View DAG
http://localhost:8080/workflows
```

---

**Last Updated**: 2025-03-18  
**Version**: 1.0.0  
**Status**: Production Ready
