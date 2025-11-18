# scripts/index_products_es.py
import csv
from typing import List, Dict
from elasticsearch import Elasticsearch, helpers

ES_URL = "http://localhost:9200"
INDEX_NAME = "products_v1"

es = Elasticsearch(ES_URL)

def create_index():
    # simple mapping - add dense_vector later when you have embeddings
    mapping = {
        "mappings": {
            "properties": {
                "product_id": {"type": "keyword"},
                "name": {"type": "text"},
                "description": {"type": "text"},
                "category": {"type": "keyword"},
                "price": {"type": "float"},
                # "embedding": {"type": "dense_vector", "dims": 768}  # add later
            }
        }
    }
    if not es.indices.exists(INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=mapping)
        print("Created index", INDEX_NAME)

def bulk_index_from_csv(csv_path: str):
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        actions = []
        for row in reader:
            doc = {
                "_index": INDEX_NAME,
                "_id": row["product_id"],
                "_source": {
                    "product_id": row["product_id"],
                    "name": row["name"],
                    "description": row.get("description", ""),
                    "category": row.get("category", ""),
                    "price": float(row.get("price", 0.0)),
                }
            }
            actions.append(doc)
            if len(actions) >= 500:
                helpers.bulk(es, actions); actions = []
        if actions:
            helpers.bulk(es, actions)


def simple_text_search(query: str, top_k: int = 5) -> List[Dict]:
    body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["name^3", "description"]
            }
        }
    }
    res = es.search(index=INDEX_NAME, body=body)
    hits = [hit["_source"] for hit in res["hits"]["hits"]]
    return hits

# placeholder for RRF fusion - simple merge for now
def rrf_fuse(list_a: List[Dict], list_b: List[Dict]) -> List[Dict]:
    # simple union preserving order and removing duplicates
    seen = set()
    fused = []
    for lst in (list_a, list_b):
        for item in lst:
            pid = item.get("product_id")
            if pid not in seen:
                fused.append(item); seen.add(pid)
    return fused


if __name__ == "__main__":
    create_index()
    bulk_index_from_csv("data/products.csv")
    print("Indexing finished.")
