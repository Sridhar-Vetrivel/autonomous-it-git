"""
ServiceNow Integration Skills

All HTTP calls to the ServiceNow REST API live here, keeping agent code clean.
"""

import aiohttp
from typing import Dict, Optional
from config import Config


async def _sn_request(method: str, path: str, payload: Optional[Dict] = None) -> Dict:
    """
    Low-level helper that sends an authenticated request to the ServiceNow instance.
    Raises on HTTP error.
    """
    if not Config.SERVICENOW_INSTANCE or not Config.SERVICENOW_API_KEY:
        raise RuntimeError("ServiceNow not configured (SERVICENOW_INSTANCE / SERVICENOW_API_KEY missing)")

    url = f"{Config.SERVICENOW_INSTANCE.rstrip('/')}/api/now/table/{Config.SERVICENOW_TABLE}/{path}"
    headers = {
        "Authorization": f"Bearer {Config.SERVICENOW_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.request(
            method,
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_ticket(arguments: Dict) -> Dict:
    """
    Fetch a ticket from ServiceNow by ticket number.

    Input:  { "ticket_id": str }
    Output: ServiceNow record dict
    """
    ticket_id = arguments["ticket_id"]
    data = await _sn_request("GET", ticket_id)
    return data.get("result", {})


async def update_ticket_status(arguments: Dict) -> Dict:
    """
    Update a ServiceNow ticket state and add work notes.

    Input: {
        "ticket_id":   str,
        "state":       str  (e.g. "resolved", "closed"),
        "work_notes":  str,
        "close_code":  str  (optional)
    }
    """
    ticket_id = arguments["ticket_id"]
    payload: Dict = {}

    state_map = {
        "new": "1",
        "in_progress": "2",
        "on_hold": "3",
        "resolved": "6",
        "closed": "7",
        "cancelled": "8",
    }

    if "state" in arguments:
        payload["state"] = state_map.get(arguments["state"], arguments["state"])
    if "work_notes" in arguments:
        payload["work_notes"] = arguments["work_notes"]
    if "close_code" in arguments:
        payload["close_code"] = arguments["close_code"]

    data = await _sn_request("PATCH", ticket_id, payload)
    return data.get("result", {})


async def add_work_note(arguments: Dict) -> Dict:
    """
    Append a work note to a ServiceNow ticket without changing state.

    Input: { "ticket_id": str, "note": str }
    """
    return await update_ticket_status(
        {"ticket_id": arguments["ticket_id"], "work_notes": arguments["note"]}
    )


async def search_related_tickets(arguments: Dict) -> list:
    """
    Query ServiceNow for tickets similar to the current one.

    Input: { "query": str, "category": str, "limit": int }
    """
    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)
    category = arguments.get("category", "")

    sysparm_query = f"short_descriptionLIKE{query}"
    if category:
        sysparm_query += f"^category={category}"

    params = f"sysparm_query={sysparm_query}&sysparm_limit={limit}&sysparm_fields=number,short_description,state,resolution_notes"

    data = await _sn_request("GET", f"?{params}")
    return data.get("result", [])
