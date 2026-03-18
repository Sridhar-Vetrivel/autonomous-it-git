# Visual Reference Guide - Autonomous IT Service Management Agent

## Agent Interaction Map

```
                        ┌─────────────────────────────┐
                        │    ServiceNow Platform      │
                        │   (CURL Trigger Entry)      │
                        └────────────────┬────────────┘
                                         │
                                         ▼
                    ╔═══════════════════════════════════╗
                    ║    INGESTION AGENT               ║
                    ║  (Parse & Normalize)              ║
                    ║  Skills: batch_ticket, normalize  ║
                    ║  Output: session.current_ticket   ║
                    ╚═════════════════┬═════════════════╝
                                      │
                                      ▼
                    ╔═══════════════════════════════════╗
                    ║  CLASSIFICATION AGENT            ║
                    ║  (AI Categorization)              ║
                    ║  Reasoner: classify_ticket_type   ║
                    ║  Output: classification_result    ║
                    ║  Decision: confidence > 0.7?      ║
                    ╚═════════════┬═══════════════════╝
                                  │
                    ┌─────────────┴─────────────┐
                    │ confidence < 0.7          │
                    │ (Escalate to Human)       │
                    ▼                           ▼
              ╔══════════════╗      ╔═══════════════════════╗
              ║  HUMAN       ║      ║ ENRICHMENT AGENT      ║
              ║  REVIEW 1    ║      ║ (Context Gathering)   ║
              ║              ║      ║ Skills: lookup_user   ║
              ║  Analyst     ║─────▶ Skills: search_kb      ║
              ║  decides &   │      Skills: identify_owner  ║
              ║  overrides   │      Output: enriched_ticket ║
              ╚══════════════╝      ╚═══════════════┬═══════╝
                    │                              │
                    │ Feedback provided           │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                   ╔═══════════════════════════════════╗
                   ║ DECISION & PLANNING AGENT        ║
                   ║ (Strategy & Risk Assessment)      ║
                   ║ Reasoner: generate_resolution_plan║
                   ║ Output: resolution_plan           ║
                   ║ Decision: risk_level high?        ║
                   ╚═════════════┬═══════════════════╝
                                 │
                   ┌─────────────┴──────────────┐
                   │ High Risk / Approval       │
                   │ Needed                     │
                   ▼                            ▼
              ╔══════════════╗       ╔════════════════════╗
              ║  HUMAN       ║       ║ EXECUTION AGENT    ║
              ║  REVIEW 2    ║       ║ (Do the Work)       ║
              ║              ║       ║ Skills: execute     ║
              ║  Manager     ║──────▶ Skills: handle_errors║
              ║  approval    │       Skills: log           ║
              ║  & feedback  │       Output: execution_log ║
              ╚══════════════╝       ╚═════════┬══════════╝
                   │                           │
                   │ Approved                  │
                   └──────────────┬────────────┘
                                  │
                    ╔═════════════▼══════════════════╗
                    ║ VALIDATION & CLOSURE AGENT    ║
                    ║ (Verify Success)               ║
                    ║ Skills: run_health_checks     ║
                    ║ Reasoner: evaluate_success    ║
                    ║ Output: validation_result     ║
                    ║ Decision: all checks passed?   ║
                    ╚═════════════┬══════════════════╝
                                  │
                    ┌─────────────┴─────────────┐
                    │ Validation Failed         │
                    │ (Escalate or Retry)       │
                    ▼                           ▼
              ╔══════════════╗      ╔═══════════════════════╗
              ║  HUMAN       ║      ║ COMMUNICATION AGENT   ║
              ║  REVIEW 3    ║      ║ (Notify & Update)     ║
              ║              ║      ║ Skills: compose_msg   ║
              ║  Remediate   ║─────▶ Skills: send_email    ║
              ║  or approve  │      Skills: update_sn      ║
              ║  workaround  │      Output: notify status  ║
              ╚══════════════╝      ╚═════════┬════════════╝
                    │                        │
                    │ Override provided      │
                    └──────────────┬─────────┘
                                   │
                   ╔═══════════════▼════════════════╗
                   ║  LEARNING AGENT               ║
                   ║  (Continuous Improvement)      ║
                   ║  Reasoner: analyze_effectiveness│
                   ║  Reasoner: extract_patterns    ║
                   ║  Vector: set_vector, similarity ║
                   ║  Output: knowledge_embeddings  ║
                   ╚═══════════════┬════════════════╝
                                   │
                   ╔═══════════════▼════════════════╗
                   ║  MEMORY FABRIC              ║
                   ║  ├─ session.*  (ticket WF)  ║
                   ║  ├─ agent.*    (patterns)   ║
                   ║  ├─ run.*      (execution)  ║
                   ║  └─ global.*   (knowledge)  ║
                   └════════════════════════════╝
```

---

## State Progression Flowchart

```
START: New ServiceNow Ticket
       │
       ▼
    [INGESTION]
       │
       ├─ Parse JSON
       ├─ Normalize fields
       ├─ Validate schema
       └─ Store in session.current_ticket
       │
       ▼
    [CLASSIFICATION]
       │
       ├─ AI: categorize ticket
       ├─ AI: assess priority
       ├─ Generate confidence_score
       │
       ├─◇ confidence_score >= 0.7?
       │  │
       │  ├─ NO ──┐
       │  │       └──────────────────────┐
       │  │                              │
       │  └─ YES ──────┐                 │
       │               │                 │
       │               ▼                 │
       │            [ENRICHMENT]         │
       │               │                 │
       │               ├─ User lookup    │
       │               ├─ KB search      │
       │               ├─ Find related   │
       │               └─ Store enriched │
       │                                 │
       │               ▼                 │
       │         [DECISION & PLANNING]   │
       │               │                 │
       │               ├─ Generate plan  │
       │               ├─ Assess risk    │
       │               │                 │
       │               ├─◇ risk high?    │
       │               │  │              │
       │               │  ├─ YES ──┐     │
       │               │  │        │     │
       │               │  └─ NO ──┐│     │
       │               │          ││     │
       │               └──────────┘│     │
       │                           │     │
       │      ┌────────────────────┼─────┤
       │      │ HUMAN REVIEW       │     │
       │      │ • Low confidence   │     │
       │      │ • High risk        │     │
       │      │ • Requires approval│     │
       │      │                    │     │
       │      └────────────────────┴─────┘
       │                           │
       │                    (Override/Approval)
       │                           │
       ▼                           ▼
    [EXECUTION]
       │
       ├─ FOR EACH step in plan:
       │  ├─ Execute skill
       │  ├─ Check result
       │  ├─ Log action
       │  ├─ On error: retry 3x
       │  └─ On failure: rollback
       │
       ├─ Store execution_log
       │
       ▼
    [VALIDATION]
       │
       ├─ Run health checks
       ├─ Verify resolution
       │
       ├─◇ All checks passed?
       │  │
       │  ├─ NO ──────────────────┐
       │  │                       │
       │  └─ YES ──────┐          │
       │               │          │
       │               ▼          │
       │            [COMMUNICATION]
       │               │          │
       │               ├─ Compose msg
       │               ├─ Email user
       │               ├─ Update SN
       │               └─ Notify team
       │                          │
       │               ▼          │
       │            [LEARNING]    │
       │               │          │
       │               ├─ Analyze result
       │               ├─ Extract patterns
       │               ├─ Generate embeddings
       │               └─ Store improvements
       │                          │
       ▼                          ▼
    END: Ticket Resolved      ESCALATE
         (Closed in SN)       (Human Review)
```

---

## Memory State Machine

```
Session Memory Timeline
========================

1. INGESTION
   ├─ session.current_ticket = normalized_ticket
   └─ session.ticket_history = [ticket_id]

2. CLASSIFICATION
   ├─ session.classification_result = classification
   ├─ [IF confidence < 0.7]
   │  └─ session.requires_human_review = True
   │     └─ session.escalation_reason = "Low confidence"
   └─ [ELSE] Continue...

3. ENRICHMENT
   ├─ session.enriched_ticket = enrichment_result
   ├─ session.user_context = user_profile
   └─ session.related_tickets = [similar_tickets]

4. DECISION & PLANNING
   ├─ session.resolution_plan = plan
   ├─ [IF high_risk]
   │  └─ session.requires_human_review = True
   │     └─ session.escalation_reason = "High risk"
   └─ [ELSE] Continue...

5. EXECUTION
   ├─ run.execution_log = execution_record
   ├─ run.step_results = [step_1, step_2, ...]
   └─ run.errors = [error_records]

6. VALIDATION
   ├─ session.validation_result = validation
   ├─ session.user_confirmation = yes/no
   └─ session.closure_metadata = {timestamp, resolver}

7. COMMUNICATION
   └─ session.communications_sent = [messages]

8. LEARNING
   ├─ agent.learned_patterns = updated_patterns
   ├─ global.knowledge_embeddings = vector_store
   └─ agent.prompt_improvements = recommendations
```

---

## Pydantic Schema Hierarchy

```
TicketData (Input from ServiceNow)
    │
    ├─ number: str
    ├─ short_description: str
    ├─ description: str
    ├─ requested_for: str
    ├─ requested_item: str
    ├─ priority: str [critical|high|medium|low]
    ├─ state: str
    ├─ assignment_group: str
    ├─ assigned_to: str
    ├─ opened: datetime
    ├─ updated: datetime
    └─ work_notes: str

         ▼

NormalizedTicket (Internal Standard)
    │
    ├─ ticket_id: str
    ├─ title: str
    ├─ description: str
    ├─ requester_email: str
    ├─ requester_name: str
    ├─ service_type: str [vpn|software|hardware|access|general]
    ├─ priority: str
    ├─ urgency: str
    ├─ impact: str
    ├─ received_at: datetime
    └─ metadata: dict

         ▼

ClassificationResult
    │
    ├─ ticket_type: str [incident|request|change|problem]
    ├─ category: str
    ├─ sub_category: str
    ├─ priority: str
    ├─ severity: str
    ├─ confidence_score: float [0.0-1.0]
    ├─ reasoning: str
    ├─ requires_human_review: bool
    ├─ suggested_assignment_group: str
    └─ tags: list[str]

         ▼

EnrichmentResult
    │
    ├─ user_profile: UserProfile
    ├─ related_tickets: list[RelatedTicket]
    ├─ service_owner: str
    ├─ service_owner_team: str
    ├─ knowledge_base_articles: list[dict]
    ├─ previous_similar_resolutions: int
    ├─ estimated_resolution_complexity: str
    ├─ required_approvals: list[str]
    └─ additional_context: dict

         ▼

ResolutionPlan
    │
    ├─ plan_id: str
    ├─ steps: list[ExecutionStep]
    │   ├─ step_id: int
    │   ├─ action: str
    │   ├─ skill_or_tool: str
    │   ├─ parameters: dict
    │   ├─ expected_duration_minutes: int
    │   ├─ required_permissions: list[str]
    │   ├─ rollback_instruction: str
    │   └─ skip_on_error: bool
    ├─ total_estimated_minutes: int
    ├─ risk_level: str [low|medium|high]
    ├─ requires_approval: bool
    ├─ rollback_procedure: str
    ├─ success_criteria: list[str]
    └─ dependencies: list[str]

         ▼

ExecutionLog
    │
    ├─ execution_id: str
    ├─ started_at: datetime
    ├─ completed_at: datetime
    ├─ overall_status: str [in_progress|success|partial_failure|failure]
    ├─ step_results: list[ExecutionStepResult]
    │   ├─ step_id: int
    │   ├─ status: str
    │   ├─ start_time: datetime
    │   ├─ end_time: datetime
    │   ├─ duration_seconds: float
    │   ├─ output: any
    │   ├─ error_message: str
    │   └─ retry_count: int
    ├─ total_duration_seconds: float
    └─ rollback_performed: bool
```

---

## Decision Gate Reference

```
GATE 1: Classification Confidence (After Classification Agent)
┌─────────────────────────────────────────────────────┐
│ Condition: confidence_score < 0.7                   │
├─────────────────────────────────────────────────────┤
│ If TRUE:  Escalate to Human Review                  │
│           ├─ Set session.requires_human_review=True │
│           ├─ Queue for analyst review               │
│           └─ Wait for override/approval             │
├─────────────────────────────────────────────────────┤
│ If FALSE: Continue to Enrichment Agent              │
└─────────────────────────────────────────────────────┘

GATE 2: Risk Assessment (After Decision & Planning)
┌─────────────────────────────────────────────────────┐
│ Condition: risk_level == "high" OR                  │
│            requires_approval == True                │
├─────────────────────────────────────────────────────┤
│ If TRUE:  Escalate to Human Review                  │
│           ├─ Set session.requires_human_review=True │
│           ├─ Queue for manager approval             │
│           └─ Wait for decision                      │
├─────────────────────────────────────────────────────┤
│ If FALSE: Continue to Execution Agent               │
└─────────────────────────────────────────────────────┘

GATE 3: Execution Success (After Execution)
┌─────────────────────────────────────────────────────┐
│ Condition: overall_status != "success"              │
├─────────────────────────────────────────────────────┤
│ If TRUE:  Attempt Rollback                          │
│           ├─ Execute rollback_procedure             │
│           ├─ On rollback failure: escalate          │
│           └─ Log rollback_performed=True            │
├─────────────────────────────────────────────────────┤
│ If FALSE: Continue to Validation Agent              │
└─────────────────────────────────────────────────────┘

GATE 4: Validation Success (After Validation)
┌─────────────────────────────────────────────────────┐
│ Condition: all_checks_passed == False               │
├─────────────────────────────────────────────────────┤
│ If TRUE:  Escalate to Human Review                  │
│           ├─ Set session.requires_human_review=True │
│           ├─ Provide validation failure details     │
│           └─ Wait for human decision                │
├─────────────────────────────────────────────────────┤
│ If FALSE: Continue to Communication Agent           │
│           └─ Close ticket in ServiceNow             │
└─────────────────────────────────────────────────────┘
```

---

## Skills vs Reasoners Quick Reference

```
INGESTION AGENT (Mostly Skills)
├─ SKILL:     batch_ticket_from_servicenow()
├─ SKILL:     normalize_ticket_fields()
├─ SKILL:     extract_attachments()
├─ SKILL:     store_to_memory()
└─ REASONER:  parse_ticket_content()

CLASSIFICATION AGENT (Mostly Reasoner)
├─ REASONER:  classify_ticket_type()  ◄─── AI REASONING
└─ SKILL:     escalate_to_human_review()

ENRICHMENT AGENT (Mixed)
├─ SKILL:     lookup_user_profile()
├─ SKILL:     search_knowledge_base()
├─ SKILL:     fetch_related_incidents()
├─ REASONER:  summarize_context()  ◄─── AI SYNTHESIS
└─ REASONER:  identify_service_owner()

DECISION & PLANNING (Mostly Reasoner)
├─ REASONER:  generate_resolution_plan()  ◄─── AI STRATEGY
├─ REASONER:  assess_risk_and_impact()  ◄─── AI ANALYSIS
└─ REASONER:  recommend_execution_path()

EXECUTION AGENT (Mostly Skills)
├─ SKILL:     execute_plan_steps()
├─ SKILL:     handle_execution_errors()
├─ SKILL:     provision_resources()
├─ SKILL:     log_execution_steps()
└─ SKILL:     log_execution_skipped()

VALIDATION & CLOSURE (Mixed)
├─ SKILL:     run_health_checks()
├─ SKILL:     request_user_confirmation()
├─ SKILL:     close_ticket_in_servicenow()
└─ REASONER:  evaluate_resolution_success()

COMMUNICATION AGENT (Skills)
├─ SKILL:     compose_resolution_message()
├─ SKILL:     send_email_notification()
├─ SKILL:     update_servicenow_ticket()
└─ SKILL:     send_team_notification()

LEARNING AGENT (Mostly Reasoner)
├─ REASONER:  analyze_resolution_effectiveness()
├─ REASONER:  extract_resolution_patterns()
├─ REASONER:  recommend_prompt_improvements()
├─ SKILL:     set_vector()  (Vector storage)
└─ SKILL:     similarity_search()  (Vector retrieval)
```

---

## Retry & Error Handling Flow

```
Execution Step Initiated
       │
       ▼
    Attempt 1
       │
    ┌──┴──┐
    │     │
   YES   NO (Failure)
    │     │
    ▼     ▼
  Success Attempt 2
           │
        ┌──┴──┐
        │     │
       YES   NO (Failure)
        │     │
        ▼     ▼
      Success Attempt 3
               │
            ┌──┴──┐
            │     │
           YES   NO (All failed)
            │     │
            ▼     ▼
          Success Execute Rollback
                   │
              ┌────┴────┐
              │          │
           Rollback   Rollback
           Succeeds   Fails
              │          │
              ▼          ▼
           Log         Escalate
        Rollback_      to Human
        Performed      Review
           │            │
           ▼            ▼
        End         Human
        Step        Decision
        │           │
        └─────┬─────┘
              │
              ▼
        Resume or
        Retry
```

---

## Vector Embedding Pipeline

```
Completed Resolution Record
       │
       ├─ ticket_id
       ├─ classification result
       ├─ enrichment data
       ├─ resolution plan
       ├─ execution log
       ├─ validation result
       ├─ success/failure status
       ├─ resolution_time_hours
       └─ user feedback
       │
       ▼
AI: Generate Embedding Vector
(Claude embedding model)
       │
       ├─ Semantic understanding
       ├─ Context captured
       ├─ Patterns encoded
       └─ Relationships embedded
       │
       ▼
Store Vector with Metadata
       │
    await app.memory.set_vector(
       ticket_id,
       embedding_vector,
       metadata={
           "ticket_type": classification.ticket_type,
           "category": classification.category,
           "resolution_time": hours,
           "success": True/False,
           "complexity": "simple|moderate|complex"
       }
    )
       │
       ▼
Knowledge Embeddings Database
       │
   ┌───┴────┬───────┬──────────┐
   │         │       │          │
  Ticket1  Ticket2 Ticket3  ...Ticketn

(Vector space organized by similarity)
       │
       ▼
Similarity Search (Future Tickets)
       │
    new_ticket → generate_embedding
                      │
                      ▼
                 similarity_search(
                    query_embedding,
                    top_k=5
                 )
                      │
           ┌──────────┼──────────┐
           │          │          │ (Top-K similar)
           ▼          ▼          ▼
        Result1    Result2    Result3
    Similarity:  Similarity: Similarity:
       0.92        0.87       0.81
       │           │          │
       └───────┬───┴──────────┘
               │
               ▼
        Use Similar Resolutions
        to Plan Current Ticket
```

---

## Escalation Decision Tree

```
                    Ticket Processed
                           │
              ┌────────────┬┴┬────────────┐
              │            │ │            │
         Ingestion      Classify     Enrich
              │            │ │            │
              ▼            ▼ ▼            ▼
           Parsed    ◇ confidence < 0.7?
                         │ │
                      NO │ │ YES
                         │ │
                         ▼ ▼
                      Proceed   ESCALATE
                         │      (Human 1)
                         │
                      Enriched
                         │
                      Plan Gen
                         │
              ◇ high_risk OR needs_approval?
                      │ │
                   NO │ │ YES
                      │ │
                      ▼ ▼
                   Proceed   ESCALATE
                      │      (Human 2)
                      │
                   Execute
                      │
              ◇ execution_success?
                      │ │
                   YES │ │ NO
                      │ │
                      ▼ ▼
                   Proceed   Rollback
                      │         │
                      │    ┌────┴────┐
                      │    │         │
                      │  Success  Failure
                      │    │         │
                      │    ▼         ▼
                   Validate    ESCALATE
                      │        (Human 3)
                      │
              ◇ validation_success?
                      │ │
                   YES │ │ NO
                      │ │
                      ▼ ▼
                 Close Ticket  ESCALATE
                      │        (Human 3)
                      │
                   Communicate
                      │
                      Learn
                      │
                  ╔═══╩════╗
                  ║ SUCCESS ║
                  ╚═════════╝
```

---

## Integration Touchpoints

```
┌──────────────────────────────────────────────────────────────┐
│ ServiceNow Instance                                          │
│ ├─ POST CURL → Ingestion Agent                             │
│ ├─ GET Table sc_task → Enrichment Agent (find related)     │
│ ├─ PATCH Work Notes → Communication Agent (update)         │
│ └─ PATCH Status → Communication Agent (close)              │
└───────────┬────────────────────────────────────────────────┘
            │
            │
┌───────────┴────────────────────────────────────────────────┐
│ AgentField Control Plane                                   │
│ ├─ Manages 9 agents                                        │
│ ├─ Routes between agents                                   │
│ ├─ Memory management                                       │
│ ├─ DAG execution tracking                                  │
│ └─ Webhook management                                      │
└───────────┬────────────────────────────────────────────────┘
            │
  ┌─────────┼─────────┬──────────┬──────────┬──────────┐
  │         │         │          │          │          │
  ▼         ▼         ▼          ▼          ▼          ▼
┌──────┐┌──────┐┌───────┐┌──────┐┌──────┐┌──────┐
│ User ││ KB   ││Asset  ││Notif ││Audit ││Logs  │
│ Dir  ││Sys   ││Mgmt   ││Sys   ││Log   ││      │
└──────┘└──────┘└───────┘└──────┘└──────┘└──────┘
```

---

## Configuration Topology

```
config.py
├─ AGENTFIELD_SERVER
├─ AI_MODEL
├─ SERVICENOW_INSTANCE
├─ SERVICENOW_API_KEY
├─ SERVICENOW_TABLE
├─ KNOWLEDGE_BASE_URL
├─ NOTIFICATION_WEBHOOK_URL
├─ RETRY_ATTEMPTS
├─ TIMEOUT_SECONDS
├─ HUMAN_REVIEW_QUEUE_URL
├─ CLASSIFICATION_CONFIDENCE_THRESHOLD ◄─ Affects Gate 1
├─ RISK_ESCALATION_THRESHOLD          ◄─ Affects Gate 2
├─ MAX_EXECUTION_RETRIES              ◄─ Affects Gate 3
└─ VECTOR_SIMILARITY_TOP_K            ◄─ Affects Learning
```

---

**Visual Reference Version**: 1.0  
**Last Updated**: 2025-03-18
