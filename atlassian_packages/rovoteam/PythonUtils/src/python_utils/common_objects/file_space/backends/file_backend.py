"""FileBackend — filesystem-based resolution backend for FileSpaceManager."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from ..resolved_content import ResolvedContent

Parser = Callable[[Any], Any]

_DEFAULT_EXTENSIONS: tuple = (".jinja2", ".jinja", ".j2", ".hbs", ".txt", "")


class FileBackend:
    """Resolves variables by looking for files in a folder.

    Resolution order inside a single folder:
      1. ``{folder}/{name}{override_suffix}{ext}`` (if enable_overrides)
      2. ``{folder}/{name}{ext}`` (direct file)
      3. ``{folder}/.config.yaml[{name}]`` -> alias (LOCAL-only alias map)
    """

    scheme: str = "file"

    def __init__(
        self,
        file_extensions: Sequence[str] = _DEFAULT_EXTENSIONS,
        enable_overrides: bool = False,
        override_suffix: str = ".override",
        encoding: str = "utf-8",
    ):
        self.file_extensions = tuple(file_extensions)
        self.enable_overrides = enable_overrides
        self.override_suffix = override_suffix
        self.encoding = encoding

    def can_resolve(self, *, folder: Path, name: str) -> bool:
        """Return True if a file matching ``name`` exists in ``folder``."""
        return self.resolve(folder=folder, name=name) is not None

    def resolve(
        self,
        *,
        folder: Path,
        name: str,
        master_version: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Optional[ResolvedContent]:
        """Find a file by name inside a single folder.

        Does NOT traverse subdirectories — that's the manager's job.
        """
        if not name or not folder.is_dir():
            return None

        # 1. Override-suffixed variant
        if self.enable_overrides:
            for ext in self.file_extensions:
                override_path = folder / f"{name}{self.override_suffix}{ext}"
                if override_path.is_file():
                    return self._make_resolved(name, override_path)

        # 2. Direct file
        for ext in self.file_extensions:
            direct_path = folder / f"{name}{ext}"
            if direct_path.is_file():
                return self._make_resolved(name, direct_path)

        # 3. .config.yaml alias map (LOCAL-only, never cascades)
        config_path = folder / ".config.yaml"
        if config_path.is_file():
            alias_map = self._read_config_yaml(config_path)
            if name in alias_map:
                alias_value = alias_map[name]
                if "/" not in alias_value and "\\" not in alias_value:
                    for ext in self.file_extensions:
                        alias_path = folder / f"{alias_value}{ext}"
                        if alias_path.is_file():
                            return self._make_resolved(name, alias_path)

        return None

    def read(self, resolved: ResolvedContent, parser: Optional[Parser] = None) -> Any:
        """Read file content. Returns str when parser=None."""
        raw = resolved.path.read_text(encoding=self.encoding)
        if parser is not None:
            return parser(raw)
        return raw

    def _make_resolved(self, name: str, path: Path) -> ResolvedContent:
        """Construct a ResolvedContent for a found file."""
        mime = self._guess_mime(path)
        return ResolvedContent(
            name=name,
            kind="file",
            uri=f"file://{path}",
            path=path,
            field=None,
            mime=mime,
            _backend=self,
        )

    @staticmethod
    def _guess_mime(path: Path) -> Optional[str]:
        suffix = path.suffix.lower()
        return {
            ".jinja2": "text/x-jinja",
            ".jinja": "text/x-jinja",
            ".j2": "text/x-jinja",
            ".hbs": "text/x-handlebars",
            ".yaml": "application/yaml",
            ".yml": "application/yaml",
            ".json": "application/json",
            ".txt": "text/plain",
        }.get(suffix)

    @staticmethod
    def _read_config_yaml(config_path: Path) -> Dict[str, str]:
        """Read .config.yaml and return {name: alias_stem} dict."""
        try:
            import yaml

            data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            str(k): str(v)
            for k, v in data.items()
            if v is not None and not str(k).startswith("_")
        }
