# Elasticsearch Setup Guide

Elasticsearch backend for `ElasticsearchRetrievalService`.

## Python Package

```bash
pip install elasticsearch
```

## Running Elasticsearch

### Docker (recommended)

```bash
docker compose -f docs/setup/service_utils/retrieval_service/elasticsearch/docker-compose.yml up -d
```

This starts a single-node Elasticsearch cluster on port **9200** with
security disabled (dev mode).

### WSL2 (Windows without Docker)

If Docker is not installed, Elasticsearch can run inside WSL2. WSL2
automatically forwards ports to Windows, so `localhost:9200` works from
PowerShell.

**1. Check that WSL is available and running:**

```powershell
wsl --list --verbose
# Should show a distro (e.g. Ubuntu) in "Running" state
```

**2. Install Elasticsearch inside WSL (one-time):**

```powershell
wsl -d Ubuntu -- bash -c "
  # Import Elastic GPG key and add repository
  wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | sudo gpg --dearmor -o /usr/share/keyrings/elasticsearch-keyring.gpg
  echo 'deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main' | sudo tee /etc/apt/sources.list.d/elastic-8.x.list
  sudo apt update && sudo apt install -y elasticsearch
"
```

**3. Configure for local dev (disable security) and start:**

```powershell
# Disable security for local development
wsl -d Ubuntu -- bash -c "sudo sed -i 's/xpack.security.enabled: true/xpack.security.enabled: false/' /etc/elasticsearch/elasticsearch.yml"
wsl -d Ubuntu -- bash -c "sudo service elasticsearch start"
```

**4. Verify from PowerShell (may take 30-60s to start):**

```powershell
Invoke-RestMethod -Uri "http://localhost:9200" -ErrorAction SilentlyContinue
# Expected: JSON with cluster info and "You Know, for Search"
```

**Stopping Elasticsearch:**

```powershell
wsl -d Ubuntu -- bash -c "sudo service elasticsearch stop"
```

### Native Install (fallback)

Download from https://www.elastic.co/downloads/elasticsearch and follow
the platform-specific instructions. Disable security for local dev:

```yaml
# config/elasticsearch.yml
xpack.security.enabled: false
```

## Verification

```bash
curl http://localhost:9200
# Expected: JSON with cluster info and "You Know, for Search"
```

```python
from python_utils.service_utils.retrieval_service.elasticsearch_retrieval_service import (
    ElasticsearchRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document

with ElasticsearchRetrievalService(
        hosts=["http://localhost:9200"],
        index_name="test_docs",
) as svc:
    assert svc.ping()
    svc.add(Document(doc_id="d1", content="hello world"))
    results = svc.search("hello")
    print(results)
    svc.clear()
```

## Configuration

| Parameter    | Default        | Description                              |
|--------------|----------------|------------------------------------------|
| `hosts`      | *(required)*   | List of ES URLs, e.g. `["http://localhost:9200"]` |
| `index_name` | `"documents"`  | Elasticsearch index name                 |
| `auth`       | `None`         | Optional `(username, password)` tuple    |

## Stopping

**Docker:**

```bash
docker compose -f docs/setup/service_utils/retrieval_service/elasticsearch/docker-compose.yml down
# Add -v to also remove data volumes
```

**WSL2:**

```powershell
wsl -d Ubuntu -- bash -c "sudo service elasticsearch stop"
```
