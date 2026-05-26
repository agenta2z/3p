# LanceDB Setup Guide

LanceDB backend for `LanceDBRetrievalService`.

## Python Package

```bash
pip install lancedb
```

LanceDB is an embedded database — no server needed. Data is stored in
the directory specified by `db_path`.

### Optional: Hybrid Search (BM25 + Vector)

```bash
pip install tantivy
```

`tantivy` enables BM25 full-text search for hybrid mode. Without it,
`hybrid_alpha` still works but the BM25 component is skipped, effectively
giving pure vector search.

## Verification

```python
import hashlib
import tempfile
from python_utils.service_utils.retrieval_service.lancedb_retrieval_service import (
    LanceDBRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document


def demo_embed(text: str) -> list:
    """Hash-based embedding for testing (16 dimensions)."""
    h = hashlib.sha256(text.encode()).hexdigest()
    return [int(h[i:i + 2], 16) / 255.0 for i in range(0, 32, 2)]


with LanceDBRetrievalService(
        db_path=tempfile.mkdtemp(),
        embedding_function=demo_embed,
) as svc:
    assert svc.ping()
    svc.add(Document(doc_id="d1", content="hello world"))
    results = svc.search("hello")
    print(results)
    svc.clear()
```

## Configuration

| Parameter            | Default        | Description                                    |
|----------------------|----------------|------------------------------------------------|
| `db_path`            | *(required)*   | Directory for LanceDB data files               |
| `embedding_function` | *(required)*   | Callable: `str -> list[float]`                 |
| `table_name`         | `"documents"`  | LanceDB table name                             |
| `hybrid_alpha`       | `0.7`          | Vector/FTS balance (0=pure FTS, 1=pure vector) |

## Notes

- `embedding_function` is required — LanceDB needs vector embeddings for ANN search.
- The FTS index (Tantivy) is created automatically on first add if `tantivy` is installed.
- For production, use a real embedding model (e.g., sentence-transformers, OpenAI).
