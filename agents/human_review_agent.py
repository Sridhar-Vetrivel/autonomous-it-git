"""
Human Review Agent — Phase 9 (Conditional)

Manages escalation to human analysts, queues tickets for review,
and resumes the pipeline once a human decision is recorded.
"""

from datetime import datetime, timezone
from typing import Dict

import aiohttp

from agentfield import Agent, AIConfig
from config import Config

app = Agent(
    node_id="human_review_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(
        model=Config.AI_MODEL,
        api_key=Config.OPENROUTER_API_KEY,
        base_url=Config.OPENROUTER_BASE_URL,
    ),
)

# Map of stage → next agent skill to resume after approval
_RESUME_MAP = {
    "classification": "enrichment_agent.enrich_ticket",
    "planning": "execution_agent.execute_plan",
    "validation": "communication_agent.notify_stakeholders",
    "execution": "validation_agent.validate_resolution",
}


# ── Skills ────────────────────────────────────────────────────────────────────

@app.skill()
async def queue_for_review(arguments: Dict) -> Dict:
    """
    Push a ticket into the human review queue and mark the session as pending.

    Input:  { "ticket_id": str, "stage": str }
    Output: { "queued": bool, "ticket_id": str, "stage": str }
    """
    ticket_id = arguments["ticket_id"]
    stage = arguments.get("stage", "unknown")
    reason = await app.memory.get("session", "human_review_reason") or "Escalated by agent"
    ticket = await app.memory.get("session", "current_ticket") or {}
    classification = await app.memory.get("session", "classification_result") or {}
    plan = await app.memory.get("session", "resolution_plan") or {}

    review_item = {
        "ticket_id": ticket_id,
        "stage": stage,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticket_summary": ticket.get("title", ""),
        "classification": classification,
        "plan": plan,
        "resume_skill": _RESUME_MAP.get(stage, ""),
    }

    # Persist in memory so it can be retrieved by the review UI
    queue: list = await app.memory.get("agent", "human_review_queue") or []
    queue.append(review_item)
    await app.memory.set("agent", "human_review_queue", queue)
    await app.memory.set("session", "human_review_item", review_item)

    # POST to the human review queue endpoint if configured
    if Config.HUMAN_REVIEW_QUEUE_URL:
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    Config.HUMAN_REVIEW_QUEUE_URL,
                    json=review_item,
                    timeout=aiohttp.ClientTimeout(total=10),
                )
        except Exception:
            pass  # Do not block the pipeline on notification failure

    return {"queued": True, "ticket_id": ticket_id, "stage": stage}


@app.skill()
async def record_human_decision(arguments: Dict) -> Dict:
    """
    Called by the review UI (via webhook) once the analyst has made a decision.

    Input: {
        "ticket_id": str,
        "decision": "approve" | "override" | "reject",
        "comments": str,
        "override_data": dict  (optional, for 'override' decisions)
    }
    """
    ticket_id = arguments["ticket_id"]
    decision = arguments["decision"]
    comments = arguments.get("comments", "")
    override_data = arguments.get("override_data", {})

    await app.memory.set("session", "human_decision", decision)
    await app.memory.set("session", "human_review_comments", comments)
    await app.memory.set("session", "requires_human_review", False)

    if override_data:
        # Merge override into the relevant memory key
        stage = (await app.memory.get("session", "human_review_item") or {}).get("stage", "")
        if stage == "classification" and "classification_result" in override_data:
            await app.memory.set("session", "classification_result", override_data["classification_result"])
        elif stage == "planning" and "resolution_plan" in override_data:
            await app.memory.set("session", "resolution_plan", override_data["resolution_plan"])

    result = {
        "ticket_id": ticket_id,
        "decision": decision,
        "comments": comments,
        "resumed": False,
    }

    if decision in ("approve", "override"):
        review_item = await app.memory.get("session", "human_review_item") or {}
        resume_skill = review_item.get("resume_skill", "")
        if resume_skill:
            await app.call(resume_skill, input={"ticket_id": ticket_id})
            result["resumed"] = True
    else:
        # Rejected — close without resolution
        await app.memory.set("session", "final_status", "rejected_by_human")

    return result


@app.skill()
async def get_pending_reviews(arguments: Dict) -> list:
    """Return all tickets currently waiting for human review."""
    return await app.memory.get("agent", "human_review_queue") or []


# ── Reasoners ─────────────────────────────────────────────────────────────────

@app.reasoner()
async def summarize_for_reviewer(arguments: Dict) -> Dict:
    """
    Generate a concise summary to help the analyst make a fast, informed decision.
    """
    ticket_id = arguments.get("ticket_id")
    ticket = await app.memory.get("session", "current_ticket") or {}
    classification = await app.memory.get("session", "classification_result") or {}
    plan = await app.memory.get("session", "resolution_plan") or {}
    reason = await app.memory.get("session", "human_review_reason") or ""

    response = await app.ai(
        system=(
            "You are an IT analyst assistant. Prepare a concise review brief. "
            "Return JSON: { summary: str (max 200 words), key_concerns: list, "
            "recommended_action: str, confidence_in_recommendation: float }"
        ),
        user=(
            f"Ticket: {ticket}\n"
            f"Classification: {classification}\n"
            f"Plan: {plan}\n"
            f"Escalation reason: {reason}"
        ),
    )
    return response
