"""
Communication Agent — Phase 7

Updates the ServiceNow ticket with work notes, notifies the requester,
and alerts the responsible team.
"""

from typing import Dict

from agentfield import Agent, AIConfig
from config import Config

app = Agent(
    node_id="communication_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(
        model=Config.AI_MODEL,
        api_key=Config.OPENROUTER_API_KEY,
        base_url=Config.OPENROUTER_BASE_URL,
    ),
)


# ── Skills ────────────────────────────────────────────────────────────────────

@app.skill()
async def notify_stakeholders(arguments: Dict) -> Dict:
    """
    Orchestrate all outbound communications for a resolved ticket.

    Input:  { "ticket_id": str }
    Output: summary of messages sent
    """
    ticket_id = arguments["ticket_id"]
    ticket = await app.memory.get("session", "current_ticket") or {}
    validation = await app.memory.get("session", "validation_result") or {}
    execution_log = await app.memory.get("run", "execution_log") or {}

    message = await compose_resolution_message(
        {
            "ticket": ticket,
            "validation": validation,
            "execution_log": execution_log,
        }
    )

    # Fire all notifications concurrently
    import asyncio

    requester_task = send_email_notification(
        {
            "recipient": ticket.get("requester_email", ""),
            "subject": f"[Resolved] {ticket.get('title', ticket_id)}",
            "body": message,
            "ticket_id": ticket_id,
        }
    )
    sn_task = update_servicenow_ticket(
        {
            "ticket_id": ticket_id,
            "work_notes": message,
            "state": "resolved",
        }
    )
    team_task = send_team_notification(
        {
            "team": (await app.memory.get("session", "enriched_ticket") or {}).get("service_owner_team", "IT Support"),
            "ticket_id": ticket_id,
            "summary": message[:500],
        }
    )

    requester_result, sn_result, team_result = await asyncio.gather(
        requester_task, sn_task, team_task, return_exceptions=True
    )

    sent_record = {
        "ticket_id": ticket_id,
        "requester_email": str(requester_result),
        "servicenow_update": str(sn_result),
        "team_notification": str(team_result),
        "message_preview": message[:200],
    }

    await app.memory.set("session", "communications_sent", sent_record)

    # Trigger Learning Agent
    await app.call("learning_agent.learn_from_resolution", input={"ticket_id": ticket_id})

    return sent_record


@app.skill()
async def update_servicenow_ticket(arguments: Dict) -> Dict:
    """Post work notes and update ticket state in ServiceNow."""
    from skills.servicenow_integration import update_ticket_status

    return await update_ticket_status(
        {
            "ticket_id": arguments["ticket_id"],
            "state": arguments.get("state", "resolved"),
            "work_notes": arguments.get("work_notes", ""),
        }
    )


@app.skill()
async def send_email_notification(arguments: Dict) -> Dict:
    """Send a resolution email to the ticket requester."""
    recipient = arguments.get("recipient", "")
    subject = arguments.get("subject", "")
    body = arguments.get("body", "")

    if not recipient:
        return {"sent": False, "reason": "No recipient"}

    # In production integrate with your email service (SendGrid, SES, etc.)
    # For now, log to agent memory as a notification record.
    templates: list = await app.memory.get("agent", "notification_templates") or []
    templates.append({"recipient": recipient, "subject": subject, "preview": body[:200]})
    await app.memory.set("agent", "notification_templates", templates)

    return {"sent": True, "recipient": recipient, "subject": subject}


@app.skill()
async def send_team_notification(arguments: Dict) -> Dict:
    """Alert the responsible team via webhook (Slack, Teams, etc.)."""
    team = arguments.get("team", "")
    ticket_id = arguments.get("ticket_id", "")
    summary = arguments.get("summary", "")

    if not Config.NOTIFICATION_WEBHOOK_URL:
        return {"sent": False, "reason": "No webhook configured"}

    import aiohttp

    payload = {"team": team, "ticket_id": ticket_id, "summary": summary}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                Config.NOTIFICATION_WEBHOOK_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return {"sent": resp.status < 300, "status_code": resp.status}
    except Exception as exc:
        return {"sent": False, "error": str(exc)}


# ── Reasoners ─────────────────────────────────────────────────────────────────

@app.reasoner()
async def compose_resolution_message(arguments: Dict) -> str:
    """
    AI-generated resolution summary message for stakeholders.
    """
    ticket = arguments.get("ticket", {})
    validation = arguments.get("validation", {})
    execution_log = arguments.get("execution_log", {})

    response = await app.ai(
        system=(
            "You are an IT communication specialist. Write a clear, professional "
            "resolution summary email body (plain text, max 300 words) that explains "
            "what was done to resolve the ticket. Be concise and user-friendly."
        ),
        user=(
            f"Ticket: {ticket.get('title')}\n"
            f"Description: {ticket.get('description')}\n"
            f"Execution status: {execution_log.get('overall_status')}\n"
            f"Validation: {validation.get('validation_notes')}\n\n"
            "Write the resolution email body."
        ),
    )
    # response is expected to be a plain string
    return response if isinstance(response, str) else str(response)
