"""
Execution Agent — Phase 5

Runs the resolution plan step by step with retry/backoff and rollback support.
All actions are logged to run-scoped memory.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List

from agentfield import Agent, AIConfig
from schemas.execution import ExecutionLog, ExecutionStepResult
from schemas.planning import ResolutionPlan
from config import Config
from shared.decorators import handle_errors, track_performance

app = Agent(
    node_id="execution_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(model=Config.AI_MODEL),
)


# ── Skills ────────────────────────────────────────────────────────────────────

@app.skill()
@handle_errors("execute_plan")
@track_performance("execute_plan")
async def execute_plan(arguments: Dict) -> Dict:
    """
    Execute every step in the resolution plan, logging results to run memory.

    Input:  { "ticket_id": str }
    Output: ExecutionLog dict
    """
    ticket_id = arguments["ticket_id"]
    print(f"\n{'='*60}")
    print(f"[EXECUTION] *** PHASE 5: PLAN EXECUTION ***")
    print(f"[EXECUTION] Executing plan for ticket: {ticket_id}")
    plan_raw = await app.memory.get("session", "resolution_plan")

    if not plan_raw:
        print(f"[EXECUTION] ERROR: No resolution plan found for ticket {ticket_id}")
        raise ValueError(f"No resolution plan found for ticket {ticket_id}")

    plan = ResolutionPlan.model_validate(plan_raw)
    execution_id = f"EXEC-{uuid.uuid4().hex[:8].upper()}"
    print(f"[EXECUTION] execution_id={execution_id}, plan_id={plan.plan_id}, steps={len(plan.steps)}")
    started_at = datetime.now(timezone.utc)
    step_results: List[ExecutionStepResult] = []
    rollback_performed = False

    for step in plan.steps:
        print(f"[EXECUTION] Running step {step.step_id}: {step.action}...")
        step_result = await _run_step_with_retry(step.model_dump(), execution_id)
        step_results.append(step_result)
        print(f"[EXECUTION] Step {step.step_id} result: status={step_result.status}, retries={step_result.retry_count}, duration={step_result.duration_seconds:.2f}s")

        if step_result.status == "failure" and not step.skip_on_error:
            # Attempt rollback and abort
            print(f"[EXECUTION] Step {step.step_id} FAILED and skip_on_error=False — initiating rollback...")
            rollback_performed = await _attempt_rollback(plan_raw, step_results)
            print(f"[EXECUTION] Rollback performed: {rollback_performed}")
            break

    completed_at = datetime.now(timezone.utc)
    overall = _compute_overall_status(step_results, rollback_performed)

    log = ExecutionLog(
        ticket_id=ticket_id,
        plan_id=plan.plan_id,
        execution_id=execution_id,
        started_at=started_at,
        completed_at=completed_at,
        overall_status=overall,
        step_results=step_results,
        total_duration_seconds=(completed_at - started_at).total_seconds(),
        rollback_performed=rollback_performed,
    )

    log_dict = log.model_dump(mode="json")
    await app.memory.set("run", "execution_log", log_dict)
    await app.memory.set("run", "step_results", [s.model_dump(mode="json") for s in step_results])

    passed = sum(1 for s in step_results if s.status == "success")
    failed = sum(1 for s in step_results if s.status == "failure")
    print(f"[EXECUTION] Completed: overall={overall}, steps_passed={passed}, steps_failed={failed}, duration={log.total_duration_seconds:.2f}s")
    print(f"[EXECUTION] Handing off to validation_agent for ticket {ticket_id}")
    print(f"{'='*60}\n")

    # Forward to Validation
    await app.call(
        "validation_agent.validate_resolution",
        input={"ticket_id": ticket_id, "execution_id": execution_id},
    )

    return log_dict


@app.skill()
@handle_errors("provision_resources")
async def provision_resources(arguments: Dict) -> Dict:
    """
    Generic resource provisioning skill (VPN, software licence, access grant, etc.).
    In production, delegate to the appropriate back-end API.
    """
    action = arguments.get("action", "")
    parameters = arguments.get("parameters", {})
    ticket_id = arguments.get("ticket_id", "")

    # Placeholder — real implementation calls ServiceNow / provisioning APIs
    return {
        "ticket_id": ticket_id,
        "action": action,
        "status": "provisioned",
        "parameters": parameters,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.skill()
async def log_execution_skipped(arguments: Dict) -> Dict:
    """Record a step that was intentionally skipped."""
    step_id = arguments.get("step_id")
    reason = arguments.get("reason", "skip_on_error flag set")
    errors: List[Dict] = await app.memory.get("run", "errors") or []
    errors.append({"step_id": step_id, "skipped": True, "reason": reason})
    await app.memory.set("run", "errors", errors)
    return {"step_id": step_id, "skipped": True}


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _run_step_with_retry(step: Dict, execution_id: str) -> ExecutionStepResult:
    """Execute a single plan step with exponential backoff retry."""
    max_attempts = Config.MAX_EXECUTION_RETRIES
    start = datetime.now(timezone.utc)
    last_error: str = ""
    retry_count = 0

    for attempt in range(max_attempts):
        if attempt > 0:
            print(f"[EXECUTION] Retrying step {step.get('step_id')} (attempt {attempt+1}/{max_attempts}, backoff={2**( attempt-1)}s)...")
        try:
            # Dispatch to the appropriate skill/tool
            output = await _dispatch_step(step)
            end = datetime.now(timezone.utc)
            return ExecutionStepResult(
                step_id=step["step_id"],
                status="success",
                start_time=start,
                end_time=end,
                duration_seconds=(end - start).total_seconds(),
                output=output,
                retry_count=retry_count,
            )
        except Exception as exc:
            last_error = str(exc)
            retry_count = attempt + 1
            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # 1 s, 2 s, 4 s

    end = datetime.now(timezone.utc)
    return ExecutionStepResult(
        step_id=step["step_id"],
        status="failure",
        start_time=start,
        end_time=end,
        duration_seconds=(end - start).total_seconds(),
        error_message=last_error,
        error_type="MaxRetriesExceeded",
        retry_count=retry_count,
    )


async def _dispatch_step(step: Dict) -> Dict:
    """Route a plan step to the correct skill."""
    skill = step.get("skill_or_tool", "")
    params = step.get("parameters", {})

    # For now every step is treated as a resource provisioning call.
    # Extend this mapping as real skills are added.
    return await provision_resources(
        {"action": step.get("action"), "parameters": params}
    )


async def _attempt_rollback(plan_raw: Dict, completed_steps: List[ExecutionStepResult]) -> bool:
    """Execute rollback instructions for completed steps in reverse order."""
    try:
        plan = ResolutionPlan.model_validate(plan_raw)
        completed_ids = {r.step_id for r in completed_steps if r.status == "success"}
        for step in reversed(plan.steps):
            if step.step_id in completed_ids and step.rollback_instruction:
                await _dispatch_step(
                    {
                        "step_id": step.step_id,
                        "action": step.rollback_instruction,
                        "skill_or_tool": step.skill_or_tool,
                        "parameters": step.parameters,
                    }
                )
        return True
    except Exception:
        return False


def _compute_overall_status(steps: List[ExecutionStepResult], rollback: bool) -> str:
    if rollback:
        return "failure"
    statuses = {s.status for s in steps}
    if statuses == {"success"}:
        return "success"
    if "failure" in statuses:
        return "partial_failure"
    return "success"
