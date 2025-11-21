import asyncio
from typing import List, Dict, Optional
import logging
import elasticsearch


async def hybrid_search(query: str, top_k: int = 5, category: str = None) -> List[Dict]:
    """Async wrapper that performs hybrid search using RRF fusion."""
    try:
        from backend.services.elasticsearch_service import hybrid_search as es_hybrid_search
        # Run the synchronous hybrid search in a thread pool
        results = await asyncio.to_thread(es_hybrid_search, query, top_k, category)
        logging.info(f"Hybrid search for '{query}' in category '{category}' returned {len(results)} results")
        return results or []
    except Exception as e:
        logging.error(f"Hybrid search error: {e}")
        return []


async def simple_product_search(query: str, top_k: int = 5) -> List[Dict]:
    """Fallback simple search if hybrid search fails."""
    try:
        from backend.services.elasticsearch_service import simple_text_search
        results = await asyncio.to_thread(simple_text_search, query, top_k)
        return results or []
    except Exception as e:
        logging.error(f"Simple search error: {e}")
        return []
