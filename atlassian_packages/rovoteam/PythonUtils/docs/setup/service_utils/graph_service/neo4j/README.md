# Neo4j Setup Guide

Neo4j backend for `Neo4jGraphService`.

## Python Package

```bash
pip install neo4j
```

## Running Neo4j

### Docker (recommended)

```bash
docker compose -f docs/setup/service_utils/graph_service/neo4j/docker-compose.yml up -d
```

This starts Neo4j with:
- Bolt port: **7687** (driver connections)
- HTTP port: **7474** (browser UI)
- Auth: `neo4j` / `testpassword`

### WSL2 (Windows without Docker)

If Docker is not installed, Neo4j can run inside WSL2. WSL2 automatically
forwards ports to Windows, so `localhost:7687` and `localhost:7474` work
from PowerShell.

**1. Check that WSL is available and running:**

```powershell
wsl --list --verbose
# Should show a distro (e.g. Ubuntu) in "Running" state
```

**2. Install Neo4j inside WSL (one-time):**

```powershell
wsl -d Ubuntu -- bash -c "
  # Add Neo4j repository
  curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/neo4j.gpg
  echo 'deb [signed-by=/usr/share/keyrings/neo4j.gpg] https://debian.neo4j.com stable latest' | sudo tee /etc/apt/sources.list.d/neo4j.list
  sudo apt update && sudo apt install -y neo4j
"
```

**3. Set the initial password and start:**

```powershell
wsl -d Ubuntu -- bash -c "sudo neo4j-admin dbms set-initial-password testpassword"
wsl -d Ubuntu -- bash -c "sudo neo4j start"
```

**4. Verify from PowerShell:**

```powershell
# Wait ~15s for startup, then check the HTTP endpoint
Invoke-RestMethod -Uri "http://localhost:7474" -ErrorAction SilentlyContinue
```

**Stopping Neo4j:**

```powershell
wsl -d Ubuntu -- bash -c "sudo neo4j stop"
```

### Native Install (fallback)

Download from https://neo4j.com/download/ and follow the platform
instructions. Set the initial password:

```bash
neo4j-admin dbms set-initial-password testpassword
```

## Verification

Open http://localhost:7474 in a browser to access the Neo4j Browser.

```python
from python_utils.service_utils.graph_service.neo4j_graph_service import (
    Neo4jGraphService,
)
from python_utils.service_utils.graph_service.graph_node import GraphNode

with Neo4jGraphService(
        uri="bolt://localhost:7687",
        auth=("neo4j", "testpassword"),
) as svc:
    assert svc.ping()
    svc.add_node(GraphNode(node_id="n1", node_type="test", label="Test Node"))
    node = svc.get_node("n1")
    print(node)  # GraphNode(node_id='n1', ...)
    svc.clear()
```

## Configuration

| Parameter  | Default     | Description                          |
|------------|-------------|--------------------------------------|
| `uri`      | *(required)* | Bolt URI, e.g. `"bolt://localhost:7687"` |
| `auth`     | *(required)* | `(username, password)` tuple         |
| `database` | `"neo4j"`   | Neo4j database name                  |

## Stopping

**Docker:**

```bash
docker compose -f docs/setup/service_utils/graph_service/neo4j/docker-compose.yml down
# Add -v to also remove data volumes
```

**WSL2:**

```powershell
wsl -d Ubuntu -- bash -c "sudo neo4j stop"
```
