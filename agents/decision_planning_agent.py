"""
Decision & Planning Agent — Phase 4

Uses AI to generate a step-by-step resolution plan including risk assessment.
High-risk or approval-required plans are escalated to human review.
"""

import uuid
from typing import Dict

from agentfield import Agent, AIConfig
from schemas.planning import ResolutionPlan
from config import Config

app = Agent(
    node_id="decision_planning_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(
        model=Config.AI_MODEL,
        api_key=Config.OPENROUTER_API_KEY,
        base_url=Config.OPENROUTER_BASE_URL,
    ),
)


# ── Reasoners ─────────────────────────────────────────────────────────────────

@app.reasoner()
async def generate_resolution_plan(arguments: Dict) -> Dict:
    """
    Generate a full resolution plan from enriched ticket context.

    Input:  { "ticket_id": str }
    Output: ResolutionPlan dict (stored in session memory)
    """
    ticket_id = arguments["ticket_id"]
    ticket = await app.memory.get("session", "current_ticket")
    classification = await app.memory.get("session", "classification_result")
    enrichment = await app.memory.get("session", "enriched_ticket")

    if not ticket or not classification:
        raise ValueError(f"Missing context for ticket {ticket_id}")

    plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"

    response: ResolutionPlan = await app.ai(
        system=(
            "You are an IT resolution planning expert. Create a detailed, step-by-step "
            "resolution plan. Return a JSON ResolutionPlan with:\n"
            "  ticket_id, plan_id (use the provided value), steps (list of ExecutionStep), "
            "total_estimated_minutes, risk_level (low|medium|high), risk_description, "
            "requires_approval (bool), approval_justification (optional), "
            "rollback_procedure, success_criteria (list), dependencies (list), "
            "alternative_approaches (int).\n\n"
            "Each ExecutionStep: step_id (int), action, skill_or_tool, parameters (dict), "
            "expected_duration_minutes, required_permissions (list), rollback_instruction, "
            "skip_on_error (bool).\n\n"
            f"plan_id to use: {plan_id}"
        ),
        user=(
            f"Ticket: {ticket}\n"
            f"Classification: {classification}\n"
            f"Enrichment: {enrichment}\n\n"
            "Produce a concrete, actionable resolution plan."
        ),
        schema=ResolutionPlan,
    )

    plan_dict = response.model_dump()
    await app.memory.set("session", "resolution_plan", plan_dict)
    await app.memory.set("session", "decision_reasoning", plan_dict.get("risk_description", ""))

    # Escalate if high risk or requires approval
    if (
        response.risk_level == "high"
        or response.requires_approval
    ):
        await app.memory.set("session", "requires_human_review", True)
        await app.memory.set(
            "run",
            "approvals_required",
            [response.approval_justification or "High-risk plan requires approval"],
        )
        await app.call(
            "human_review_agent.queue_for_review",
            input={"ticket_id": ticket_id, "stage": "planning"},
        )
    else:
        await app.call(
            "execution_agent.execute_plan",
            input={"ticket_id": ticket_id},
        )

    return plan_dict


@app.reasoner()
async def assess_risk_and_impact(arguments: Dict) -> Dict:
    """
    Stand-alone risk assessment called when a plan needs re-evaluation.
    """
    plan = arguments.get("plan", {})
    ticket = arguments.get("ticket", {})

    response = await app.ai(
        system=(
            "You are an IT risk assessment expert. Evaluate the resolution plan and "
            "return JSON: { risk_level: low|medium|high, risk_score: float 0-1, "
            "risk_factors: list, mitigation_strategies: list }"
        ),
        user=f"Plan: {plan}\nTicket: {ticket}",
    )
    return response


@app.reasoner()
async def recommend_execution_path(arguments: Dict) -> Dict:
    """
    Given multiple resolution options, recommend the optimal path.
    """
    options = arguments.get("options", [])
    ticket = arguments.get("ticket", {})
    enrichment = arguments.get("enrichment", {})

    response = await app.ai(
        system=(
            "You are an IT execution strategy expert. Given resolution options, "
            "recommend the best approach. Return JSON: "
            "{ recommended_option_index: int, reasoning: str, estimated_success_rate: float }"
        ),
        user=f"Options: {options}\nTicket: {ticket}\nEnrichment: {enrichment}",
    )
    return response
