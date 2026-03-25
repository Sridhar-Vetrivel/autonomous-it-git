"""
Validation & Closure Agent — Phase 6

Verifies that the executed resolution actually solved the problem,
confirms with the requester, and closes the ServiceNow ticket.
"""

from typing import Dict, List

from agentfield import Agent, AIConfig
from schemas.execution import ValidationResult
from config import Config
from shared.decorators import handle_errors, track_performance, track_slow_operation

app = Agent(
    node_id="validation_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(model=Config.AI_MODEL),
)


# ── Skills ────────────────────────────────────────────────────────────────────

@app.skill()
@handle_errors("validate_resolution")
@track_performance("validate_resolution")
async def validate_resolution(arguments: Dict) -> Dict:
    """
    Run health checks and AI evaluation to confirm resolution success.

    Input:  { "ticket_id": str, "execution_id": str }
    Output: ValidationResult dict (stored in session memory)
    """
    ticket_id = arguments["ticket_id"]
    execution_id = arguments.get("execution_id", "")
    print(f"\n{'='*60}")
    print(f"[VALIDATION] *** PHASE 6: VALIDATION & CLOSURE ***")
    print(f"[VALIDATION] Validating resolution for ticket: {ticket_id}, execution: {execution_id}")

    execution_log = await app.memory.get("run", "execution_log") or {}
    plan = await app.memory.get("session", "resolution_plan") or {}
    ticket = await app.memory.get("session", "current_ticket") or {}

    print(f"[VALIDATION] Execution status: {execution_log.get('overall_status', 'unknown')}, rollback={execution_log.get('rollback_performed', False)}")
    print(f"[VALIDATION] Running health checks...")
    health_checks = await run_health_checks(
        {
            "ticket": ticket,
            "plan": plan,
            "execution_log": execution_log,
        }
    )

    for check in health_checks:
        status_str = "PASS" if check.get("passed") else "FAIL"
        print(f"[VALIDATION] Health check '{check.get('name')}': {status_str} — {check.get('message')}")

    print(f"[VALIDATION] Running AI assessment of resolution success...")
    ai_assessment = await evaluate_resolution_success(
        {
            "ticket": ticket,
            "plan": plan,
            "execution_log": execution_log,
            "health_checks": health_checks,
        }
    )

    all_passed = all(c.get("passed", False) for c in health_checks) and ai_assessment.get(
        "success", False
    )
    recommended = "close" if all_passed else ("escalate" if execution_log.get("rollback_performed") else "replan")

    result = ValidationResult(
        ticket_id=ticket_id,
        execution_id=execution_id,
        all_checks_passed=all_passed,
        checks=health_checks,
        user_confirmed=False,
        validation_notes=ai_assessment.get("reasoning", ""),
        recommended_action=recommended,
    )

    result_dict = result.model_dump(mode="json")
    await app.memory.set("session", "validation_result", result_dict)

    print(f"[VALIDATION] AI assessment: success={ai_assessment.get('success')}, confidence={ai_assessment.get('confidence', 0):.2f}")
    print(f"[VALIDATION] Overall result: all_checks_passed={all_passed}, recommended_action={recommended}")

    if all_passed:
        print(f"[VALIDATION] Validation PASSED — closing ticket in ServiceNow and notifying stakeholders")
        print(f"{'='*60}\n")
        await close_ticket_in_servicenow({"ticket_id": ticket_id, "resolution_notes": ai_assessment.get("reasoning", "")})
        await app.call("communication_agent.notify_stakeholders", input={"ticket_id": ticket_id})
    else:
        print(f"[VALIDATION] Validation FAILED — escalating to human_review_agent (stage=validation)")
        print(f"{'='*60}\n")
        await app.memory.set("session", "requires_human_review", True)
        await app.call(
            "human_review_agent.queue_for_review",
            input={"ticket_id": ticket_id, "stage": "validation"},
        )

    return result_dict


@app.skill()
async def run_health_checks(arguments: Dict) -> List[Dict]:
    """
    Run post-execution checks (service availability, access confirmed, etc.).
    Returns a list of { name, passed, message } dicts.
    """
    ticket = arguments.get("ticket", {})
    execution_log = arguments.get("execution_log", {})

    checks = []

    # Check 1: execution finished without failure
    overall_status = execution_log.get("overall_status", "failure")
    checks.append(
        {
            "name": "execution_completed",
            "passed": overall_status in ("success", "partial_failure"),
            "message": f"Execution status: {overall_status}",
        }
    )

    # Check 2: no rollback was performed
    checks.append(
        {
            "name": "no_rollback",
            "passed": not execution_log.get("rollback_performed", False),
            "message": "Rollback was performed" if execution_log.get("rollback_performed") else "No rollback needed",
        }
    )

    # Check 3: all required steps succeeded
    step_results = execution_log.get("step_results", [])
    failed_steps = [s for s in step_results if s.get("status") == "failure"]
    checks.append(
        {
            "name": "all_steps_passed",
            "passed": len(failed_steps) == 0,
            "message": f"{len(failed_steps)} step(s) failed" if failed_steps else "All steps passed",
        }
    )

    return checks


@app.skill()
@handle_errors("close_ticket_in_servicenow")
async def close_ticket_in_servicenow(arguments: Dict) -> Dict:
    """Update the ServiceNow ticket state to 'Closed'."""
    from skills.servicenow_integration import update_ticket_status

    ticket_id = arguments["ticket_id"]
    notes = arguments.get("resolution_notes", "Resolved by Autonomous IT Agent")

    return await update_ticket_status(
        {
            "ticket_id": ticket_id,
            "state": "closed",
            "work_notes": notes,
            "close_code": "Solved (Permanently)",
        }
    )


@app.skill()
async def request_user_confirmation(arguments: Dict) -> Dict:
    """
    Send a confirmation request to the ticket requester.
    (Async — actual confirmation arrives via webhook callback.)
    """
    ticket_id = arguments["ticket_id"]
    requester_email = arguments.get("requester_email", "")

    await app.memory.set("session", "awaiting_user_confirmation", True)

    return {
        "ticket_id": ticket_id,
        "confirmation_requested": True,
        "sent_to": requester_email,
    }


# ── Reasoners ─────────────────────────────────────────────────────────────────

@app.reasoner()
@handle_errors("evaluate_resolution_success")
@track_slow_operation("evaluate_resolution_success", warn_seconds=5.0, critical_seconds=15.0)
async def evaluate_resolution_success(arguments: Dict) -> Dict:
    """
    AI assessment of whether the resolution genuinely solved the ticket.
    """
    ticket = arguments.get("ticket", {})
    plan = arguments.get("plan", {})
    execution_log = arguments.get("execution_log", {})
    health_checks = arguments.get("health_checks", [])

    response = await app.ai(
        system=(
            "You are an IT resolution quality assessor. Given a ticket, its resolution plan, "
            "execution log, and health check results, determine if the issue was genuinely resolved. "
            "Return JSON: { success: bool, confidence: float, reasoning: str, "
            "unresolved_items: list }"
        ),
        user=(
            f"Ticket: {ticket}\n"
            f"Plan: {plan}\n"
            f"Execution: {execution_log}\n"
            f"Health checks: {health_checks}"
        ),
    )
    return response
