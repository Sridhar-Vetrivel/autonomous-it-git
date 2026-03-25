"""
Ingestion Agent — Phase 1

Parses incoming ServiceNow tickets, normalizes fields, and stores the result
in session memory before handing off to the Classification Agent.
"""

import asyncio
import json
from typing import Dict, List
from datetime import datetime

from agentfield import Agent, AIConfig
from schemas.ticket import TicketData, NormalizedTicket
from config import Config
from shared.decorators import handle_errors, track_performance

app = Agent(
    node_id="ingestion_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(model=Config.AI_MODEL),
)


# ── Skills (deterministic) ────────────────────────────────────────────────────

@app.skill()
@handle_errors("batch_ticket_from_servicenow")
async def batch_ticket_from_servicenow(arguments: Dict) -> Dict:
    """
    Parse and validate an incoming ServiceNow ticket payload.

    Input:  { "ticket_payload": { ...ServiceNow JSON... } }
    Output: TicketData dict
    """
    payload = arguments.get("ticket_payload", {})
    print(f"\n[INGESTION] Received ticket payload: number={payload.get('number')}, description='{payload.get('short_description')}'")

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
        print(f"[INGESTION] Ticket parsed: id={ticket.number}, priority={ticket.priority}, requester={ticket.requested_for}")
        return ticket.model_dump()
    except Exception as e:
        print(f"[INGESTION] ERROR parsing ticket: {e}")
        raise ValueError(f"Failed to parse ServiceNow ticket: {e}")


@app.skill()
@handle_errors("normalize_ticket_fields")
async def normalize_ticket_fields(arguments: Dict) -> Dict:
    """
    Map ServiceNow fields to the internal NormalizedTicket schema.

    Input:  { "ticket_data": { ...TicketData dict... } }
    Output: NormalizedTicket dict
    """
    td = arguments.get("ticket_data", {})
    print(f"[INGESTION] Normalizing fields for ticket: {td.get('number')}")

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
    print(f"[INGESTION] Normalized: ticket_id={normalized.ticket_id}, service_type={normalized.service_type}, priority={normalized.priority}, urgency={normalized.urgency}")
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
@handle_errors("store_to_memory")
async def store_to_memory(arguments: Dict) -> Dict:
    """Persist normalized ticket in session memory."""
    ticket_id = arguments["ticket_id"]
    normalized_ticket = arguments["normalized_ticket"]

    await app.memory.set("current_ticket", normalized_ticket)

    history: List[str] = await app.memory.get("ticket_history") or []
    if not isinstance(history, list):
        history = []
    if ticket_id not in history:
        history.append(ticket_id)
    await app.memory.set("ticket_history", history)
    print(f"[INGESTION] Stored ticket {ticket_id} in session memory (history size: {len(history)})")

    return {"status": "stored", "ticket_id": ticket_id, "memory_key": "session.current_ticket"}


# ── Reasoner (non-deterministic) ──────────────────────────────────────────────

@app.reasoner()
async def parse_ticket_content(arguments: Dict) -> Dict:
    """
    Use LLM to extract structured meaning from free-text ticket descriptions.
    Identifies symptoms, affected systems, urgency cues, and user intent
    even from poorly written tickets. Result is stored for downstream agents.

    Output keys: symptoms, affected_systems, urgency_cues, user_intent, summary
    """
    td = arguments.get("ticket_data", {})

    print(f"[INGESTION][LLM] Calling OpenRouter ({Config.AI_MODEL}) to extract meaning from ticket {td.get('number')}...")
    response = await app.ai(
        system=(
            "You are an IT support analyst. Extract structured meaning from ticket descriptions. "
            "Return a JSON object with these keys:\n"
            "  symptoms: list of specific problems or error symptoms described\n"
            "  affected_systems: list of systems, apps, or services impacted\n"
            "  urgency_cues: list of phrases indicating urgency or business impact\n"
            "  user_intent: one-sentence summary of what the user actually needs\n"
            "  summary: 2-3 sentence plain-English summary of the ticket\n"
            "Extract meaning even from vague or poorly written descriptions."
        ),
        user=(
            f"Title: {td.get('short_description')}\n"
            f"Description: {td.get('description')}\n"
            f"Requested item: {td.get('requested_item')}\n"
            f"Priority: {td.get('priority')}\n"
        ),
    )
    # app.ai() returns a MultimodalResponse; extract text and parse JSON
    raw_text = response.text.strip()
    print(f"[INGESTION][LLM] OpenRouter raw response: {raw_text[:300]}")
    try:
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        print(f"[INGESTION][LLM] Warning: could not parse LLM response as JSON, storing raw text")
        result = {"summary": raw_text, "symptoms": [], "affected_systems": [], "urgency_cues": [], "user_intent": ""}
    print(f"[INGESTION][LLM] Extracted: intent='{result.get('user_intent')}', systems={result.get('affected_systems')}, symptoms={result.get('symptoms')}")
    return result


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
@app.skill()
async def process_incoming_ticket(ticket_payload: Dict) -> Dict:
    """
    Main ingestion flow: parse → normalize → store → hand off to classification.
    """
    print(f"\n{'='*60}")
    print(f"[INGESTION] *** PHASE 1: TICKET INGESTION ***")
    print(f"[INGESTION] Processing ticket: {ticket_payload.get('number', 'UNKNOWN')}")
    try:
        # 1. Parse
        print(f"[INGESTION] Step 1/5: Parsing ServiceNow payload...")
        ticket_data = await batch_ticket_from_servicenow({"ticket_payload": ticket_payload})

        # 2. LLM semantic extraction via reasoner
        print(f"[INGESTION] Step 2/5: Extracting structured meaning (reasoner → OpenRouter)...")
        parsed_content = await parse_ticket_content({"ticket_data": ticket_data})
        print(f"[INGESTION] Extraction complete: intent='{parsed_content.get('user_intent')}', systems={parsed_content.get('affected_systems')}")

        # 3. Normalize
        print(f"[INGESTION] Step 3/5: Normalizing ticket fields...")
        normalized = await normalize_ticket_fields({"ticket_data": ticket_data})

        # 4. Attachments
        print(f"[INGESTION] Step 4/5: Extracting attachments...")
        attach_result = await extract_attachments({"ticket_data": ticket_data})
        print(f"[INGESTION] Attachments found: {attach_result.get('attachment_count', 0)}")

        # 5. Store in memory (normalized ticket + parsed content for downstream agents)
        print(f"[INGESTION] Step 5/5: Storing to session memory...")
        await store_to_memory({"ticket_id": ticket_data["number"], "normalized_ticket": normalized})
        await app.memory.set("parsed_ticket_content", parsed_content)
        print(f"[INGESTION] Stored parsed content in memory (key: parsed_ticket_content) — available to classification, enrichment, decision agents")

        # Trigger classification
        print(f"[INGESTION] Handing off to classification_agent for ticket {ticket_data['number']}...")
        print(f"{'='*60}\n")
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
        print(f"[INGESTION] ERROR in pipeline: {e}")
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
