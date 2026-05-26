"""File viewer and directory browser endpoints for the FileViewer drawer.

Security: Only serves files/directories that resolve to within the server's
runtime directory.  Uses pathlib.resolve() to prevent path traversal attacks.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, FileResponse, JSONResponse
from pathlib import Path

router = APIRouter()

_MAX_BROWSE_DEPTH = 5
_MAX_BROWSE_ENTRIES = 500


@router.get("/view/{file_path:path}")
async def view_file(request: Request, file_path: str):
    """Serve file content by absolute path.

    Security model:
    - Path must be absolute
    - Path must resolve to within _runtime/ directory (prevent traversal)
    - Serves .md as plain text (rendered by client), .html as HTML
    """
    # Browser/proxy normalization can collapse `//` in URLs.
    # `/api/view//Users/foo.md` may arrive as `/api/view/Users/foo.md`,
    # making file_path = "Users/foo.md" (no leading slash → not absolute).
    # Reconstruct the absolute path by re-prepending the leading slash on Unix.
    # On Windows, absolute paths start with a drive letter (e.g., "C:/...") so this is a no-op.
    if not file_path.startswith("/") and not (len(file_path) >= 2 and file_path[1] == ":"):
        file_path = "/" + file_path

    path = Path(file_path).resolve()

    # Must be absolute (resolve() always returns absolute, but guard original)
    if not Path(file_path).is_absolute():
        raise HTTPException(status_code=400, detail="Path must be absolute")

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {file_path}")

    # Security: only serve files under _runtime/ to prevent arbitrary filesystem access.
    # Use resolved path to defeat ../ traversal attacks.
    # Find the runtime root from app state if available, else fall back to marker check.
    runtime_dir = None
    data_service = getattr(request.app.state, "data_service", None)
    if data_service is not None:
        session_store = getattr(data_service, "_session_store", None)
        if session_store is not None:
            # SessionStore exposes the runtime root via the `runtime_root` property
            # (NOT runtime_dir — that attribute does not exist).
            runtime_dir = getattr(session_store, "runtime_root", None)

    if runtime_dir is not None:
        # Strict check: resolved path must be under the actual runtime directory
        try:
            path.relative_to(Path(runtime_dir).resolve())
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail="Access denied — file is outside the runtime directory"
            )
    else:
        # Fallback: require "_runtime" marker in resolved path string
        if "_runtime" not in str(path):
            raise HTTPException(
                status_code=403,
                detail="Access denied — only runtime files can be viewed"
            )

    # Serve content
    if path.suffix in ('.html', '.htm'):
        return FileResponse(str(path), media_type="text/html")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 text")

    return PlainTextResponse(content)


def _build_tree(directory: Path, depth: int = 0, counter: list | None = None):
    """Recursively build a directory tree structure.

    Returns a sorted list of entries (directories first, then files).
    """
    if counter is None:
        counter = [0]
    if depth >= _MAX_BROWSE_DEPTH:
        return []

    entries = []
    try:
        children = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return []

    for child in children:
        if child.name.startswith("."):
            continue
        counter[0] += 1
        if counter[0] > _MAX_BROWSE_ENTRIES:
            break

        if child.is_symlink():
            continue  # skip symlinks — prevent traversal outside runtime dir
        elif child.is_dir():
            entries.append({
                "name": child.name,
                "type": "directory",
                "children": _build_tree(child, depth + 1, counter),
            })
        elif child.is_file():
            entries.append({
                "name": child.name,
                "type": "file",
                "path": str(child),
                "size": child.stat().st_size,
            })
    return entries


@router.get("/browse/{dir_path:path}")
async def browse_directory(request: Request, dir_path: str):
    """Return recursive directory listing as JSON for folder browser UI."""
    if not dir_path.startswith("/") and not (len(dir_path) >= 2 and dir_path[1] == ":"):
        dir_path = "/" + dir_path

    path = Path(dir_path).resolve()

    if not Path(dir_path).is_absolute():
        raise HTTPException(status_code=400, detail="Path must be absolute")

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {dir_path}")

    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {dir_path}")

    runtime_dir = None
    data_service = getattr(request.app.state, "data_service", None)
    if data_service is not None:
        session_store = getattr(data_service, "_session_store", None)
        if session_store is not None:
            runtime_dir = getattr(session_store, "runtime_root", None)

    if runtime_dir is not None:
        try:
            path.relative_to(Path(runtime_dir).resolve())
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail="Access denied — directory is outside the runtime directory"
            )
    else:
        if "_runtime" not in str(path):
            raise HTTPException(
                status_code=403,
                detail="Access denied — only runtime directories can be browsed"
            )

    entries = _build_tree(path)
    return JSONResponse({"path": str(path), "entries": entries})
