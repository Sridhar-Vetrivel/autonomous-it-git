"""
Classification Agent — Phase 2

Uses AI to categorise the ticket by type, category, priority, and severity.
If confidence falls below the threshold the ticket is flagged for human review.
"""

from typing import Dict

from agentfield import Agent, AIConfig
from schemas.classification import ClassificationResult
from config import Config
from shared.decorators import handle_errors, track_slow_operation

app = Agent(
    node_id="classification_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(model=Config.AI_MODEL),
)


# ── Reasoners ─────────────────────────────────────────────────────────────────

@app.reasoner()
@handle_errors("classify_ticket_type")
@track_slow_operation("classify_ticket_type", warn_seconds=8.0, critical_seconds=20.0)
async def classify_ticket_type(arguments: Dict) -> Dict:
    """
    AI-driven ticket classification.

    Input:  { "ticket_id": str }
    Output: ClassificationResult dict (stored in session memory)
    """
    ticket_id = arguments.get("ticket_id")
    print(f"\n{'='*60}")
    print(f"[CLASSIFICATION] *** PHASE 2: TICKET CLASSIFICATION ***")
    print(f"[CLASSIFICATION] Classifying ticket: {ticket_id}")
    ticket = await app.memory.get("session", "current_ticket")

    if not ticket:
        print(f"[CLASSIFICATION] ERROR: Ticket {ticket_id} not found in session memory")
        raise ValueError(f"Ticket {ticket_id} not found in session memory")

    print(f"[CLASSIFICATION] Ticket loaded: '{ticket.get('title')}' (service_type={ticket.get('service_type')})")
    print(f"[CLASSIFICATION] Calling AI to classify...")
    response: ClassificationResult = await app.ai(
        system=(
            "You are an IT ticket classification expert. Analyse tickets and return "
            "a structured JSON classification with these fields:\n"
            "  ticket_id, ticket_type (incident|request|change|problem), "
            "category (vpn_access|software_install|hardware_request|access_management|"
            "network_issue|other), sub_category (optional), "
            "priority (critical|high|medium|low), severity (1|2|3|4), "
            "confidence_score (0.0-1.0), reasoning (max 1000 chars), "
            "requires_human_review (bool), suggested_assignment_group (optional), "
            "tags (list of strings).\n\n"
            "Be conservative: lower confidence_score when unsure."
        ),
        user=(
            f"Classify this ticket:\n\n"
            f"ID: {ticket.get('ticket_id')}\n"
            f"Title: {ticket.get('title')}\n"
            f"Description: {ticket.get('description')}\n"
            f"Service Type: {ticket.get('service_type')}\n"
            f"Priority: {ticket.get('priority')}\n"
            f"Urgency: {ticket.get('urgency')}\n\n"
            "Provide a JSON classification."
        ),
        schema=ClassificationResult,
    )

    result_dict = response.model_dump()
    print(f"[CLASSIFICATION] AI result: type={result_dict.get('ticket_type')}, category={result_dict.get('category')}, priority={result_dict.get('priority')}, confidence={result_dict.get('confidence_score', 0):.2f}")

    # Enforce threshold
    if response.confidence_score < Config.CLASSIFICATION_CONFIDENCE_THRESHOLD:
        result_dict["requires_human_review"] = True
        print(f"[CLASSIFICATION] Confidence {response.confidence_score:.2f} below threshold {Config.CLASSIFICATION_CONFIDENCE_THRESHOLD} — flagging for human review")
        await app.memory.set(
            "session",
            "human_review_reason",
            f"Low classification confidence: {response.confidence_score:.2f}",
        )
        await app.memory.set("session", "requires_human_review", True)
    else:
        print(f"[CLASSIFICATION] Confidence OK ({response.confidence_score:.2f} >= {Config.CLASSIFICATION_CONFIDENCE_THRESHOLD})")

    await app.memory.set("session", "classification_result", result_dict)

    if result_dict["requires_human_review"]:
        print(f"[CLASSIFICATION] Escalating to human_review_agent (stage=classification)")
        print(f"{'='*60}\n")
        await app.call(
            "human_review_agent.queue_for_review",
            input={"ticket_id": ticket_id, "stage": "classification"},
        )
    else:
        print(f"[CLASSIFICATION] Handing off to enrichment_agent for ticket {ticket_id}")
        print(f"{'='*60}\n")
        await app.call(
            "enrichment_agent.enrich_ticket",
            input={"ticket_id": ticket_id},
        )

    return result_dict


@app.reasoner()
@handle_errors("assess_priority_and_severity")
@track_slow_operation("assess_priority_and_severity", warn_seconds=5.0, critical_seconds=15.0)
async def assess_priority_and_severity(arguments: Dict) -> Dict:
    """
    Re-evaluate priority and severity when flagged by another agent.
    """
    ticket_id = arguments.get("ticket_id")
    ticket = await app.memory.get("session", "current_ticket")
    classification = await app.memory.get("session", "classification_result") or {}

    response = await app.ai(
        system=(
            "You are an IT priority assessment expert. Given ticket details and an "
            "existing classification, re-evaluate priority (critical|high|medium|low) "
            "and severity (1|2|3|4). Return JSON with: priority, severity, reasoning."
        ),
        user=(
            f"Ticket: {ticket}\n"
            f"Existing classification: {classification}\n\n"
            "Re-assess priority and severity."
        ),
    )

    classification.update(response)
    await app.memory.set("session", "classification_result", classification)
    return classification


# ── Skills ────────────────────────────────────────────────────────────────────

@app.skill()
@handle_errors("escalate_to_human_review")
async def escalate_to_human_review(arguments: Dict) -> Dict:
    """Flag ticket for human review due to low confidence."""
    ticket_id = arguments.get("ticket_id")
    reason = arguments.get("reason", "Low confidence classification")

    await app.memory.set("session", "requires_human_review", True)
    await app.memory.set("session", "human_review_reason", reason)

    return {"ticket_id": ticket_id, "escalated": True, "reason": reason}
