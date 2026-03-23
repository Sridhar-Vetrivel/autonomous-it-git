"""
Learning Agent — Phase 8

Extracts resolution patterns, stores vector embeddings, and generates
recommendations to improve future agent performance.
"""

from typing import Dict

from agentfield import Agent, AIConfig
from config import Config

app = Agent(
    node_id="learning_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(
        model=Config.AI_MODEL,
        api_key=Config.OPENROUTER_API_KEY,
        base_url=Config.OPENROUTER_BASE_URL,
    ),
)


# ── Reasoners ─────────────────────────────────────────────────────────────────

@app.reasoner()
async def learn_from_resolution(arguments: Dict) -> Dict:
    """
    Full learning pipeline for a completed ticket.

    Input:  { "ticket_id": str }
    Output: dict with pattern and embedding keys stored
    """
    ticket_id = arguments["ticket_id"]

    ticket = await app.memory.get("session", "current_ticket") or {}
    classification = await app.memory.get("session", "classification_result") or {}
    enrichment = await app.memory.get("session", "enriched_ticket") or {}
    plan = await app.memory.get("session", "resolution_plan") or {}
    execution_log = await app.memory.get("run", "execution_log") or {}
    validation = await app.memory.get("session", "validation_result") or {}

    context = {
        "ticket": ticket,
        "classification": classification,
        "enrichment": enrichment,
        "plan": plan,
        "execution_log": execution_log,
        "validation": validation,
    }

    patterns = await extract_resolution_patterns(context)
    artifact = await generate_knowledge_artifact(context)
    improvements = await recommend_prompt_improvements(context)

    # Persist learned patterns per category
    existing: dict = await app.memory.get("agent", "learned_patterns") or {}
    category = classification.get("category", "general")
    cat_patterns: list = existing.get(category, [])
    cat_patterns.append(patterns)
    existing[category] = cat_patterns[-50:]  # Keep last 50 per category
    await app.memory.set("agent", "learned_patterns", existing)

    # Store vector embedding for future similarity search
    embedding_text = (
        f"{ticket.get('title', '')} {ticket.get('description', '')} "
        f"Resolution: {artifact.get('resolution_summary', '')}"
    )
    success = validation.get("all_checks_passed", False)
    resolution_time = execution_log.get("total_duration_seconds", 0) / 60

    await app.memory.set_vector(
        ticket_id,
        embedding_text,
        metadata={
            "category": category,
            "ticket_type": classification.get("ticket_type", ""),
            "status": "success" if success else "failed",
            "resolution_time_hours": round(resolution_time / 60, 2),
        },
    )

    # Store prompt improvement suggestions
    prompt_improvements: list = await app.memory.get("agent", "prompt_improvements") or []
    prompt_improvements.append(improvements)
    prompt_improvements = prompt_improvements[-20:]
    await app.memory.set("agent", "prompt_improvements", prompt_improvements)

    return {
        "ticket_id": ticket_id,
        "patterns_stored": True,
        "embedding_stored": True,
        "category": category,
    }


@app.reasoner()
async def extract_resolution_patterns(context: Dict) -> Dict:
    """
    Identify reusable patterns from a completed resolution.
    """
    response = await app.ai(
        system=(
            "You are an IT knowledge management expert. Analyse a completed ticket "
            "resolution and extract reusable patterns. Return JSON: "
            "{ pattern_name: str, trigger_conditions: list, resolution_steps: list, "
            "success_factors: list, estimated_time_minutes: int, confidence: float }"
        ),
        user=(
            f"Ticket: {context.get('ticket')}\n"
            f"Classification: {context.get('classification')}\n"
            f"Plan: {context.get('plan')}\n"
            f"Execution: {context.get('execution_log')}\n"
            f"Validation: {context.get('validation')}"
        ),
    )
    return response


@app.reasoner()
async def analyze_resolution_effectiveness(arguments: Dict) -> Dict:
    """
    Evaluate the quality and efficiency of a completed resolution.
    """
    context = arguments.get("context", {})

    response = await app.ai(
        system=(
            "You are an IT process analyst. Evaluate the resolution effectiveness. "
            "Return JSON: { effectiveness_score: float (0-1), "
            "time_efficiency: str (fast|normal|slow), "
            "quality_rating: str (excellent|good|acceptable|poor), "
            "improvement_areas: list }"
        ),
        user=f"Resolution context: {context}",
    )
    return response


@app.reasoner()
async def recommend_prompt_improvements(context: Dict) -> Dict:
    """
    Suggest improvements to agent prompts based on resolution outcome.
    """
    response = await app.ai(
        system=(
            "You are an AI prompt engineer for IT automation. Analyse this resolution "
            "and suggest improvements to agent prompts. Return JSON: "
            "{ agent_name: str, current_issue: str, suggested_improvement: str, "
            "expected_impact: str }"
        ),
        user=(
            f"Classification result: {context.get('classification')}\n"
            f"Plan outcome: {context.get('execution_log', {}).get('overall_status')}\n"
            f"Validation: {context.get('validation')}"
        ),
    )
    return response


@app.reasoner()
async def generate_knowledge_artifact(context: Dict) -> Dict:
    """
    Create a structured knowledge base entry from the resolution.
    """
    response = await app.ai(
        system=(
            "You are an IT knowledge base curator. Create a knowledge article from "
            "this ticket resolution. Return JSON: "
            "{ title: str, problem_description: str, resolution_summary: str, "
            "step_by_step: list, applicable_scenarios: list, keywords: list }"
        ),
        user=(
            f"Ticket: {context.get('ticket')}\n"
            f"Plan: {context.get('plan')}\n"
            f"Execution: {context.get('execution_log')}"
        ),
    )
    return response
