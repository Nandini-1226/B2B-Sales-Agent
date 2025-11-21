import asyncio
from typing import List, Dict, Optional


async def hybrid_search(query: str, top_k: int = 5) -> List[Dict]:
    """Async wrapper that performs hybrid search using RRF fusion."""
    try:
        from backend.services.elasticsearch_service import hybrid_search as es_hybrid_search
        # Run the synchronous hybrid search in a thread pool
        results = await asyncio.to_thread(es_hybrid_search, query, top_k)
        return results or []
    except Exception as e:
        print(f"Hybrid search error: {e}")
        return []


async def simple_product_search(query: str, top_k: int = 5) -> List[Dict]:
    """Fallback simple search if hybrid search fails."""
    try:
        from backend.services.elasticsearch_service import simple_text_search
        results = await asyncio.to_thread(simple_text_search, query, top_k)
        return results or []
    except Exception as e:
        print(f"Simple search error: {e}")
        return []
