# Enhanced Elasticsearch service with vector search and RRF
import os
import csv
import json
import sys
import glob
import uuid
import re
import numpy as np
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch, helpers

ES_URL = "http://localhost:9200"
INDEX_NAME = "products_v1"

# Initialize Elasticsearch client
es = Elasticsearch(hosts=[ES_URL])


def _safe_index_name_from_path(path: str) -> str:
    """Generate safe index name from file path."""
    base = os.path.splitext(os.path.basename(path))[0]
    safe = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")
    return f"products_{safe}" if safe else INDEX_NAME


def _infer_column_types(sample_rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Infer column types from sample data."""
    types: Dict[str, str] = {}
    for col in sample_rows[0].keys() if sample_rows else []:
        vals = [r.get(col, "") for r in sample_rows]
        non_empty = [v for v in vals if v is not None and str(v).strip() != ""]
        col_type = "text"
        if non_empty:
            all_float = True
            for v in non_empty:
                try:
                    float(v)
                except Exception:
                    all_float = False
                    break
            if all_float:
                col_type = "float"
        types[col] = col_type
    return types


def _generate_mock_vector(text: str, dim: int = 384) -> List[float]:
    """Generate a mock vector for text. In production, use sentence-transformers."""
    import hashlib
    hash_obj = hashlib.md5(text.encode())
    # Use hash to seed random number generator for consistent vectors
    np.random.seed(int(hash_obj.hexdigest(), 16) % (2**32))
    vector = np.random.normal(0, 1, dim)
    # Normalize to unit vector
    vector = vector / np.linalg.norm(vector)
    return vector.tolist()


def create_index_for_fields(index_name: str, headers: List[str], sample_rows: Optional[List[Dict[str, str]]] = None):
    """Create Elasticsearch index with proper mapping including vector field."""
    sample_rows = sample_rows or []
    inferred = _infer_column_types(sample_rows) if sample_rows else {h: "text" for h in headers}
    
    properties = {}
    for h in headers:
        if h.lower() in ("id", "product_id"):
            properties[h] = {"type": "keyword"}
        else:
            if inferred.get(h) == "float":
                properties[h] = {"type": "float"}
            else:
                properties[h] = {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}}
                }
    
    # Add vector field for semantic search
    properties["description_vector"] = {
        "type": "dense_vector",
        "dims": 384,
        "index": True,
        "similarity": "cosine"
    }

    mapping = {"mappings": {"properties": properties}}
    
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    
    es.indices.create(index=index_name, body=mapping)
    print(f"Created index {index_name}")


def bulk_index_from_csv(csv_path: str, index_name: Optional[str] = None):
    """Index CSV data into Elasticsearch with vector embeddings."""
    index_name = index_name or _safe_index_name_from_path(csv_path)
    
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not rows:
            print(f"No rows found in {csv_path}")
            return

        headers = list(rows[0].keys())
        create_index_for_fields(index_name, headers, sample_rows=rows[:20])

        actions = []
        for i, row in enumerate(rows):
            src = {}
            for h in headers:
                val = row.get(h, "").strip()
                if val:
                    try:
                        if "." in val or "e" in val.lower():
                            src[h] = float(val)
                        else:
                            src[h] = int(val) if val.isdigit() else val
                    except ValueError:
                        src[h] = val
                else:
                    src[h] = val

            # Canonicalize name and description fields
            name_aliases = ["name", "product", "title", "product_name", "model", "item"]
            desc_aliases = ["description", "details", "specs", "long_description", "info"]

            def first_nonempty(dct, aliases):
                for alias in aliases:
                    val = dct.get(alias)
                    if val and str(val).strip():
                        return str(val).strip()
                return ""

            if "name" not in src or not src.get("name"):
                name_val = first_nonempty(src, name_aliases)
                if name_val:
                    src["name"] = name_val

            if "description" not in src or not src.get("description"):
                desc_val = first_nonempty(src, desc_aliases)
                if desc_val:
                    src["description"] = desc_val

            # Generate vector for description/name field
            description_text = src.get("description", "") or src.get("name", "")
            if description_text:
                src["description_vector"] = _generate_mock_vector(description_text)

            # Set document ID
            _id = row.get("product_id") or row.get("id") or row.get("name") or str(uuid.uuid4())
            
            doc = {"_index": index_name, "_id": _id, "_source": src}
            actions.append(doc)
            
            if len(actions) >= 500:
                helpers.bulk(es, actions)
                actions = []

        if actions:
            helpers.bulk(es, actions)
        
        print(f"Indexed {len(rows)} documents from {csv_path}")


def simple_text_search(query: str, top_k: int = 5, index_name: Optional[str] = None) -> List[Dict]:
    """Perform text-based search using multi-match query."""
    idx = index_name or "products_*"
    
    body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["name^3", "description^2", "*"]
            }
        }
    }
    
    try:
        res = es.search(index=idx, body=body)
        hits = [hit["_source"] for hit in res["hits"]["hits"]]
        return hits
    except Exception as e:
        print(f"Text search failed: {e}")
        return []


def vector_search(query: str, top_k: int = 5, index_name: Optional[str] = None) -> List[Dict]:
    """Perform vector similarity search."""
    idx = index_name or "products_*"
    
    query_vector = _generate_mock_vector(query)
    
    body = {
        "size": top_k,
        "query": {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": "cosineSimilarity(params.query_vector, 'description_vector') + 1.0",
                    "params": {"query_vector": query_vector}
                }
            }
        }
    }
    
    try:
        res = es.search(index=idx, body=body)
        hits = [hit["_source"] for hit in res["hits"]["hits"]]
        return hits
    except Exception as e:
        print(f"Vector search failed: {e}")
        return []


def rrf_fuse(text_results: List[Dict], vector_results: List[Dict], k: int = 60) -> List[Dict]:
    """Reciprocal Rank Fusion algorithm to combine search results."""
    
    def get_product_id(item):
        return item.get("product_id") or item.get("id") or item.get("name", "")
    
    # Create rank maps
    text_ranks = {get_product_id(item): rank + 1 for rank, item in enumerate(text_results)}
    vector_ranks = {get_product_id(item): rank + 1 for rank, item in enumerate(vector_results)}
    
    # Calculate RRF scores
    rrf_scores = {}
    all_items = {}
    
    # Process text results
    for item in text_results:
        pid = get_product_id(item)
        all_items[pid] = item
        rrf_scores[pid] = 1.0 / (k + text_ranks[pid])
    
    # Process vector results
    for item in vector_results:
        pid = get_product_id(item)
        all_items[pid] = item
        if pid in rrf_scores:
            rrf_scores[pid] += 1.0 / (k + vector_ranks[pid])
        else:
            rrf_scores[pid] = 1.0 / (k + vector_ranks[pid])
    
    # Sort by RRF score
    sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Return fused results
    fused = []
    for pid, score in sorted_items:
        if pid in all_items:
            fused.append(all_items[pid])
    
    return fused


def hybrid_search(query: str, top_k: int = 5, index_name: Optional[str] = None) -> List[Dict]:
    """Perform hybrid search combining text and vector search with RRF."""
    text_results = simple_text_search(query, top_k * 2, index_name)
    vector_results = vector_search(query, top_k * 2, index_name)
    
    if not text_results and not vector_results:
        return []
    
    if not text_results:
        return vector_results[:top_k]
    
    if not vector_results:
        return text_results[:top_k]
    
    fused_results = rrf_fuse(text_results, vector_results)
    return fused_results[:top_k]


if __name__ == "__main__":
    # Index CSV files
    args = sys.argv[1:]
    if args:
        csv_paths = args
    else:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        csv_dir = os.path.join(repo_root, 'data', 'csv')
        csv_paths = glob.glob(os.path.join(csv_dir, '*.csv'))

    if not csv_paths:
        print("No CSV files found to index.")
    else:
        for p in csv_paths:
            print(f"Indexing {p}...")
            try:
                bulk_index_from_csv(p)
            except Exception as e:
                print(f"Error indexing {p}: {e}")
        print("Indexing finished.")