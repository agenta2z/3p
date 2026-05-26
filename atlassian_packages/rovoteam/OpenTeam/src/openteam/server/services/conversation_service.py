"""ConversationService — renders conversation prompts and manages LLM interactions.

Responsibilities:
1. Render initial.jinja2 with session history + user input
2. Call LLM via configurable backend (ai-gateway, direct API, or mock)
3. Parse <Response> tags from LLM output
4. Return the assistant's response content

Does NOT manage session persistence — that's SessionStore's job.
The route handler orchestrates: append user msg → call service → append response.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import agent_foundation.resources as _af_res

_AF_TEMPLATES_ROOT = Path(_af_res.__file__).parent / "prompt_templates"

logger = logging.getLogger(__name__)


class _SimplePromptRenderer:
    """Minimal PromptRenderer conforming to ConversationalInferencer's protocol.

    Uses Jinja2 directly, avoiding JinjaPromptRenderer's YAML config loading
    which depends on a newer merge_mappings signature.
    """

    def __init__(self, templates_dir: Path) -> None:
        from jinja2 import Environment, FileSystemLoader

        self._templates_dir = templates_dir
        self._template_path = "conversation/main/initial.jinja2"
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,
        )
        self._variable_manager = None

    def render(self, variables: dict) -> str:
        template = self._env.get_template(self._template_path)
        return template.render(**variables)

    def render_string(self, template_str: str, context: dict) -> str:
        template = self._env.from_string(template_str)
        return template.render(**context)

    @property
    def template_source(self) -> str:
        source = self._env.loader.get_source(self._env, self._template_path)
        return source[0]

    @property
    def template_config(self) -> dict:
        """Load .initial.config.yaml sidecar config for the template.

        Resolution order (matching JinjaPromptRenderer):
          1. .<basename>.config.yaml  (e.g. .initial.config.yaml)
          2. .config.yaml             (folder-level default)
        """
        if hasattr(self, "_cached_template_config"):
            return self._cached_template_config

        import yaml as _yaml

        template_dir = self._templates_dir / "conversation" / "main"
        for candidate in (
            template_dir / ".initial.config.yaml",
            template_dir / ".config.yaml",
        ):
            if candidate.is_file():
                try:
                    data = _yaml.safe_load(candidate.read_text(encoding="utf-8"))
                    self._cached_template_config = data if isinstance(data, dict) else {}
                    return self._cached_template_config
                except Exception:
                    pass

        self._cached_template_config = {}
        return self._cached_template_config

    @property
    def template_variables(self) -> dict:
        """Load .variables.yaml from the template directory."""
        template_dir = self._templates_dir / "conversation" / "main"
        variables_file = template_dir / ".variables.yaml"
        if variables_file.is_file():
            import yaml

            try:
                data = yaml.safe_load(variables_file.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

    @property
    def variable_manager(self):
        return self._variable_manager

    def find_sop_file(self) -> Path | None:
        template_dir = self._templates_dir / "conversation" / "main"
        variables_dir = template_dir / "_variables" / "workflow"
        if not variables_dir.is_dir():
            return None
        for ext in (".jinja2", ".j2", ".md", ".yaml", ".yml"):
            candidate = variables_dir / f"sop{ext}"
            if candidate.is_file():
                return candidate
        return None


def _build_prompt_renderer(templates_dir: Path) -> _SimplePromptRenderer:
    """Build a PromptRenderer for the ConversationalInferencer."""
    return _SimplePromptRenderer(templates_dir)


class ConversationService:
    """Renders conversation prompts and manages LLM interactions."""

    def __init__(
        self,
        templates_dir: Path,
        llm_backend: str = "mock",
        working_dir: str | None = None,
        cache_dir: str | None = None,
        session_store: object | None = None,
        llm_model: str | None = None,
    ) -> None:
        self._templates_dir = templates_dir
        self._llm_backend = llm_backend
        self._llm_model = llm_model
        self._working_dir = working_dir or str(Path.home())
        self._cache_dir = cache_dir
        self._session_store = session_store
        self._inferencers: dict[str, object] = {}  # session_id → ConversationalInferencer
        self._mock_prompt_cache: dict[str, dict] = {}  # session_id → last prompt data (mock mode)
        # Per-session JsonLogger cache for RankEvolve-style structured logging.
        # Created lazily on first run_conversation_turn call so that we have
        # a session_dir to bind to. Reused across turns so the JSONL file
        # accumulates and the parts/ subfolders persist across the session.
        self._session_loggers: dict[str, Any] = {}
        self._template_manager = self._build_template_manager()

    def _build_template_manager(self):
        """Create TemplateManager for conversation prompt rendering.

        Uses the same TemplateManager pattern as create_role/executor.py:
        - Root: prompt_templates/
        - active_template_type: "main"
        - predefined_variables: True (loads .variables.yaml for {{ employee }})

        Falls back to raw Jinja2 rendering if TemplateManager is not available.
        """
        try:
            from python_utils.string_utils.formatting.template_manager import (
                TemplateManager,
            )

            return TemplateManager(
                templates=[str(self._templates_dir), str(_AF_TEMPLATES_ROOT)],
                active_template_type="main",
                predefined_variables=True,
                cross_root_variable_lookup=True,  # Refactor 17
            )
        except ImportError:
            logger.warning(
                "python_utils not available — using fallback Jinja2 rendering"
            )
            return None

    def render_prompt(self, session: dict, user_message: str) -> str:
        """Render the conversation prompt with session history + current turn.

        Builds the template feed:
        - conversation_history: list of {role, content} from session.messages
        - current_turn: {role: "manager", content: user_message}
        - employee: auto-injected from .variables.yaml (via TemplateManager)
        """
        messages = session.get("messages", [])

        # Build conversation_history from existing messages
        conversation_history = []
        for msg in messages:
            role = msg.get("role", "manager")
            # Map OpenTeam roles to prompt template roles
            prompt_role = "manager" if role in ("manager", "user") else "assistant"
            conversation_history.append(
                {
                    "role": prompt_role,
                    "content": msg.get("content", ""),
                }
            )

        current_turn = {"role": "manager", "content": user_message}

        if self._template_manager is not None:
            return self._template_manager(
                "initial",
                active_template_root_space="conversation",
                conversation_history=conversation_history,
                current_turn=current_turn,
                # Workflow variables not passed — template guards with {% if defined %}
            )

        # Fallback: raw Jinja2 rendering
        return self._render_fallback(conversation_history, current_turn)

    @classmethod
    def AVAILABLE_BACKENDS(cls) -> list[str]:
        """Names of all backends registered in the global registry.

        Used by run_server.py's --llm-backend choices and by the
        /api/server/backends meta route.
        """
        from openteam.server.backends import get_registry
        return list(get_registry().list_backends())

    # ── Workflow-controlled conversation ────────────────────────────

    def _get_session_inferencer(self, session_id: str, session: dict | None = None):
        """Get or create a per-session ConversationalInferencer.

        Effective backend/model precedence:
          1. ``session["llm_backend"]`` / ``session["llm_model"]`` (per-session)
          2. ``self._llm_backend`` / ``self._llm_model`` (server default)

        ``mock`` is fast-pathed: returns ``None`` so the caller streams
        canned responses via ``astream_response`` without consulting the
        registry. Any other backend dispatches through
        ``BackendRegistry.create()``.
        """
        from openteam.server.backends import BackendBuildContext, get_registry

        sess = session or {}
        backend = sess.get("llm_backend") or self._llm_backend
        model = sess.get("llm_model") or self._llm_model

        if backend == "mock":
            return None

        if session_id in self._inferencers:
            return self._inferencers[session_id]

        ctx = BackendBuildContext(
            templates_dir=self._templates_dir,
            working_dir=self._working_dir,
            cache_dir=self._cache_dir,
            session_store=self._session_store,
            model_name=model,
            session_id=session_id,
        )
        try:
            inferencer = get_registry().create(backend, ctx)
        except Exception as e:
            logger.error("Failed to build inferencer for backend %r: %s", backend, e)
            raise

        self._inferencers[session_id] = inferencer
        return inferencer

    def set_session_backend(
        self,
        session_id: str,
        backend: str,
        model: str | None = None,
    ) -> dict | None:
        """Set the per-session LLM backend (and optional model).

        Validates ``backend`` against the registry, persists via
        ``session_store.update_session``, and evicts any cached inferencer
        so the next turn rebuilds with the new choice.

        Returns the updated session dict, or ``None`` if the session is
        unknown or no session store is wired.
        """
        from openteam.server.backends import get_registry

        registered = get_registry().list_backends()
        if backend not in registered:
            available = ", ".join(sorted(registered)) or "(none)"
            raise KeyError(
                f"Unknown backend {backend!r}. Registered backends: {available}"
            )

        # Evict cached inferencer so the next turn rebuilds with the new backend
        self._inferencers.pop(session_id, None)

        if self._session_store is None or not hasattr(
            self._session_store, "update_session"
        ):
            logger.warning(
                "set_session_backend(%s, %s): no session_store wired — "
                "in-memory eviction only", session_id, backend,
            )
            return None

        updates = {"llm_backend": backend, "llm_model": model}
        return self._session_store.update_session(session_id, updates)

    def evict_session_inferencer(self, session_id: str) -> None:
        """Free memory when a session is deleted."""
        self._inferencers.pop(session_id, None)

    def get_last_prompt_data(self, session_id: str) -> dict:
        """Return cached prompt data from the last turn for a given session.

        Reads _last_template_source, _last_template_feed, _last_rendered_prompt,
        _last_template_config from the ConversationalInferencer after run_agentic_loop().
        Returns empty dict if session has no inferencer or no data yet.

        The template_feed is sanitized — non-JSON-serializable objects (e.g. SOP,
        StateGraphTracker) that get spread into the feed via **prior_context are
        converted to their string representation or omitted.
        """
        inf = self._inferencers.get(session_id)
        if inf is None:
            # Fall back to mock prompt cache (populated by astream_response in mock mode)
            return self._mock_prompt_cache.get(session_id, {})
        return {
            "template_source": getattr(inf, "_last_template_source", "") or "",
            "template_feed": self._sanitize_feed(getattr(inf, "_last_template_feed", {}) or {}),
            "rendered_prompt": getattr(inf, "_last_rendered_prompt", "") or "",
            "template_config": getattr(inf, "_last_template_config", {}) or {},
        }

    @staticmethod
    def _sanitize_feed(feed: dict) -> dict:
        """Make template_feed JSON-serializable.

        The feed dict contains **prior_context spread, which includes non-JSON
        objects like SOP (from _sop key), StateGraphTracker, SOPPhase, etc.
        This method converts them to safe representations.
        """
        import json

        result = {}
        for key, value in feed.items():
            # Skip internal/private keys that are never useful for display
            if key.startswith("_"):
                continue
            try:
                # Test if value is JSON serializable
                json.dumps(value)
                result[key] = value
            except (TypeError, ValueError):
                # Convert non-serializable objects to string repr
                try:
                    result[key] = str(value)
                except Exception:
                    result[key] = f"<non-serializable: {type(value).__name__}>"
        return result

    def _compute_session_context(self, session: dict) -> dict:
        """Build prior_context dict from session workflow state — called once per turn."""
        from agent_foundation.server.workflow_context import WorkflowContext

        wc_dict = session.get("workflow_context", {})
        # Ensure workflow_description is non-empty before constructing
        # WorkflowContext — its __post_init__ tries a stale rankevolve
        # importlib path when workflow_description is falsy.
        if wc_dict:
            if not wc_dict.get("workflow_description"):
                wc_dict["workflow_description"] = self._load_workflow_description()
            wc = WorkflowContext.from_dict(wc_dict)
        else:
            wc = WorkflowContext(
                workflow_description=self._load_workflow_description()
            )

        return {
            "session_root_path": self._working_dir,
            "workflow_status": wc.to_status_text(),
            "workflow_description": wc.workflow_description,
            "strategy": wc.strategy,
            "current_phase": wc.current_phase,
            "phase_status": wc.phase_status,
            "completed_phases": wc.completed_phases,
            "phase_outputs": wc.phase_outputs,
        }

    def _load_workflow_description(self) -> str:
        """Load the default workflow description from prompt templates."""
        desc_file = (
            self._templates_dir
            / "conversation"
            / "main"
            / "_variables"
            / "workflow_description"
            / "default.jinja2"
        )
        return desc_file.read_text(encoding="utf-8") if desc_file.is_file() else ""

    def _persist_workflow_updates(
        self, session: dict, prior_context: dict, data_service: object | None
    ) -> None:
        """Persist updated workflow state from the inferencer's prior_context."""
        from agent_foundation.server.workflow_context import (
            WorkflowContext,
            WorkflowPhaseRecord,
        )

        # Rebuild from prior_context (inferencer's live state, updated in-place
        # by context_updates during the turn) — NOT from the stale session dict.
        completed_raw = prior_context.get("completed_phases", [])
        completed = []
        for r in completed_raw:
            if isinstance(r, WorkflowPhaseRecord):
                completed.append(r)
            elif isinstance(r, dict):
                completed.append(WorkflowPhaseRecord.from_dict(r))

        wc = WorkflowContext(
            strategy=prior_context.get("strategy", "default"),
            workflow_description=prior_context.get("workflow_description") or self._load_workflow_description(),
            current_phase=prior_context.get("current_phase", "idle"),
            phase_status=prior_context.get("phase_status", "idle"),
            completed_phases=completed,
            phase_outputs=prior_context.get("phase_outputs", {}),
        )

        if data_service and hasattr(data_service, "update_workflow_context"):
            data_service.update_workflow_context(session["id"], wc.to_dict())
        elif self._session_store and hasattr(self._session_store, "update_workflow_context"):
            self._session_store.update_workflow_context(session["id"], wc.to_dict())

    def _get_or_create_session_logger(self, session_id: str, data_service):
        """Lazily create the per-session JsonLogger.

        Adapts RankEvolve's pattern (python_utils.io_utils.json_io.JsonLogger
        configured with is_artifact + parts_min_size=0 + parts_file_namer) to
        OpenTeam's session layout, but bypasses RankEvolve's `SessionLogger`
        wrapper because it always creates a NEW nested subdirectory inside the
        passed `base_log_dir` — incompatible with our existing session dirs.
        """
        if session_id in self._session_loggers:
            return self._session_loggers[session_id]
        if data_service is None or not hasattr(data_service, "get_session_dir"):
            return None
        session_dir = data_service.get_session_dir(session_id)
        if session_dir is None:
            return None
        try:
            from python_utils.io_utils.json_io import JsonLogger
        except ImportError:
            logger.debug("JsonLogger not available; skipping structured session logging")
            return None
        json_logger = JsonLogger(
            file_path=str(session_dir / "session.jsonl"),
            append=True,
            parts_min_size=0,            # all fields → parts/ files (matches RankEvolve)
            is_artifact=True,            # auto-sets parts_key_paths='*'
            parts_file_namer=lambda obj: obj.get("type", "") if isinstance(obj, dict) else "",
            # space_ext_mode omitted: only affects space= param, not group=/subfolder=
        )
        self._session_loggers[session_id] = json_logger
        return json_logger

    async def run_conversation_turn(
        self, session: dict, user_message: str, *, interactive, data_service=None
    ):
        """Run a full conversation turn with workflow-controlled agentic loop.

        Unlike astream_response() (async generator yielding chunks),
        this returns AgenticResult after run_agentic_loop() completes.
        Streaming happens inside run_agentic_loop() via interactive.stream_token_batches().
        """
        inferencer = self._get_session_inferencer(session["id"])
        if inferencer is None:
            raise RuntimeError("ConversationalInferencer not initialized")

        # Inject per-turn interactive into the dispatcher so async tools (create_role,
        # role_setup) can send task_status WS messages and spawn background tasks.
        if hasattr(inferencer, "_tool_dispatcher"):
            inferencer._tool_dispatcher._interactive = interactive

        # Inject workflow state as prior_context
        session_ctx = self._compute_session_context(session)
        inferencer.set_prior_context(session_ctx)

        # Sync conversation history
        conv_messages = [
            {
                "role": "user" if m.get("role") in ("manager", "user") else "assistant",
                "content": m.get("content", ""),
            }
            for m in session.get("messages", [])
        ]
        inferencer.set_messages(conv_messages)

        # ── RankEvolve-style structured logging setup ─────────────────────
        # Get/create per-session JsonLogger; compute initial turn number from
        # what's already on disk; track the current turn so we can save data
        # for both intermediate iterations (via on_new_turn) and the final turn.
        sid = session["id"]
        json_logger = self._get_or_create_session_logger(sid, data_service)
        session_dir = (
            data_service.get_session_dir(sid)
            if data_service is not None and hasattr(data_service, "get_session_dir")
            else None
        )

        # Count existing turn directories. Prefer new-style (turn_NNN/ at root,
        # RankEvolve layout); fall back to legacy nested (turns/turn_NNN/).
        initial_turn = 0
        if session_dir is not None:
            new_style = sum(
                1 for p in session_dir.iterdir()
                if p.is_dir() and p.name.startswith("turn_") and p.name != "turns"
            )
            if new_style > 0:
                initial_turn = new_style
            else:
                legacy_dir = session_dir / "turns"
                if legacy_dir.is_dir():
                    initial_turn = sum(
                        1 for p in legacy_dir.iterdir()
                        if p.is_dir() and p.name.startswith("turn_")
                    )

        current_turn = [initial_turn]                # 1-based after first increment
        last_widget_response: list[Any] = [None]      # tracked for final-turn user_input

        # ── on_new_turn callback (fires between agentic-loop iterations) ──
        # When the inferencer hands control back to the user (widget, free-text),
        # the previous iteration's prompt+response is now complete. We:
        #   1) Log the per-turn artifacts to JSONL (PromptTemplate, RenderedPrompt, …)
        #   2) Save turn.json via save_turn_data so REST View Prompt works
        #   3) Update WebSocketInteractive._last_prompt_data so the NEXT preamble
        #      message can carry inline prompt_data
        #   4) Point the inferencer's cache_folder at the next turn's directory
        #      so streaming cache files (stream_*.txt) co-locate with that turn.
        # Returns the new turn number (1-based) so the inferencer can use it for
        # its own per-turn output paths if it wants.
        #
        # NOTE: Must be `async def` — `run_agentic_loop` calls this with `await`
        # (see conversational_inferencer.py: `new_turn = await on_new_turn(...)`).
        # All work inside is synchronous (file I/O via JsonLogger, save_turn_data),
        # but the function signature must be a coroutine. We don't actually need
        # any `await` calls inside; making it `async` simply ensures the returned
        # value is a coroutine object that can be awaited.
        async def _on_new_turn(prev_turn: int, widget_response: Any) -> int:
            last_widget_response[0] = widget_response
            new_turn = (prev_turn or 0) + 1
            current_turn[0] = new_turn

            import json as _json
            # 1) Per-turn JSONL records (RankEvolve-style, group= → subfolder)
            if json_logger is not None:
                _grp = f"turn_{new_turn:03d}"
                try:
                    if widget_response is not None:
                        json_logger(
                            {"type": "UserInput", "item": str(widget_response)},
                            group=_grp, parts_key_path_root="item",
                        )
                    if getattr(inferencer, "_last_template_source", None):
                        json_logger(
                            {"type": "PromptTemplate",
                             "item": inferencer._last_template_source},
                            group=_grp, parts_key_path_root="item",
                        )
                    if getattr(inferencer, "_last_rendered_prompt", None):
                        json_logger(
                            {"type": "RenderedPrompt",
                             "item": inferencer._last_rendered_prompt},
                            group=_grp, parts_key_path_root="item",
                        )
                    if getattr(inferencer, "_last_template_feed", None):
                        json_logger(
                            {"type": "TemplateFeed",
                             "item": _json.dumps(inferencer._last_template_feed,
                                                  indent=2, ensure_ascii=False, default=str)},
                            group=_grp, parts_key_path_root="item",
                        )
                    if getattr(inferencer, "_last_template_config", None):
                        json_logger(
                            {"type": "TemplateConfig",
                             "item": _json.dumps(inferencer._last_template_config,
                                                  indent=2, ensure_ascii=False, default=str)},
                            group=_grp, parts_key_path_root="item",
                        )
                    json_logger(
                        {"type": "ApiPayload",
                         "item": _json.dumps({
                             # ConversationalInferencer exposes system_prompt as a property
                             # (→ base_inferencer.system_prompt), same concept as
                             # RankEvolve's conversation.system_prompt.
                             "system_prompt": getattr(inferencer, "system_prompt", "") or "",
                             # Use _messages (live state, updated via add_message() throughout
                             # the loop) — NOT session["messages"] (a snapshot from turn start).
                             "messages": list(getattr(inferencer, "_messages", [])),
                         }, indent=2, ensure_ascii=False, default=str)},
                        group=_grp, parts_key_path_root="item",
                    )
                    # InferenceResponse: empty placeholder for the widget-interrupted
                    # iteration; the LLM didn't fully respond (handed off to the user).
                    json_logger(
                        {"type": "InferenceResponse", "item": ""},
                        group=_grp, parts_key_path_root="item",
                    )
                except Exception as e:
                    logger.debug("[_on_new_turn] JSONL logging failed: %s", e)

            # 2) save_turn_data so REST View Prompt has turn.json available
            if data_service is not None and hasattr(data_service, "save_turn_data"):
                prompt_data = self.get_last_prompt_data(sid) or {}
                if widget_response is not None:
                    prompt_data["user_input"] = str(widget_response)
                try:
                    data_service.save_turn_data(sid, new_turn, prompt_data)
                except Exception as e:
                    logger.debug("[_on_new_turn] save_turn_data failed: %s", e)

                # 3) Refresh the interactive's inline prompt_data cache so the next
                # preamble carries the latest rendered prompt without a REST round-trip.
                if hasattr(interactive, "_last_prompt_data"):
                    interactive._last_prompt_data = prompt_data

            # 4) Co-locate the next turn's streaming cache with its directory
            if session_dir is not None and hasattr(inferencer, "cache_folder"):
                try:
                    next_turn_dir = session_dir / f"turn_{(new_turn + 1):03d}"
                    next_turn_dir.mkdir(parents=True, exist_ok=True)
                    inferencer.cache_folder = str(next_turn_dir)
                except Exception as e:
                    logger.debug("[_on_new_turn] cache_folder rotation failed: %s", e)

            return new_turn

        # Set up cache_folder for the very first turn before the loop starts.
        if session_dir is not None and hasattr(inferencer, "cache_folder"):
            try:
                first_turn_dir = session_dir / f"turn_{(initial_turn + 1):03d}"
                first_turn_dir.mkdir(parents=True, exist_ok=True)
                inferencer.cache_folder = str(first_turn_dir)
            except Exception as e:
                logger.debug("Initial cache_folder setup failed: %s", e)

        # Run the full agentic loop
        result = await inferencer.run_agentic_loop(
            user_message,
            interactive=interactive,
            session_id=sid,
            on_new_turn=_on_new_turn,
            turn_number=initial_turn,
        )

        # ── Final-turn logging (after the loop returns) ──────────────────
        # The last iteration's prompt+response don't go through on_new_turn
        # because there's no "next turn" handoff. Capture them here.
        final_turn = current_turn[0] + 1
        # Stash on result so manager_websocket_routes can use it as the canonical
        # turn number (avoids the off-by-one recomputation).
        try:
            result.turn_number = final_turn  # type: ignore[attr-defined]
        except Exception:
            pass

        if json_logger is not None:
            import json as _json
            _grp = f"turn_{final_turn:03d}"
            try:
                # The final turn's user_input is the most recent widget response
                # (from the last on_new_turn iteration), or the original message
                # if no widget interactions happened.
                _user_input = last_widget_response[0] if last_widget_response[0] is not None else user_message
                json_logger(
                    {"type": "UserInput", "item": str(_user_input)},
                    group=_grp, parts_key_path_root="item",
                )
                if getattr(result, "last_template_source", None):
                    json_logger(
                        {"type": "PromptTemplate", "item": result.last_template_source},
                        group=_grp, parts_key_path_root="item",
                    )
                if getattr(result, "last_rendered_prompt", None):
                    json_logger(
                        {"type": "RenderedPrompt", "item": result.last_rendered_prompt},
                        group=_grp, parts_key_path_root="item",
                    )
                if getattr(result, "last_template_feed", None):
                    json_logger(
                        {"type": "TemplateFeed",
                         "item": _json.dumps(result.last_template_feed,
                                              indent=2, ensure_ascii=False, default=str)},
                        group=_grp, parts_key_path_root="item",
                    )
                if getattr(result, "last_template_config", None):
                    json_logger(
                        {"type": "TemplateConfig",
                         "item": _json.dumps(result.last_template_config,
                                              indent=2, ensure_ascii=False, default=str)},
                        group=_grp, parts_key_path_root="item",
                    )
                json_logger(
                    {"type": "ApiPayload",
                     "item": _json.dumps({
                         "system_prompt": getattr(inferencer, "system_prompt", "") or "",
                         "messages": list(getattr(inferencer, "_messages", [])),
                     }, indent=2, ensure_ascii=False, default=str)},
                    group=_grp, parts_key_path_root="item",
                )
                json_logger(
                    {"type": "InferenceResponse",
                     "item": getattr(result, "raw_response", "") or ""},
                    group=_grp, parts_key_path_root="item",
                )
            except Exception as e:
                logger.debug("[run_conversation_turn] final-turn JSONL logging failed: %s", e)

        # save_turn_data for the final turn (REST View Prompt support)
        if data_service is not None and hasattr(data_service, "save_turn_data"):
            try:
                prompt_data = self.get_last_prompt_data(sid) or {}
                _user_input = last_widget_response[0] if last_widget_response[0] is not None else user_message
                prompt_data["user_input"] = str(_user_input)
                data_service.save_turn_data(sid, final_turn, prompt_data)
                if hasattr(interactive, "_last_prompt_data"):
                    interactive._last_prompt_data = prompt_data
            except Exception as e:
                logger.debug("Final-turn save_turn_data failed: %s", e)

        # Persist updated workflow context
        self._persist_workflow_updates(session, inferencer.prior_context, data_service)

        return result

    async def astream_response(self, session: dict, user_message: str):
        """Stream response tokens for the user's message.

        Yields individual text chunks. For mock backend, simulates streaming
        by yielding word-by-word. For rovodev backend, streams real LLM output
        line-by-line from ``acli rovodev run``.

        The caller is responsible for persisting messages — this method
        only renders the prompt, calls the LLM, and yields chunks.
        """
        if self._llm_backend == "mock":
            rendered_prompt = self.render_prompt(session, user_message)
            raw_response = self._mock_response(user_message)
            parsed = self._parse_response(raw_response)
            # Cache prompt data so get_last_prompt_data() works in mock mode
            sid = session.get("id", "")
            self._mock_prompt_cache[sid] = {
                "template_source": "(mock mode — no Jinja2 template rendered)",
                "template_feed": {"user_message": user_message},
                "rendered_prompt": rendered_prompt,
                "template_config": {"backend": "mock"},
            }
            # Simulate streaming: yield word-by-word with tiny delays
            words = parsed.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == 0 else " " + word
                yield chunk
                await asyncio.sleep(0.03)  # 30ms per word — feels natural

        else:
            # Generic agentic-backend path: any registered non-mock backend.
            # Safety fallback only — the WS route prefers run_conversation_turn().
            inferencer = self._get_session_inferencer(session["id"], session=session)
            if inferencer is None:
                raise RuntimeError(
                    f"No inferencer registered for backend {self._llm_backend!r}. "
                    f"Available: {', '.join(sorted(self.AVAILABLE_BACKENDS()))}"
                )

            # Sync conversation history from session into the inferencer
            messages = session.get("messages", [])
            conv_messages = []
            for msg in messages:
                role = msg.get("role", "manager")
                prompt_role = "user" if role in ("manager", "user") else "assistant"
                conv_messages.append(
                    {"role": prompt_role, "content": msg.get("content", "")}
                )
            inferencer.set_messages(conv_messages)

            # Stream via base ainfer_streaming() — NOTE: this bypasses run_agentic_loop(),
            # so workflow context, SOP, and tools are NOT active in this path.
            # Prefer run_conversation_turn() for full workflow-controlled streaming.
            full_response = ""
            async for chunk in inferencer.ainfer_streaming(user_message):
                chunk_str = str(chunk) if not isinstance(chunk, str) else chunk
                if chunk_str:
                    full_response += chunk_str
                    yield chunk_str

            inferencer.add_message("user", user_message)
            inferencer.add_message("assistant", full_response)

    async def get_response(self, session: dict, user_message: str) -> str:
        """Get an AI response for the user's message.

        1. Render prompt with session history
        2. Call LLM backend
        3. Parse <Response> tags from output
        4. Return cleaned response text
        """
        rendered_prompt = self.render_prompt(session, user_message)

        if self._llm_backend == "mock":
            raw_response = self._mock_response(user_message)
        else:
            raw_response = await self._call_llm(rendered_prompt)

        return self._parse_response(raw_response)

    def _mock_response(self, user_message: str) -> str:
        """Generate a mock response for testing without an LLM."""
        return (
            f"<Response>\n"
            f'I received your message: "{user_message}"\n\n'
            f"As the Orchestrator, I can help you with team management, "
            f"project oversight, task coordination, and more. "
            f"This is currently running in mock mode — connect an LLM backend "
            f"to enable full AI conversations.\n"
            f"</Response>"
        )

    async def _call_llm(self, rendered_prompt: str) -> str:
        """Single-shot prompt path (legacy ``get_response``).

        Real backends are reached through ``_get_session_inferencer`` +
        ``run_conversation_turn`` / ``astream_response``. This single-shot
        path has no caller for non-mock backends and is intentionally not
        implemented.
        """
        raise RuntimeError(
            f"No single-shot inferencer for backend {self._llm_backend!r}. "
            f"Available backends: {', '.join(sorted(self.AVAILABLE_BACKENDS()))}. "
            f"Use astream_response() or run_conversation_turn() instead."
        )

    @staticmethod
    def _parse_response(raw_output: str) -> str:
        """Extract content from <Response>...</Response> tags.

        Uses the LAST match (not first), matching rankevolve's extract_delimited()
        behavior — handles cases where the LLM outputs multiple attempts.
        Falls back to full output if no tags found (graceful degradation).
        """
        matches = re.findall(r"<Response>(.*?)</Response>", raw_output, re.DOTALL)
        if matches:
            return matches[-1].strip()  # Last match — final attempt
        # No tags — return full output (may happen with some LLM backends)
        return raw_output.strip()

    def _render_fallback(self, conversation_history: list, current_turn: dict) -> str:
        """Fallback rendering when TemplateManager is not available.

        Uses raw Jinja2 to render the conversation template directly.
        """
        from jinja2 import Environment, FileSystemLoader

        template_dir = self._templates_dir / "conversation" / "main"
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            undefined=__import__("jinja2").Undefined,  # silent undefined
        )
        template = env.get_template("initial.jinja2")
        return template.render(
            conversation_history=conversation_history,
            current_turn=current_turn,
        )
