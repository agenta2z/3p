"""GET /api/task/topologies — list available agent topology presets for /task autocomplete.

Returns each *.yaml under server/resources/tools/task/topologies/ with a description
parsed from the file's first leading-`# ...` comment.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_TOPOLOGIES_DIR = (
    Path(__file__).resolve().parent.parent
    / "resources" / "tools" / "task" / "topologies"
)

_DESC_RE = re.compile(r"^#\s*(.+)$")


@router.get("/topologies")
async def list_topologies() -> dict:
    items = []
    if _TOPOLOGIES_DIR.is_dir():
        for f in sorted(_TOPOLOGIES_DIR.glob("*.yaml")):
            desc = ""
            try:
                for line in f.read_text(encoding="utf-8").splitlines():
                    m = _DESC_RE.match(line)
                    if m:
                        desc = m.group(1).strip()
                        break
            except OSError:
                pass
            items.append({"name": f.stem, "description": desc})
    return {"topologies": items}
