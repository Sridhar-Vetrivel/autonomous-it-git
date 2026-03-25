"""
Enrichment Agent — Phase 3

Gathers contextual information (user profile, related tickets, KB articles)
to inform the resolution plan.
"""

import asyncio
from typing import Dict, List

from agentfield import Agent, AIConfig
from schemas.enrichment import EnrichmentResult, UserProfile, RelatedTicket
from config import Config
from shared.decorators import handle_errors, handle_errors_silently, track_performance, track_slow_operation

app = Agent(
    node_id="enrichment_agent",
    agentfield_server=Config.AGENTFIELD_SERVER,
    ai_config=AIConfig(model=Config.AI_MODEL),
)


# ── Skills ────────────────────────────────────────────────────────────────────

@app.skill()
@handle_errors("enrich_ticket")
@track_performance("enrich_ticket")
async def enrich_ticket(arguments: Dict) -> Dict:
    """
    Orchestrate all enrichment sub-tasks in parallel, then synthesize results.

    Input:  { "ticket_id": str }
    Output: EnrichmentResult dict (stored in session memory)
    """
    ticket_id = arguments["ticket_id"]
    print(f"\n{'='*60}")
    print(f"[ENRICHMENT] *** PHASE 3: TICKET ENRICHMENT ***")
    print(f"[ENRICHMENT] Enriching ticket: {ticket_id}")
    ticket = await app.memory.get("current_ticket")
    classification = await app.memory.get("classification_result")

    if not ticket:
        print(f"[ENRICHMENT] ERROR: Ticket {ticket_id} not found in session memory")
        raise ValueError(f"Ticket {ticket_id} not found in session memory")

    print(f"[ENRICHMENT] Running parallel lookups: user profile, knowledge base, related incidents...")
    # Run lookups concurrently
    user_profile_task = lookup_user_profile({"email": ticket.get("requester_email", "")})
    kb_task = search_knowledge_base(
        {"query": ticket.get("title", ""), "category": (classification or {}).get("category", "")}
    )
    related_task = fetch_related_incidents(
        {"ticket_id": ticket_id, "category": (classification or {}).get("category", "")}
    )

    user_profile_dict, kb_articles, related_tickets = await asyncio.gather(
        user_profile_task, kb_task, related_task
    )
    print(f"[ENRICHMENT] User profile: {user_profile_dict.get('display_name')} ({user_profile_dict.get('department')})")
    print(f"[ENRICHMENT] KB articles found: {len(kb_articles)}")
    print(f"[ENRICHMENT] Related incidents found: {len(related_tickets)}")

    # Determine service owner via AI
    print(f"[ENRICHMENT] Identifying service owner via AI...")
    service_info = await identify_service_owner(
        {"classification": classification, "ticket": ticket}
    )

    print(f"[ENRICHMENT] Service owner: {service_info.get('service_owner')} / {service_info.get('service_owner_team')}")
    # Summarize and store
    print(f"[ENRICHMENT] Synthesizing enrichment context via AI...")
    enriched = await summarize_context(
        {
            "ticket": ticket,
            "classification": classification,
            "user_profile": user_profile_dict,
            "kb_articles": kb_articles,
            "related_tickets": related_tickets,
            "service_info": service_info,
        }
    )

    await app.memory.set("enriched_ticket", enriched)
    await app.memory.set("user_context", user_profile_dict)
    await app.memory.set("related_tickets", related_tickets)
    print(f"[ENRICHMENT] Enrichment stored. Complexity: {enriched.get('estimated_resolution_complexity', 'unknown')}")
    print(f"[ENRICHMENT] Handing off to decision_planning_agent for ticket {ticket_id}")
    print(f"{'='*60}\n")

    # Hand off to Decision & Planning
    await app.call(
        "decision_planning_agent.generate_resolution_plan",
        arguments={"ticket_id": ticket_id},
    )

    return enriched


@app.skill()
@handle_errors_silently("lookup_user_profile")
async def lookup_user_profile(arguments: Dict) -> Dict:
    """
    Fetch user profile from the directory / ServiceNow user table.
    Returns a UserProfile dict (mocked or real depending on environment).
    """
    email = arguments.get("email", "")
    print(f"[ENRICHMENT] Looking up user profile for: {email}")

    # In production this would call the user directory API.
    # We return a sensible default so the pipeline never blocks.
    profile = UserProfile(
        email=email,
        display_name=email.split("@")[0].replace(".", " ").title(),
        department="Unknown",
        active=True,
        mfa_enabled=False,
        recent_tickets=[],
    )
    return profile.model_dump()


@app.skill()
@handle_errors_silently("search_knowledge_base")
@track_slow_operation("search_knowledge_base", warn_seconds=3.0, critical_seconds=8.0)
async def search_knowledge_base(arguments: Dict) -> List[Dict]:
    """
    Search the knowledge base for articles relevant to the ticket.

    Returns a list of { "id", "title", "url", "relevance_score" } dicts.
    """
    query = arguments.get("query", "")
    category = arguments.get("category", "")

    print(f"[ENRICHMENT] Searching KB for: '{query}' (category={category})")
    if not Config.KNOWLEDGE_BASE_URL:
        print(f"[ENRICHMENT] No KNOWLEDGE_BASE_URL configured — skipping KB search")
        # No KB configured — return empty list
        return []

    import aiohttp

    params = {"q": query, "category": category, "limit": 5}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{Config.KNOWLEDGE_BASE_URL}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("articles", [])
    except Exception:
        pass
    return []


@app.skill()
@handle_errors_silently("fetch_related_incidents")
@track_performance("fetch_related_incidents")
async def fetch_related_incidents(arguments: Dict) -> List[Dict]:
    """
    Use vector similarity search to find previously resolved similar tickets.
    """
    ticket_id = arguments.get("ticket_id", "")
    category = arguments.get("category", "")

    # Search global vector store for similar resolutions
    current_ticket = await app.memory.get("current_ticket") or {}
    query_text = f"{current_ticket.get('title', '')} {current_ticket.get('description', '')}"

    try:
        results = await app.memory.similarity_search(
            query=query_text,
            top_k=Config.VECTOR_SIMILARITY_TOP_K,
            filter={"category": category} if category else None,
        )
        related = []
        for r in results:
            related.append(
                RelatedTicket(
                    ticket_id=r.get("key", ""),
                    similarity_score=r.get("score", 0.0),
                    category=r.get("metadata", {}).get("category", category),
                    status=r.get("metadata", {}).get("status", "closed"),
                    resolution=r.get("text"),
                    resolution_time_hours=r.get("metadata", {}).get("resolution_time_hours"),
                ).model_dump()
            )
        return related
    except Exception:
        return []


# ── Reasoners ─────────────────────────────────────────────────────────────────

@app.reasoner()
@handle_errors("summarize_context")
@track_slow_operation("summarize_context", warn_seconds=8.0, critical_seconds=20.0)
async def summarize_context(arguments: Dict) -> Dict:
    """
    AI synthesis: combine all gathered context into an EnrichmentResult.
    """
    ticket = arguments.get("ticket", {})
    classification = arguments.get("classification", {})
    user_profile = arguments.get("user_profile", {})
    kb_articles = arguments.get("kb_articles", [])
    related_tickets = arguments.get("related_tickets", [])
    service_info = arguments.get("service_info", {})

    response: EnrichmentResult = await app.ai(
        system=(
            "You are an IT enrichment expert. Given ticket, classification, user, "
            "knowledge base articles, and related tickets, produce a JSON EnrichmentResult "
            "with fields: ticket_id, user_profile (passthrough), related_tickets (passthrough), "
            "service_owner (string), service_owner_team (string), knowledge_base_articles "
            "(passthrough), previous_similar_resolutions (int), "
            "estimated_resolution_complexity (simple|moderate|complex), "
            "required_approvals (list of strings), additional_context (dict)."
        ),
        user=(
            f"Ticket: {ticket}\n"
            f"Classification: {classification}\n"
            f"User: {user_profile}\n"
            f"KB Articles: {kb_articles}\n"
            f"Related Tickets: {related_tickets}\n"
            f"Service Info: {service_info}\n\n"
            "Produce the enrichment result."
        ),
        schema=EnrichmentResult,
    )
    return response.model_dump()


@app.reasoner()
@handle_errors("identify_service_owner")
@track_slow_operation("identify_service_owner", warn_seconds=5.0, critical_seconds=15.0)
async def identify_service_owner(arguments: Dict) -> Dict:
    """
    Determine the responsible team/owner based on classification and ticket context.
    """
    classification = arguments.get("classification", {})
    ticket = arguments.get("ticket", {})

    response = await app.ai(
        system=(
            "You are an IT service routing expert. Based on ticket category and details, "
            "identify the service owner and team. Return JSON: "
            "{ service_owner: str, service_owner_team: str, reasoning: str }"
        ),
        user=(
            f"Category: {classification.get('category')}\n"
            f"Ticket: {ticket.get('title')}\n"
            f"Assignment group hint: {ticket.get('metadata', {}).get('assignment_group')}"
        ),
    )
    return response
