# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""RankEvolve session manager — creates and manages agent sessions."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from attr import attrib, attrs
from agent_foundation.ui.queue_interactive import (
    QueueInteractive,
)
from rankevolve.src.server.config import AppConfig, load_config
from rankevolve.src.server.conversation import Conversation
from rankevolve.src.server.factories import create_llm_client, create_sync_inferencer
from rankevolve.src.server.shared_loader import load_system_prompt
from rankevolve.src.server.workflow_context import WorkflowContext
from rich_python_utils.common_objects.debuggable import LoggerConfig
from rankevolve.src.utils.io_utils.json_io import JsonLogger, SpaceExtMode
from rankevolve.src.utils.service_utils.queue_service.queue_service_base import (
    QueueServiceBase,
)
from rankevolve.src.utils.service_utils.session_management.session_base import (
    SessionBase,
)
from rankevolve.src.utils.service_utils.session_management.session_info import (
    SessionInfo,
)
from rankevolve.src.utils.service_utils.session_management.session_logger import (
    SessionLogger,
)
from rankevolve.src.utils.service_utils.session_management.session_manager import (
    SessionManager,
)

from .config import RankEvolveServiceConfig
from .session import RankEvolveSession
from .session_info import RankEvolveSessionInfo

logger = logging.getLogger(__name__)


@attrs(slots=False)
class RankEvolveSessionManager(SessionManager):
    """Creates and manages RankEvolve agent sessions.

    Each session gets its own LLM client, conversation, QueueInteractive
    (with per-session input/response queues), and optionally a KnowledgeBridge.
    """

    _queue_service: QueueServiceBase = attrib(kw_only=True)
    _service_config: RankEvolveServiceConfig = attrib(kw_only=True)

    def get_or_create(
        self, session_id: str, session_type: str | None = None, **kwargs: Any
    ) -> SessionBase:
        """Get existing session, restore from disk, or create new.

        Extends the base get_or_create to check for persisted session state
        on disk before creating a brand new session. This prevents empty
        duplicate directories when a session reconnects after idle cleanup.
        """
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]

            # Check disk for persisted state (idle-cleaned but restorable)
            if self._service_log_dir:
                prefix = f"{session_id}_"
                for subdir in sorted(self._service_log_dir.iterdir(), reverse=True):
                    if not subdir.name.startswith(prefix):
                        continue
                    state_file = subdir / "session_state.json"
                    if not state_file.is_file():
                        continue
                    try:
                        data = json.loads(state_file.read_text(encoding="utf-8"))
                        if data.get("status") == "closed":
                            continue
                        session = self._restore_session(state_file, data)
                        self._sessions[session_id] = session
                        logger.info(
                            "Re-restored session %s from disk (was idle-cleaned)",
                            session_id,
                        )
                        return session
                    except Exception as e:
                        logger.warning("Failed to re-restore %s: %s", session_id, e)

            # No disk state — create fresh
            session = self._create_session(
                session_id, session_type or "webui", **kwargs
            )
            self._sessions[session_id] = session
            self.log_info(
                {
                    "type": self._get_log_type_session_management(),
                    "message": f"Session created: {session_id}",
                    "session_type": session_type,
                }
            )
            return session

    def _create_session(
        self, session_id: str, session_type: str, **kwargs: Any
    ) -> SessionBase:
        """Create a new RankEvolve session with all infrastructure."""
        now = time.time()

        # Session info
        info = RankEvolveSessionInfo(
            session_id=session_id,
            created_at=now,
            last_active=now,
            session_type=session_type or "rankevolve",
            model=self._service_config.model,
            session_root_path=self._service_config.session_root_path,
            provider=self._service_config.provider,
        )

        # Session logger
        log_dir = self._service_log_dir or Path("rankevolve/_runtime/sessions")
        session_logger = SessionLogger(
            base_log_dir=log_dir,
            session_id=session_id,
            session_type=session_type or "rankevolve",
        )

        # App config (session-scoped copy)
        app_config = load_config()
        app_config.model = self._service_config.model
        app_config.provider = self._service_config.provider

        # Conversation
        system_prompt = load_system_prompt(app_config.system_prompt_file)
        conversation = Conversation(system_prompt)

        # LLM client
        llm_client = create_llm_client(app_config)

        # Per-session queues
        input_queue_id = f"{self._service_config.input_queue_id}_{session_id}"
        response_queue_id = f"{self._service_config.response_queue_id}_{session_id}"
        self._queue_service.create_queue(input_queue_id)
        self._queue_service.create_queue(response_queue_id)

        # QueueInteractive for this session
        interactive = QueueInteractive(
            system_name="RankEvolve",
            user_name="User",
            input_queue=self._queue_service,
            response_queue=self._queue_service,
            input_queue_id=input_queue_id,
            response_queue_id=response_queue_id,
            blocking=False,
            timeout=0.1,
        )

        # Knowledge bridge (optional)
        knowledge_bridge = None
        if self._service_config.enable_knowledge:
            try:
                from rankevolve.src.server.knowledge_bridge import KnowledgeBridge

                inferencer = create_sync_inferencer(llm_client, app_config)
                knowledge_bridge = KnowledgeBridge(inferencer=inferencer)
                logger.info("Knowledge bridge initialized for session %s", session_id)
            except Exception as e:
                logger.warning(
                    "Knowledge bridge unavailable for session %s: %s", session_id, e
                )

        # Set up JsonLogger for per-turn artifact logging (prompt, response, etc.)
        chat_json_logger = JsonLogger(
            file_path=str(session_logger.session_dir / "session.jsonl"),
            append=True,
            is_artifact=True,
            parts_min_size=0,
            space_ext_mode=SpaceExtMode.MOVE,
            parts_file_namer=lambda obj: obj.get("type", "")
            if isinstance(obj, dict)
            else "",
        )
        session_logger.add_turn_aware_logger(chat_json_logger)

        # Logger pair for inferencer wiring
        logger_pair = (
            session_logger,
            LoggerConfig(pass_item_key_as="parts_key_path_root"),
        )

        # Conversation inferencer (provider-based API inferencer for agentic chat)
        conversation_inferencer = None
        tool_registry = None
        try:
            from rankevolve.src.resources.tools.registry import load_all_tools

            base_inferencer = self._create_base_inferencer(
                app_config,
                session_id,
                session_logger,
                logger_pair,
            )

            from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational import (
                ConversationalInferencer,
            )
            from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.prompt_rendering import (
                JinjaPromptRenderer,
            )

            tool_registry = load_all_tools()

            # Create prompt renderer
            from pathlib import Path as _Path

            _template_dir = (
                _Path(__file__).resolve().parent.parent.parent
                / "resources"
                / "prompt_templates"
            )
            prompt_renderer = JinjaPromptRenderer(str(_template_dir))

            conversation_inferencer = ConversationalInferencer(
                base_inferencer=base_inferencer,
                interactive=interactive,
                tool_registry=tool_registry,
                prompt_renderer=prompt_renderer,
            )
            logger.info(
                "Conversation inferencer initialized for session %s", session_id
            )
        except Exception as e:
            logger.warning(
                "Conversation inferencer unavailable for session %s: %s",
                session_id,
                e,
            )

        # Wire loggers to conversation inferencer (for RenderedPrompt logging)
        if conversation_inferencer is not None:
            conversation_inferencer.logger = [logger_pair]
            conversation_inferencer._normalize_loggers()

            if hasattr(conversation_inferencer, "base_inferencer"):
                conversation_inferencer.base_inferencer.logger = [logger_pair]
                conversation_inferencer.base_inferencer._normalize_loggers()
                conversation_inferencer.base_inferencer.log_level = logging.DEBUG

        session = RankEvolveSession(
            info=info,
            session_logger=session_logger,
            interactive=interactive,
            llm_client=llm_client,
            conversation=conversation,
            app_config=app_config,
            knowledge_bridge=knowledge_bridge,
            conversation_inferencer=conversation_inferencer,
            tool_registry=tool_registry,
        )
        # Load default workflow description
        session.workflow_context.set_strategy("default")

        info.initialized = True
        self.persist_session_state(session)
        return session

    def _on_before_cleanup(self, session: SessionBase) -> None:
        """Cancel active tasks and persist final state before session cleanup.

        Persists as 'idle' (not 'closed') so the session can be restored on
        server restart via --resume-last-server. Only explicit user action
        (e.g., /close-session) should set status to 'closed'.
        """
        if isinstance(session, RankEvolveSession):
            if session.active_task and not session.active_task.done():
                session.active_task.cancel()
                logger.info("Cancelled active task for session %s", session.session_id)
            if session.knowledge_bridge is not None:
                try:
                    session.knowledge_bridge.close()
                except Exception:
                    pass
            self.persist_session_state(session, status="idle")

    def _create_base_inferencer(
        self,
        app_config: AppConfig,
        session_id: str,
        session_logger: SessionLogger,
        logger_pair: tuple,
    ) -> Any:
        """Create a provider-based API inferencer with streaming support.

        Returns a MetagenApiInferencer or PlugboardApiInferencer (both extend
        StreamingInferencerBase), configured with caching, logging, and idle timeout.
        """
        if app_config.provider == "plugboard":
            from rankevolve.src.agentic_foundation.common.inferencers.api_inferencers.plugboard.plugboard_api_inferencer import (
                PlugboardApiInferencer,
            )

            return PlugboardApiInferencer(
                model_id=app_config.model,
                max_tokens=app_config.max_tokens,
                temperature=app_config.temperature,
                pipeline=app_config.pipeline,
                model_pipeline_overrides=app_config.model_pipeline_overrides or {},
                cache_folder=str(session_logger.session_dir),
                idle_timeout_seconds=600,
                id=f"chat_{session_id}",
                logger=[logger_pair],
            )
        else:
            from rankevolve.src.agentic_foundation.common.inferencers.api_inferencers.metagen.metagen_api_inferencer import (
                MetagenApiInferencer,
            )

            return MetagenApiInferencer(
                model_id=app_config.model,
                max_tokens=app_config.max_tokens,
                temperature=app_config.temperature,
                cache_folder=str(session_logger.session_dir),
                idle_timeout_seconds=600,
                id=f"chat_{session_id}",
                logger=[logger_pair],
            )

    def persist_session_state(
        self,
        session: SessionBase,
        status: str = "active",
        change_types: list[str] | None = None,
    ) -> None:
        """Persist session state to disk for crash recovery.

        Writes session_state.json into the session's log directory using
        atomic writes (write to .tmp then os.replace) to prevent corruption
        if the server crashes mid-write.

        After writing, sends a lightweight notification on the response queue
        so connected clients know to re-read the store.

        Args:
            session: The session to persist.
            status: Session status string ("active" or "closed").
            change_types: What changed, e.g. ["config"], ["content"], ["status"].
        """
        if not isinstance(session, RankEvolveSession):
            return
        with self._lock:
            try:
                session_dir = session.session_logger.session_dir
                state = {
                    "info": session.info.to_dict(),
                    "conversation": (
                        session.conversation.to_dict() if session.conversation else None
                    ),
                    "app_config": (
                        session.app_config.to_dict() if session.app_config else None
                    ),
                    "workflow_context": session.workflow_context.to_dict(),
                    "status": status,
                }

                state_path = session_dir / "session_state.json"
                tmp_path = session_dir / "session_state.json.tmp"
                tmp_path.write_text(
                    json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                os.replace(str(tmp_path), str(state_path))
                # Update the sessions index for fast listing
                self._write_sessions_index()
            except Exception as e:
                logger.warning(
                    "Failed to persist session state for %s: %s",
                    session.session_id,
                    e,
                )

        # Send lightweight notification (best-effort, outside lock)
        if isinstance(session, RankEvolveSession) and session.interactive:
            try:
                session.interactive._send_response(
                    {
                        "type": "session_notification",
                        "session_id": session.session_id,
                        "change_types": change_types or ["state"],
                        "timestamp": time.time(),
                    }
                )
            except Exception:
                pass  # Best-effort; file store is the source of truth

    def _write_sessions_index(self) -> None:
        """Write sessions_index.json listing all active sessions.

        This lightweight index file enables fast session listing without
        scanning individual session directories. Uses atomic writes.

        Must be called under self._lock.
        """
        if self._service_log_dir is None:
            return
        try:
            sessions = self.get_all_sessions()
            index = {
                "sessions": [
                    {
                        "session_id": sid,
                        "session_type": getattr(s.info, "session_type", ""),
                        "model": getattr(s.info, "model", ""),
                        "target_path": getattr(s.info, "session_root_path", ""),
                        "provider": getattr(s.info, "provider", ""),
                        "status": "active",
                        "created_at": getattr(s.info, "created_at", 0),
                        "last_active": getattr(s.info, "last_active", 0),
                    }
                    for sid, s in sessions.items()
                ],
                "updated_at": time.time(),
            }
            index_path = self._service_log_dir / "sessions_index.json"
            tmp_path = index_path.with_suffix(".json.tmp")
            tmp_path.write_text(
                json.dumps(index, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(str(tmp_path), str(index_path))
        except Exception as e:
            logger.debug("Failed to write sessions_index.json: %s", e)

    def _restore_session(
        self, session_state_path: Path, data: dict[str, Any]
    ) -> SessionBase:
        """Restore a session from a persisted session_state.json file.

        Args:
            session_state_path: Path to the session_state.json file.
            data: Already-parsed contents of the session_state.json file.

        Returns:
            A fully reconstructed RankEvolveSession.
        """

        # Reconstruct session info
        info = RankEvolveSessionInfo.from_dict(data["info"])
        # Clear active_task_id since the task no longer exists
        info.active_task_id = None
        info.initialized = True
        # Reset last_active to prevent immediate idle-timeout cleanup
        info.last_active = time.time()

        # Reconstruct session logger from existing directory
        session_dir = session_state_path.parent
        session_logger = SessionLogger.from_existing(session_dir)

        # Reconstruct app config
        app_config = None
        if data.get("app_config"):
            app_config = AppConfig.from_dict(data["app_config"])

        # Reconstruct conversation
        conversation = None
        if data.get("conversation"):
            conversation = Conversation.from_dict(data["conversation"])

        # Recreate LLM client
        llm_client = None
        if app_config:
            llm_client = create_llm_client(app_config)

        # Re-register per-session queues and recreate QueueInteractive
        input_queue_id = f"{self._service_config.input_queue_id}_{info.session_id}"
        response_queue_id = (
            f"{self._service_config.response_queue_id}_{info.session_id}"
        )
        self._queue_service.create_queue(input_queue_id)
        self._queue_service.create_queue(response_queue_id)

        interactive = QueueInteractive(
            system_name="RankEvolve",
            user_name="User",
            input_queue=self._queue_service,
            response_queue=self._queue_service,
            input_queue_id=input_queue_id,
            response_queue_id=response_queue_id,
            blocking=False,
            timeout=0.1,
        )

        # Optionally recreate knowledge bridge
        knowledge_bridge = None
        if self._service_config.enable_knowledge and llm_client and app_config:
            try:
                from rankevolve.src.server.knowledge_bridge import KnowledgeBridge

                inferencer = create_sync_inferencer(llm_client, app_config)
                knowledge_bridge = KnowledgeBridge(inferencer=inferencer)
            except Exception as e:
                logger.warning(
                    "Knowledge bridge unavailable for restored session %s: %s",
                    info.session_id,
                    e,
                )

        # Set up JsonLogger for per-turn artifact logging
        chat_json_logger = JsonLogger(
            file_path=str(session_logger.session_dir / "session.jsonl"),
            append=True,
            is_artifact=True,
            parts_min_size=0,
            space_ext_mode=SpaceExtMode.MOVE,
            parts_file_namer=lambda obj: obj.get("type", "")
            if isinstance(obj, dict)
            else "",
        )
        session_logger.add_turn_aware_logger(chat_json_logger)

        # Logger pair for inferencer wiring
        logger_pair = (
            session_logger,
            LoggerConfig(pass_item_key_as="parts_key_path_root"),
        )

        # Recreate conversation inferencer and tool registry
        conversation_inferencer = None
        tool_registry = None
        try:
            from rankevolve.src.resources.tools.registry import load_all_tools

            base_inferencer = self._create_base_inferencer(
                app_config,
                info.session_id,
                session_logger,
                logger_pair,
            )

            from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational import (
                ConversationalInferencer,
            )
            from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.prompt_rendering import (
                JinjaPromptRenderer,
            )

            tool_registry = load_all_tools()

            from pathlib import Path as _Path

            _template_dir = (
                _Path(__file__).resolve().parent.parent.parent
                / "resources"
                / "prompt_templates"
            )
            prompt_renderer = JinjaPromptRenderer(str(_template_dir))

            conversation_inferencer = ConversationalInferencer(
                base_inferencer=base_inferencer,
                interactive=interactive,
                tool_registry=tool_registry,
                prompt_renderer=prompt_renderer,
            )
        except Exception as e:
            logger.warning(
                "Conversation inferencer unavailable for restored session %s: %s",
                info.session_id,
                e,
            )

        # Wire loggers to conversation inferencer
        if conversation_inferencer is not None:
            conversation_inferencer.logger = [logger_pair]
            conversation_inferencer._normalize_loggers()

            if hasattr(conversation_inferencer, "base_inferencer"):
                conversation_inferencer.base_inferencer.logger = [logger_pair]
                conversation_inferencer.base_inferencer._normalize_loggers()
                conversation_inferencer.base_inferencer.log_level = logging.DEBUG

        # Restore workflow context (backward-compatible: missing key -> fresh context)
        workflow_context = WorkflowContext()
        if "workflow_context" in data:
            workflow_context = WorkflowContext.from_dict(data["workflow_context"])
        # Ensure workflow_description is populated (handles old sessions)
        if not workflow_context.workflow_description:
            workflow_context.set_strategy(workflow_context.strategy)

        # Layer 2: reconcile task_queue against on-disk task workspaces.
        # The persisted task_queue may be stale (statuses captured at the
        # last persist event, which historically fired infrequently). Disk
        # truth — presence of `results/implementation_consensus_summary.json`
        # — is authoritative for determining completion.
        # Per-session layout: tasks live at <session_dir>/tasks/. The
        # restoring session's directory is `session_state_path.parent`
        # (= the session_dir built by SessionLogger.from_existing above).
        try:
            from rankevolve.src.server.hub_state import reconcile_task_queue_with_disk

            tasks_dir = session_dir / "tasks"
            changed = reconcile_task_queue_with_disk(workflow_context, tasks_dir)
            if changed:
                logger.info(
                    "Session %s: reconciled %d task_queue entries from disk",
                    info.session_id,
                    changed,
                )
        except Exception as e:
            logger.warning(
                "Session %s: task_queue reconciliation failed: %s",
                info.session_id,
                e,
            )

        session = RankEvolveSession(
            info=info,
            session_logger=session_logger,
            interactive=interactive,
            llm_client=llm_client,
            conversation=conversation,
            app_config=app_config,
            knowledge_bridge=knowledge_bridge,
            conversation_inferencer=conversation_inferencer,
            tool_registry=tool_registry,
            workflow_context=workflow_context,
        )

        logger.info("Restored session %s", info.session_id)
        return session

    def restore_sessions(self, session_log_dir: Path) -> None:
        """Restore sessions from previous run, then write sessions index.

        After restore, persist each session ONCE so that any changes made by
        Layer 2 reconciliation (status fixes, workspace fields filled in from
        disk) are written back to session_state.json. Future loads then read
        already-consistent state without re-running the disk scan.
        """
        super().restore_sessions(session_log_dir)
        with self._lock:
            self._write_sessions_index()
            # Persist each restored session so reconciled state lands on disk.
            # Cheap (~ms each); idempotent if nothing actually changed.
            for session_id, session in list(self._sessions.items()):
                try:
                    self.persist_session_state(session)
                except Exception as e:
                    logger.warning(
                        "Post-restore persist failed for session %s: %s",
                        session_id,
                        e,
                    )
