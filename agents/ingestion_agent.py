"""
Ingestion Agent — Phase 1

Parses incoming ServiceNow tickets, normalizes fields, and stores the result
in session memory before handing off to the Classification Agent.
"""

import asyncio
from typing import Dict, List
from datetime import datetime

from agentfield import Agent, AIConfig
from schemas.ticket import TicketData, NormalizedTicket
from config import Config

app = Agent(
    node_id="ingestion_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(model=Config.AI_MODEL),
)


# ── Skills (deterministic) ────────────────────────────────────────────────────

@app.skill()
async def batch_ticket_from_servicenow(arguments: Dict) -> Dict:
    """
    Parse and validate an incoming ServiceNow ticket payload.

    Input:  { "ticket_payload": { ...ServiceNow JSON... } }
    Output: TicketData dict
    """
    payload = arguments.get("ticket_payload", {})

    try:
        ticket = TicketData(
            number=payload["number"],
            short_description=payload["short_description"],
            description=payload.get("description"),
            requested_for=payload["requested_for"],
            requested_item=payload.get("requested_item", ""),
            priority=payload.get("priority", "medium").lower(),
            state=payload.get("state", "new"),
            assignment_group=payload.get("assignment_group"),
            assigned_to=payload.get("assigned_to"),
            opened=payload["opened"],
            updated=payload["updated"],
            opened_by=payload["opened_by"],
            work_notes=payload.get("work_notes"),
            attachments=payload.get("attachments", []),
        )
        return ticket.model_dump()
    except Exception as e:
        raise ValueError(f"Failed to parse ServiceNow ticket: {e}")


@app.skill()
async def normalize_ticket_fields(arguments: Dict) -> Dict:
    """
    Map ServiceNow fields to the internal NormalizedTicket schema.

    Input:  { "ticket_data": { ...TicketData dict... } }
    Output: NormalizedTicket dict
    """
    td = arguments.get("ticket_data", {})

    priority_map = {
        "critical": "critical",
        "1": "critical",
        "high": "high",
        "2": "high",
        "medium": "medium",
        "3": "medium",
        "low": "low",
        "4": "low",
    }
    priority = priority_map.get(td.get("priority", "medium").lower(), "medium")

    urgency_map = {"critical": "immediate", "high": "urgent", "medium": "normal", "low": "low"}
    urgency = urgency_map.get(priority, "normal")
    impact = "high" if priority in ("critical", "high") else "medium" if priority == "medium" else "low"

    opened_str = td.get("opened", datetime.utcnow().isoformat())
    # Tolerate both "Z" suffix and "+00:00"
    opened_str = opened_str.replace("Z", "+00:00")

    normalized = NormalizedTicket(
        ticket_id=td["number"],
        title=td["short_description"],
        description=td.get("description") or "",
        requester_email=td["requested_for"],
        requester_name=None,
        service_type=_categorize_service_type(td.get("requested_item", "")),
        priority=priority,
        urgency=urgency,
        impact=impact,
        received_at=datetime.fromisoformat(opened_str),
        metadata={
            "servicenow_id": td["number"],
            "assignment_group": td.get("assignment_group"),
            "work_notes": td.get("work_notes"),
        },
    )
    return normalized.model_dump(mode="json")


@app.skill()
async def extract_attachments(arguments: Dict) -> Dict:
    """Extract attachment metadata from the ticket."""
    td = arguments.get("ticket_data", {})
    attachments = td.get("attachments", [])
    return {
        "ticket_id": td.get("number"),
        "attachment_count": len(attachments),
        "attachments": attachments,
    }


@app.skill()
async def store_to_memory(arguments: Dict) -> Dict:
    """Persist normalized ticket in session memory."""
    ticket_id = arguments["ticket_id"]
    normalized_ticket = arguments["normalized_ticket"]

    await app.memory.set("session", "current_ticket", normalized_ticket)

    history: List[str] = await app.memory.get("session", "ticket_history") or []
    if not isinstance(history, list):
        history = []
    if ticket_id not in history:
        history.append(ticket_id)
    await app.memory.set("session", "ticket_history", history)

    return {"status": "stored", "ticket_id": ticket_id, "memory_key": "session.current_ticket"}


# ── Reasoner (non-deterministic) ──────────────────────────────────────────────

@app.reasoner()
async def parse_ticket_content(arguments: Dict) -> Dict:
    """
    Use AI to validate edge cases and surface data-quality issues in a ticket.
    """
    td = arguments.get("ticket_data", {})

    response = await app.ai(
        system=(
            "You are an IT ticket validation expert. Analyse the ticket for "
            "missing required fields, inconsistencies, or data quality issues. "
            "Return a JSON object with keys: is_valid (bool), issues (list of "
            "strings), recommendations (list of strings)."
        ),
        user=(
            f"Ticket number: {td.get('number')}\n"
            f"Title: {td.get('short_description')}\n"
            f"Description: {td.get('description')}\n"
            f"Requester: {td.get('requested_for')}\n"
            f"Priority: {td.get('priority')}\n\n"
            "Identify any issues and provide recommendations."
        ),
    )
    return response


# ── Helpers ───────────────────────────────────────────────────────────────────

def _categorize_service_type(requested_item: str) -> str:
    item = requested_item.lower()
    if any(k in item for k in ("vpn", "network", "internet", "wifi")):
        return "vpn"
    if any(k in item for k in ("software", "license", "application", "app")):
        return "software"
    if any(k in item for k in ("hardware", "laptop", "printer", "monitor", "mouse")):
        return "hardware"
    if any(k in item for k in ("access", "permission", "role", "group")):
        return "access"
    return "general"


# ── Orchestrator ──────────────────────────────────────────────────────────────

async def process_incoming_ticket(ticket_payload: Dict) -> Dict:
    """
    Main ingestion flow: parse → normalize → store → hand off to classification.
    """
    try:
        # 1. Parse
        ticket_data = await batch_ticket_from_servicenow({"ticket_payload": ticket_payload})

        # 2. Normalize
        normalized = await normalize_ticket_fields({"ticket_data": ticket_data})

        # 3. Attachments
        await extract_attachments({"ticket_data": ticket_data})

        # 4. Store in memory
        await store_to_memory({"ticket_id": ticket_data["number"], "normalized_ticket": normalized})

        # 5. Trigger classification
        await app.call(
            "classification_agent.classify_ticket_type",
            input={"ticket_id": ticket_data["number"]},
        )

        return {
            "status": "success",
            "ticket_id": ticket_data["number"],
            "ingestion_status": "complete",
            "next_step": "classification_agent",
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "next_step": "error_handling"}


if __name__ == "__main__":
    sample = {
        "number": "SCTASK0802841",
        "short_description": "VPN Access Required",
        "description": "User needs VPN access for remote work",
        "requested_for": "john.doe@company.com",
        "requested_item": "VPN License",
        "priority": "high",
        "state": "new",
        "assignment_group": "IT Support",
        "opened": "2025-03-18T09:00:00Z",
        "updated": "2025-03-18T09:00:00Z",
        "opened_by": "admin",
    }
    result = asyncio.run(process_incoming_ticket(sample))
    print(result)
