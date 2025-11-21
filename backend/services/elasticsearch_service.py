# scripts/index_products_es.py
import csv
import os
import re
import uuid
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch, helpers

ES_URL = "http://localhost:9200"
# default index used when caller doesn't provide one
INDEX_NAME = "products_v1"

# Use keyword/hosts-style initialization to be explicit and compatible
es = Elasticsearch(hosts=[ES_URL])


def _safe_index_name_from_path(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    # sanitize to lowercase letters, numbers and underscores
    safe = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")
    return f"products_{safe}" if safe else INDEX_NAME


def _infer_column_types(sample_rows: List[Dict[str, str]]) -> Dict[str, str]:
    # naive inference: if all non-empty values parse as float -> float, else text
    types: Dict[str, str] = {}
    for col in sample_rows[0].keys() if sample_rows else []:
        vals = [r.get(col, "") for r in sample_rows]
        non_empty = [v for v in vals if v is not None and str(v).strip() != ""]
        col_type = "text"
        if non_empty:
            all_float = True
            for v in non_empty:
                try:
                    float(str(v))
                except Exception:
                    all_float = False
                    break
            if all_float:
                col_type = "float"
        types[col] = col_type
    return types


def create_index_for_fields(index_name: str, headers: List[str], sample_rows: Optional[List[Dict[str, str]]] = None):
    # build properties mapping based on headers and sample data
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
                # index as text for full-text search, keep a keyword subfield for exact matches
                properties[h] = {"type": "text", "fields": {"raw": {"type": "keyword"}}}

    mapping = {"mappings": {"properties": properties}}
    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name, body=mapping)
        print("Created index", index_name)


def bulk_index_from_csv(csv_path: str, index_name: Optional[str] = None):
    index_name = index_name or _safe_index_name_from_path(csv_path)
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not rows:
            print(f"No rows found in {csv_path}")
            return

        headers = rows[0].keys()
        # create index with inferred mapping
        create_index_for_fields(index_name, list(headers), sample_rows=rows[:20])

        actions = []
        for i, row in enumerate(rows):
            # build the source by including all headers present in CSV
            src = {}
            for h in headers:
                val = row.get(h, None)
                if val is None or str(val).strip() == "":
                    continue
                # coerce numeric-like fields to float when possible
                try:
                    if _infer_column_types([row]).get(h) == "float":
                        src[h] = float(val)
                        continue
                except Exception:
                    pass
                src[h] = val

            # Canonicalize common name/description fields so search is consistent
            name_aliases = ["name", "product", "title", "product_name", "model", "item"]
            desc_aliases = ["description", "details", "specs", "long_description", "info"]

            def first_nonempty(dct, aliases):
                for a in aliases:
                    # check both original header and lowercased variants
                    for key in (a, a.lower(), a.upper()):
                        v = dct.get(key)
                        if v is not None and str(v).strip() != "":
                            return v
                return None

            # if a canonical name isn't present, try aliases
            if "name" not in src or not src.get("name"):
                fn = first_nonempty(row, name_aliases)
                if fn:
                    src["name"] = fn

            if "description" not in src or not src.get("description"):
                fd = first_nonempty(row, desc_aliases)
                if fd:
                    src["description"] = fd

            # determine _id: prefer product_id/id/name, else generate uuid
            _id = row.get("product_id") or row.get("id") or row.get("name") or str(uuid.uuid4())

            doc = {"_index": index_name, "_id": _id, "_source": src}
            actions.append(doc)
            if len(actions) >= 500:
                helpers.bulk(es, actions)
                actions = []

        if actions:
            helpers.bulk(es, actions)


def simple_text_search(query: str, top_k: int = 5, index_name: Optional[str] = None) -> List[Dict]:
    # By default search across all product indices created by the CSV indexer
    idx = index_name or "products_*"
    body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["name^3", "description", "*^2"]
            }
        }
    }
    res = es.search(index=idx, body=body)
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
    import sys
    import glob

    # allow passing file paths on the command line; otherwise index all CSVs under data/csv
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
        for p in csv_paths[:2]: # limit to first 2 for quick testing
            print(f"Indexing {p}...")
            try:
                bulk_index_from_csv(p)
            except Exception as e:
                print(f"Failed indexing {p}: {e}")
        print("Indexing finished.")
