# Redis Setup Guide

Redis backend for `RedisKeyValueService`.

## Python Package

```bash
pip install redis
```

## Running Redis

### Docker (recommended)

```bash
docker compose -f docs/setup/service_utils/keyvalue_service/redis/docker-compose.yml up -d
```

This starts Redis on port **6379** with no authentication (dev mode).

### WSL2 (Windows without Docker)

If Docker is not installed, Redis can run inside WSL2. WSL2 automatically
forwards ports to Windows, so `localhost:6379` works from PowerShell.

**1. Check that WSL is available and running:**

```powershell
wsl --list --verbose
# Should show a distro (e.g. Ubuntu) in "Running" state
```

**2. Install Redis inside WSL (one-time):**

```powershell
wsl -d Ubuntu -- bash -c "sudo apt update && sudo apt install -y redis-server"
```

**3. Start the Redis server:**

```powershell
# Start as a background service
wsl -d Ubuntu -- bash -c "sudo service redis-server start"
```

**4. Verify from PowerShell:**

```powershell
wsl -d Ubuntu -- bash -c "redis-cli ping"
# Expected: PONG
```

Redis is now accessible from Windows at `localhost:6379`.

**Stopping Redis:**

```powershell
wsl -d Ubuntu -- bash -c "sudo service redis-server stop"
```

### Native Install (fallback)

- **Windows (no WSL)**: Use [Memurai](https://www.memurai.com/), a Windows-native Redis-compatible server.
- **macOS**: `brew install redis && brew services start redis`
- **Linux**: `sudo apt install redis-server && sudo systemctl start redis`

## Verification

```bash
# CLI (Linux/macOS or from within WSL)
redis-cli ping
# Expected: PONG
```

```powershell
# From Windows PowerShell (if Redis is running in WSL or Docker)
wsl -d Ubuntu -- bash -c "redis-cli ping"
# Expected: PONG
```

```python
from python_utils.service_utils.keyvalue_service.redis_keyvalue_service import (
    RedisKeyValueService,
)

with RedisKeyValueService(host="localhost", port=6379) as svc:
    assert svc.ping()
    svc.put("test_key", {"hello": "world"})
    print(svc.get("test_key"))  # {'hello': 'world'}
    svc.delete("test_key")
```

## Configuration

| Parameter  | Default       | Description              |
|------------|---------------|--------------------------|
| `host`     | `"localhost"` | Redis server hostname    |
| `port`     | `6379`        | Redis server port        |
| `db`       | `0`           | Redis database index     |
| `prefix`   | `"kv"`        | Key prefix for all keys  |
| `password` | `None`        | Optional Redis password  |

## Stopping

```bash
docker compose -f docs/setup/service_utils/keyvalue_service/redis/docker-compose.yml down
```
