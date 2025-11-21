import asyncio
from typing import List, Dict, Optional


async def hybrid_search(query: str, top_k: int = 5) -> List[Dict]:
	"""Async wrapper that performs a simple text search against Elasticsearch.

	Falls back to an empty list on errors. Uses the existing
	`backend.services.elasticsearch_service.simple_text_search` helper.
	"""
	try:
		from backend.services.elasticsearch_service import simple_text_search
	except Exception:
		return []

	# simple_text_search is synchronous; run in threadpool
	try:
		results = await asyncio.to_thread(simple_text_search, query, top_k)
		return results or []
	except Exception:
		return []
