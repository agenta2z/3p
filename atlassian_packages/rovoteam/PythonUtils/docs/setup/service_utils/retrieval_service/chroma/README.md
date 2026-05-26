# ChromaDB Setup Guide

ChromaDB backend for `ChromaRetrievalService`.

## Python Package

```bash
pip install chromadb
```

ChromaDB runs as an embedded library by default — no server needed.
For persistent storage, pass `persist_directory` to the service constructor.

## Verification

```python
from python_utils.service_utils.retrieval_service.chroma_retrieval_service import (
    ChromaRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document

# In-memory (no persist_directory)
with ChromaRetrievalService(collection_name="test") as svc:
    assert svc.ping()
    svc.add(Document(doc_id="d1", content="hello world"))
    results = svc.search("hello")
    print(results)  # [(Document(...), 0.85)]
    svc.clear()
```

## Configuration

| Parameter             | Default        | Description                                      |
|-----------------------|----------------|--------------------------------------------------|
| `collection_name`     | `"documents"`  | Chroma collection name                           |
| `persist_directory`   | `None`         | Directory for persistent storage (None = memory) |
| `embedding_function`  | `None`         | Custom Chroma embedding function                 |

When `embedding_function` is `None`, ChromaDB uses its default model
(all-MiniLM-L6-v2 via sentence-transformers), which will be downloaded
on first use.

## Server Mode (optional)

For multi-process access, run ChromaDB as a server:

```bash
pip install chromadb
chroma run --path /tmp/chroma_data --port 8000
```

Then use `chromadb.HttpClient(host="localhost", port=8000)` instead of
the default embedded client. The `ChromaRetrievalService` currently uses
the embedded client; server mode requires subclassing or a future update.
