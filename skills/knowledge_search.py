"""
Knowledge Base Search Skills

Wrappers for querying the internal knowledge base / KB articles.
"""

import aiohttp
from typing import Dict, List
from config import Config


async def search_articles(arguments: Dict) -> List[Dict]:
    """
    Search the knowledge base for articles matching the query.

    Input:  { "query": str, "category": str (optional), "limit": int (optional) }
    Output: list of { id, title, url, snippet, relevance_score }
    """
    if not Config.KNOWLEDGE_BASE_URL:
        return []

    query = arguments.get("query", "")
    category = arguments.get("category", "")
    limit = arguments.get("limit", 5)

    params = {"q": query, "limit": limit}
    if category:
        params["category"] = category

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


async def get_article(arguments: Dict) -> Dict:
    """
    Retrieve a specific knowledge article by ID.

    Input:  { "article_id": str }
    Output: full article dict
    """
    if not Config.KNOWLEDGE_BASE_URL:
        return {}

    article_id = arguments["article_id"]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{Config.KNOWLEDGE_BASE_URL}/articles/{article_id}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass

    return {}
