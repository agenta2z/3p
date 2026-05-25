"""DevMate CLI inferencer for executing DevMate CLI commands."""

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    TextIO,
    Union,
)

from attr import attrib, attrs
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.common import (
    InferencerExecutionError,
    MaxIterationsExhaustedError,
)


# ---------------------------------------------------------------------------
# Devmate-internal-failure detection
# ---------------------------------------------------------------------------
# Patterns indicating devmate's own daemon hit a fatal infrastructure issue
# (Iris/srproxy timeout, executor death, etc.) that does NOT propagate as a
# clean subprocess exit. Devmate hangs silently in these cases — its stdout
# pipe stays open (so our ``idle_timeout_seconds`` is evaded by heartbeats)
# and the only signal is errors written to the daemon's shared ``devmate.stderr``.
#
# When detected AND OUR cache file has been silent for >120s (confirming the
# failure affects OUR call, not just a concurrent session sharing the daemon),
# the watcher SHORTENS the call's deadline from ``total_timeout_seconds`` to
# ``total_timeout_on_internal_error_detection_seconds`` — a SOFT signal,
# not an immediate abort. Devmate may still self-recover within the shortened
# window. If it doesn't, the cancellation fires and the retry envelope kicks in.
#
# Pattern set is intentionally MINIMAL — only patterns we have direct evidence
# for being terminal in devmate (vs. transient warnings devmate self-recovers
# from). Adding more patterns over time is OK; removing is OK too.
_FATAL_DEVMATE_PATTERNS: List[re.Pattern] = [
    # StreamingMessageHandler executor died (no recovery path):
    re.compile(r"ERROR.*StreamingMessageHandler executor failure"),
    # Iris/srproxy publish timeout (52s+ recv timeout — fatal in observed cases):
    re.compile(r"RECV_TIMEOUT to .*srproxy\.titan\.prod"),
]

_DEVMATE_LOG_TAIL_BYTES: int = 200_000  # cap how much we read per scan
_INTERNAL_FAILURE_WATCHER_POLL_SECONDS: float = 60.0
# Cache-silence threshold for confirmation. If our own cache file has grown
# within this window, the matching log line is from another session sharing
# the daemon — don't shorten OUR deadline.
_INTERNAL_FAILURE_CACHE_SILENCE_THRESHOLD_SECONDS: float = 120.0

# Absolute path to the rankevolve-side ``freeform_agentic.md`` config (the
# one with shell/``execute_command`` enabled + the F5-bumped caps). Computed
# at module load time from this file's own location so it works regardless
# of which fbsource checkout rankevolve is running from.
#
# Why absolute (not fbsource-relative):
#   Devmate's resolver (``devai/config/loader/loader_utils.py``) walks up
#   from devmate's CWD to find ``fbsource_path``. When the rankevolve
#   server is launched with ``--session-root`` pointing into a DIFFERENT
#   fbsource checkout (e.g., ``fbs_cfr_dev``) than the one rankevolve
#   itself lives in (e.g., ``fbsource260327``), an fbsource-relative path
#   resolves against the WRONG tree — the file isn't there. An absolute
#   path bypasses that lookup entirely (resolver's step 1 is
#   ``os.path.exists(os.path.realpath(path))``).
#
# Pre-Apr 24 this was solved by ``sync_config_to_target(...)`` (in
# ``common.py:135``) which physically copied the .md from rankevolve's
# fbsource into the target's fbsource on every inferencer ``__init__``.
# That call was removed by the Apr 24 rename commit (``72e8378ddf40``),
# silently breaking custom-config loading whenever source-fbsource ≠
# target-fbsource. Using the absolute path here is the simpler, more
# durable fix.
_FREEFORM_AGENTIC_ABS_PATH: str = str(
    Path(__file__).resolve().parent / "configs" / "freeform_agentic.md"
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate.common import (
    SessionMode,
)
from rankevolve.src.agentic_foundation.common.inferencers.terminal_inferencers.terminal_session_inferencer_base import (
    TerminalSessionInferencerBase,
)

logger = logging.getLogger(__name__)

# Devmate's Rust CLI fails with `Failed to read port file ... os error 2`
# when the daemon hasn't yet finished writing devmate.port. The race window
# is bounded by daemon init (~1-3s), so a single short backoff before the
# existing max_retry envelope re-attempts is enough to ride through it.
_PORT_FILE_RACE_BACKOFF_SECONDS = 2.5


def _looks_like_port_file_race(error_text: str) -> bool:
    """True iff the error matches Devmate's port-file ENOENT cold-start race."""
    if not error_text:
        return False
    if "Failed to read port file" in error_text:
        return True
    et = error_text.lower()
    return "port" in et and "os error 2" in et


def _looks_like_max_iterations(error_text: str) -> bool:
    """True iff error matches Devmate's per-session MAX_ITERATIONS cap.

    Devmate enforces a per-session iteration budget. Default in the
    rankevolve-side ``freeform_agentic.md`` (rankevolve's default
    ``config_name``) is 500 after the F5 bump (was 200). The bundled
    devmate built-in ``freeform`` is 50 server-side, but rankevolve
    no longer defaults to it.
    The counter is per-session cumulative — calls reusing an existing
    session inherit the prior count. When exhausted, the session terminates
    with:
      "Session completed with non-successful exit code 'MAX_ITERATIONS':
       Max iterations of N reached"

    Recovery requires a fresh session — the iteration counter is per-session
    and cannot be reset within an existing session. The handler at
    ``_ainfer`` clears ``self.active_session_id`` so the next retry creates
    a fresh devmate session.

    Triple-AND substring check (false-positive prevention): all three
    substrings must be present to qualify, avoiding false-positives on
    other recoverable errors that happen to mention "iterations" or
    "reached".
    """
    if not error_text:
        return False
    return (
        "MAX_ITERATIONS" in error_text
        and "Max iterations of" in error_text
        and "reached" in error_text
    )


def _looks_like_tool_use_corruption(error_text: str) -> bool:
    """True iff the error indicates an Anthropic tool_use/tool_result mismatch.

    These errors mean the devmate session's conversation history has an
    orphan tool_use block (no matching tool_result) — typically caused
    upstream by a tool execution that timed out or was interrupted before
    its result could be appended. Resuming such a session will hit the same
    API rejection every time; recovery requires starting a fresh session.

    Match samples (verified against actual Anthropic error strings; the API
    uses backticks around `tool_use` / `tool_result`, NOT single quotes):
      - "messages.7: `tool_use` ids were found without `tool_result` blocks"
      - "tool_use_id ... does not match" (mismatched pairing)
      - "`tool_result` block(s) provided when previous message does not
         contain any `tool_use` blocks"
    """
    if not error_text:
        return False
    et = error_text.lower()
    return (
        ("`tool_use` ids were found without `tool_result`" in et)
        or ("tool_use_id" in et and "does not match" in et)
        or ("tool_result" in et and "does not contain" in et and "tool_use" in et)
    )


@attrs
class DevmateCliInferencer(TerminalSessionInferencerBase):
    """
    DevMate CLI inferencer for executing DevMate CLI commands.

    This inferencer wraps the `devmate` CLI tool to execute freeform prompts
    and other DevMate commands programmatically. Supports both sync and async
    operations with session continuation.

    Consistent Session API:
        This inferencer implements the unified session management API shared by
        all three external inferencers (ClaudeCodeInferencer, DevmateSDKInferencer,
        DevmateCliInferencer). The API includes:

        Attributes:
            auto_resume (bool): If True, automatically resume previous session.
                Default True.

        Properties:
            active_session_id: Get the current session ID for resumption.

        Session Methods (sync):
            new_session(prompt, **kwargs): Start a new session, clearing previous.
            resume_session(prompt, session_id=None, **kwargs): Resume a session.
            infer(prompt, **kwargs): Infer with auto-resume if enabled.
            infer_streaming(prompt, **kwargs): Sync streaming inference.

        Session Methods (async):
            anew_session(prompt, **kwargs): Async start new session.
            aresume_session(prompt, session_id=None, **kwargs): Async resume session.
            ainfer(prompt, **kwargs): Async infer with auto-resume.
            ainfer_streaming(prompt, **kwargs): Async streaming inference.

        Keyword Arguments for infer/ainfer:
            session_id (str): Explicit session ID to resume.
            new_session (bool): If True, forces a new session (ignores auto_resume).
            resume (bool): Whether to resume a previous session.

    The inferencer automatically sets up a pre-execution script to change
    to the repo directory before executing devmate commands, which is required
    for proper devmate operation.

    Session Support:
        DevMate supports session continuation via --resume and --session-id flags.
        This inferencer inherits from TerminalSessionInferencerBase to provide:
        - Automatic session tracking (with auto_resume=True by default)
        - Multi-turn conversation support
        - Session history management

    Usage Patterns:
        # Single-turn usage:
        inferencer = DevmateCliInferencer(root_folder="/path/to/repo")
        result = inferencer.infer("Help me understand this code")
        print(result["output"])

        # Multi-turn with auto-resume (recommended):
        inferencer = DevmateCliInferencer(root_folder="/repo", auto_resume=True)
        r1 = inferencer.new_session("My number is 42")
        r2 = inferencer.infer("What is my number?")  # Auto-resumes!
        r3 = inferencer.infer("New topic", new_session=True)  # Force new

        # Async multi-turn:
        r1 = await inferencer.anew_session("My number is 42")
        r2 = await inferencer.ainfer("What is my number?")  # Auto-resumes!

        # Sync streaming:
        for line in inferencer.infer_streaming("Explain this"):
            print(line, end="")

        # Async streaming:
        async for line in inferencer.ainfer_streaming("Explain this"):
            print(line, end="")

    Attributes:
        root_folder (str): Path to the repository for DevMate context.
            Defaults to ~/fbsource if not specified.
            Standardized name across all inferencer classes (was ``repo_path``).
        model_name (str): Model to use for inference (e.g., 'claude-sonnet-4.5').
            Defaults to 'claude-sonnet-4.5'.
        max_tokens (int): Maximum tokens for response. Defaults to 32768.
        no_create_commit (bool): If True, prevents DevMate from creating commits.
            Defaults to True.
        context_files (List[str]): Optional list of files to include as context.
        headless (bool): If True, runs devmate in headless mode. Defaults to False.
        dump_output (bool): If True, dumps final structs to a temp file for
            reliable output parsing. Defaults to False.
        timeout_percent (int): Optional Sandcastle timeout percentage.
        config_name (str): The config to use. Defaults to 'freeform'.
            Note: Changing this mid-session or between resume calls may cause
            devmate CLI to reject the resume. Keep consistent within a session.
        privacy_type (str): Optional privacy type (PUBLIC or PRIVATE).
        extra_cli_args (List[str]): Additional CLI args to append.
            Caller is responsible for shell-safe values.
        auto_resume (bool): If True, automatically resume previous session.
            Defaults to True.

    Inherited Session Attributes:
        session_arg_name (str): CLI arg for session ID. Defaults to '--session-id'.
        resume_arg_name (str): CLI arg for resume flag. Defaults to '--resume'.
        active_session_id (str): Currently active session ID.
    """

    # Existing attributes
    root_folder: Optional[str] = attrib(default=None)
    model_name: str = attrib(default="claude-sonnet-4.5")
    # Bumped 32K → 64K (claude opus 4.x standard cap) to give the orchestrator
    # more headroom for legitimate large outputs. NOTE: this does NOT raise the
    # cap on devmate's `edit`/PATCH tool, which routes through a SEPARATE
    # patchgen LLM with a HARDCODED ~8 KB output cap (in devai/config/patchgen).
    # For files >5 KB, prompts must steer the model to use `write_file` instead
    # of `edit` — see followup.jinja2 "Tool selection" section.
    max_tokens: int = attrib(default=65536)
    no_create_commit: bool = attrib(default=True)
    context_files: Optional[List[str]] = attrib(default=None)

    # Enhanced CLI options
    headless: bool = attrib(default=False)
    dump_output: bool = attrib(default=False)
    timeout_percent: Optional[int] = attrib(default=None)
    # Default to the ABSOLUTE path of the rankevolve-side
    # ``freeform_agentic.md`` (computed at module load from ``__file__``).
    # See ``_FREEFORM_AGENTIC_ABS_PATH`` above for the full rationale on
    # why absolute and not fbsource-relative or bare-name.
    config_name: str = attrib(default=_FREEFORM_AGENTIC_ABS_PATH)
    privacy_type: Optional[str] = attrib(default=None)
    extra_cli_args: Optional[List[str]] = attrib(default=None)

    # Override base default to enable FILE-mode auto-promotion for large
    # prompts. The base's __attrs_post_init__ flips large_input_mode INLINE
    # → FILE when this attrib is set (terminal_session_inferencer_base.py
    # :144-152). Devmate's construct_command always inlines `prompt=<value>`
    # as a shell arg; without auto-promotion, prompts > Linux's
    # MAX_ARG_STRLEN (~128 KB) crash with `OSError: [Errno 7] Argument list
    # too long: '/bin/sh'`. 100 KB threshold keeps short prompts on the
    # INLINE fast-path while leaving 28 KB headroom for the rest of the
    # shell command (devmate flags, model_name, max_tokens, session args).
    # STDIN mode is not viable: devmate's construct_command doesn't honor
    # kwargs["use_stdin"], so STDIN would still inline the full prompt and
    # hit the same E2BIG. Mirror of claude_code_cli_inferencer.py:82
    # (which sets large_input_mode=STDIN directly because Claude Code's CLI
    # supports stdin natively).
    use_file_for_large_arg_exceeding_size: Optional[
        Union[bool, int, List[str], Dict[str, int]]
    ] = attrib(default=100_000)

    # Session management - inherited from StreamingInferencerBase via TerminalSessionInferencerBase:
    #   auto_resume, active_session_id, new_session, anew_session, resume_session, aresume_session

    # SessionMode: when to start a fresh devmate session vs reuse the active one.
    # Class-level default = SAME_SESSION_ACROSS_ROUNDS for backward-compat with
    # chat_cli and other long-running conversational uses. Dual_inferencer
    # ctor-sites override to NEW_SESSION_PER_CALL via the bridge factory
    # (because each dual_inferencer round is conceptually independent and the
    # prompts are self-contained). See `external/devmate/common.py:SessionMode`
    # for full docs on the trade-offs.
    session_mode: SessionMode = attrib(
        default=SessionMode.SAME_SESSION_ACROSS_ROUNDS,
        converter=lambda v: v if isinstance(v, SessionMode) else SessionMode(v),
    )
    # Threshold for SessionMode.NEW_SESSION_ON_CONSECUTIVE_ERRORS: reset
    # active_session_id after this many consecutive failures.
    consecutive_error_threshold: int = attrib(default=2)
    # Internal counter — tracks consecutive errors for the
    # NEW_SESSION_ON_CONSECUTIVE_ERRORS policy. Reset to 0 on every success.
    _consecutive_error_count: int = attrib(default=0, init=False, repr=False)

    # When the devmate-internal-failure watcher detects a fatal pattern in the
    # devmate-server daemon's stderr AND OUR cache file is silent for >120s,
    # tighten this call's effective deadline to this value (instead of
    # ``total_timeout_seconds``). 0 disables the watcher (graceful fallback).
    # See ``_FATAL_DEVMATE_PATTERNS`` + ``_watch_for_devmate_internal_failure``
    # for the full design rationale (motivated by the Iris RECV_TIMEOUT class
    # of failures where devmate hangs silently and idle_timeout is evaded by
    # heartbeats — see velvet-wondering-crane plan post-mortem).
    total_timeout_on_internal_error_detection_seconds: float = attrib(default=2400)
    # Set by ``_watch_for_devmate_internal_failure`` when it triggers a
    # cancellation, so ``ainfer()``'s except handler can convert the
    # CancelledError into a meaningful InferencerExecutionError.
    _internal_failure_detected: bool = attrib(default=False, init=False, repr=False)
    _internal_failure_reason: str = attrib(default="", init=False, repr=False)

    # Internal state for dump file path (same concurrency constraints as base class)
    _output_file: Optional[str] = attrib(default=None, init=False, repr=False)

    def __attrs_post_init__(self):
        """Set root_folder and configure pre-execution script to cd to repo."""
        # Default root_folder to ~/fbsource if not specified
        if self.root_folder is None:
            self.root_folder = os.path.expanduser("~/fbsource")

        # Set working_dir to root_folder for command execution
        if self.working_dir is None:
            self.working_dir = self.root_folder

        # Set up pre-execution script to cd to repo directory
        # This is required because devmate needs to be run from within the repo
        cd_script = f'cd "{self.root_folder}" || exit 1'

        if self.pre_exec_scripts is None:
            self.pre_exec_scripts = [cd_script]
        elif cd_script not in self.pre_exec_scripts:
            # Insert cd command at the beginning if not already present
            self.pre_exec_scripts.insert(0, cd_script)

        super().__attrs_post_init__()

    def _build_session_args(self, session_id: str, is_resume: bool) -> str:
        """
        Build CLI arguments for DevMate session management.

        DevMate uses --resume and --session-id flags for session continuation:
        - --resume: Flag to indicate resuming a previous session
        - --session-id 'uuid': The session ID to resume

        Args:
            session_id: The session ID to use.
            is_resume: Whether this is resuming an existing session.

        Returns:
            String containing the CLI arguments (e.g., "--resume --session-id 'abc123'").
        """
        if is_resume and session_id:
            return f"{self.resume_arg_name} {self.session_arg_name} '{session_id}'"
        elif session_id:
            # Just pass session ID without resume (for tracking purposes)
            return f"{self.session_arg_name} '{session_id}'"
        return ""

    def construct_command(self, inference_input: Any, **kwargs) -> str:
        """
        Construct the DevMate CLI command as a shell command string.

        This returns a properly quoted shell command string that matches
        the working bash script format:
        devmate run freeform "prompt=$PROMPT" "model_name=$MODEL" "max_tokens=32768" --no-create-commit

        For session continuation (resume), the format is:
        devmate run --resume --session-id 'uuid' freeform "prompt=$PROMPT" ...

        Args:
            inference_input: The prompt string or dict with 'prompt' key.
            **kwargs: Additional arguments:
                - model_name: Override model name
                - max_tokens: Override max tokens
                - context_files: Override context files
                - session_id: Session ID for continuation
                - resume: Whether to resume a previous session

        Returns:
            Shell command string with properly quoted arguments.
        """
        # Extract prompt
        if isinstance(inference_input, dict):
            prompt = inference_input.get("prompt", str(inference_input))
        else:
            prompt = str(inference_input)

        # Get model and token settings (allow overrides via kwargs)
        model = kwargs.get("model_name", self.model_name)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        context_files = kwargs.get("context_files", self.context_files)

        # Get session settings from kwargs (set by _infer in parent class)
        session_id = kwargs.get("session_id")
        is_resume = kwargs.get("resume", False)

        # Escape prompt for shell (order matters - backslash first)
        escaped_prompt = (
            prompt.replace("\\", "\\\\")  # Escape backslashes first
            .replace('"', '\\"')  # Escape double quotes
            .replace("$", "\\$")  # Escape variable expansion
            .replace("`", "\\`")  # Escape command substitution (backticks)
        )

        # Build the shell command string
        # Base: devmate run
        command_parts = ["devmate", "run"]

        # Add session args if resuming (before config name)
        if is_resume and session_id:
            session_args = self._build_session_args(session_id, is_resume)
            command_parts.append(session_args)

        # Add config name
        command_parts.append(self.config_name)

        # Add variables
        command_parts.extend(
            [
                f'"prompt={escaped_prompt}"',
                f'"model_name={model}"',
                f'"max_tokens={max_tokens}"',
            ]
        )

        # Add context files if specified (also quoted)
        if context_files:
            for file_path in context_files:
                command_parts.append(f'"context_file={file_path}"')

        # Add headless flag
        if self.headless:
            command_parts.append("--headless")

        # Add dump output file (use mkstemp for security)
        if self.dump_output:
            fd, self._output_file = tempfile.mkstemp(
                suffix=".json", prefix="devmate_output_"
            )
            os.close(fd)  # Close fd; devmate writes by path
            command_parts.append(f"--dump-final-structs-to-file {self._output_file}")

        # Add timeout percentage (use `is not None` since 0 is a valid value)
        if self.timeout_percent is not None:
            command_parts.append(f"--sandcastle-timeout-percent {self.timeout_percent}")

        # Add privacy type
        if self.privacy_type:
            command_parts.append(f"--privacy-type {self.privacy_type}")

        # Add no_create_commit flag at the END (like the working bash script)
        if self.no_create_commit:
            command_parts.append("--no-create-commit")

        # Add extra CLI args (caller responsible for shell-safe values)
        if self.extra_cli_args:
            command_parts.extend(self.extra_cli_args)

        # Return as a single shell command string
        return " ".join(command_parts)

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> Dict[str, Any]:
        """
        Parse the DevMate command output.

        If dump_output is enabled, reads from the dump file for more reliable
        output parsing. Falls back to stdout parsing if file is not available.

        This method cleans up the raw DevMate output by:
        1. Removing session header/footer blocks (Session ID, Trajectory, etc.)
        2. Extracting the actual response content
        3. Handling duplicate responses (takes the first one)

        Args:
            stdout: Standard output from DevMate command.
            stderr: Standard error from DevMate command.
            return_code: Process return code.

        Returns:
            Dictionary with:
                - output (str): The cleaned main response content
                - raw_output (str): The original unprocessed output
                - stderr (str): Any error output
                - return_code (int): Process return code
                - success (bool): True if command succeeded
                - session_id (str, optional): Extracted session ID
                - trajectory_url (str, optional): Extracted trajectory URL
                - dump_data (dict, optional): Full dump data if dump_output enabled
                - error (str, optional): Error message if failed
        """
        result = {
            "raw_output": stdout.strip() if stdout else "",
            "stderr": stderr.strip() if stderr else "",
            "return_code": return_code,
            "success": return_code == 0,
        }

        # Try dump file first (more reliable when enabled)
        if self.dump_output and self._output_file and os.path.exists(self._output_file):
            try:
                with open(self._output_file, "r") as f:
                    dump_data = json.load(f)

                result["output"] = self._extract_output_from_dump(dump_data)
                result["session_id"] = dump_data.get("session_id")
                result["dump_data"] = dump_data

                # Build trajectory URL if we have session_id
                if result.get("session_id"):
                    result["trajectory_url"] = (
                        f"https://www.internalfb.com/intern/devai/devmate/inspector/{result['session_id']}"
                    )

            except Exception as e:
                # Catch all exceptions (JSONDecodeError, IOError, and any unexpected errors)
                # to ensure graceful fallback to stdout parsing
                self.log_debug(f"Failed to process dump file: {e}", "ParseError")
            finally:
                # Always clean up temp file
                self._cleanup_output_file()

        # Fall back to stdout parsing if no dump data
        if "output" not in result:
            session_id = self._extract_session_id(result["raw_output"])
            trajectory_url = self._extract_trajectory_url(result["raw_output"])
            cleaned_output = self._clean_devmate_output(result["raw_output"])

            result["output"] = cleaned_output
            if session_id:
                result["session_id"] = session_id
            if trajectory_url:
                result["trajectory_url"] = trajectory_url

        # Add error if failed
        if return_code != 0 and "error" not in result:
            result["error"] = (
                stderr.strip() if stderr else f"Command failed with code {return_code}"
            )

        # Surface the model's finish_reason (LENGTH / STOP / etc.) when devmate
        # reports it in stdout. devmate's diagnostic format is e.g.:
        #   "Model returned a response with a finish reason of FinishReason.LENGTH."
        # This lets downstream orchestrators (DualInferencer) distinguish
        # token-truncation from a model that deliberately skipped <Response>.
        finish_reason_match = re.search(
            r"FinishReason\.([A-Z_]+)", result.get("raw_output", "")
        )
        if finish_reason_match:
            result["finish_reason"] = finish_reason_match.group(1)

        return result

    def _extract_output_from_dump(self, dump_data: Dict[str, Any]) -> str:
        """Extract main output from dump file structure."""
        try:
            if "final_response" in dump_data:
                return dump_data["final_response"]
            # Fallback: stringify the dump
            return json.dumps(dump_data, indent=2)
        except Exception as e:
            self.log_debug(f"Failed to extract output from dump: {e}", "ParseError")
            return ""

    def _cleanup_output_file(self) -> None:
        """Clean up temporary output file."""
        if self._output_file and os.path.exists(self._output_file):
            try:
                os.remove(self._output_file)
                self.log_debug(
                    f"Cleaned up output file: {self._output_file}", "Cleanup"
                )
            except OSError as e:
                self.log_debug(f"Failed to clean up output file: {e}", "Cleanup")
            finally:
                self._output_file = None

    def _extract_session_id(self, output: str) -> Optional[str]:
        """Extract session ID from DevMate output."""
        import re

        match = re.search(r"Session ID:\s*([a-f0-9-]+)", output)
        if match:
            return match.group(1)
        return None

    def _extract_trajectory_url(self, output: str) -> Optional[str]:
        """Extract trajectory URL from DevMate output."""
        import re

        match = re.search(r"Trajectory:\s*(https?://\S+)", output)
        if match:
            return match.group(1)
        return None

    def _clean_devmate_output(self, output: str) -> str:
        """
        Clean DevMate output by removing session headers/footers.

        DevMate output typically has this structure:
        - Header: "Starting Devmate server...", session info block
        - Content: The actual response
        - Footer: "Finished session...", session info block repeated

        This method extracts just the actual response content.
        """
        if not output:
            return ""

        import re

        # Split into lines for processing
        lines = output.split("\n")
        cleaned_lines = []

        # Patterns to identify session-related lines (case insensitive for robustness)
        session_patterns = [
            r"^Starting Devmate server",
            r"^Finished starting Devmate server",
            r"^Started session",
            r"^Finished session",
            r"^Session ID:",
            r"^Trajectory:",
            r"^Server logs available at:",
            r"^Client logs available at:",
            r"^=+$",  # Separator lines (================)
        ]

        # Compile patterns (case insensitive)
        compiled_patterns = [re.compile(p, re.IGNORECASE) for p in session_patterns]

        for line in lines:
            stripped_line = line.strip()

            # Skip empty lines at the beginning
            if not cleaned_lines and not stripped_line:
                continue

            # Check if this line matches any session pattern
            is_session_line = any(
                pattern.match(stripped_line) for pattern in compiled_patterns
            )

            if is_session_line:
                # Skip session-related lines
                continue
            else:
                # This is content
                cleaned_lines.append(line)

        # Join cleaned lines and strip trailing whitespace/empty lines
        cleaned_output = "\n".join(cleaned_lines).strip()

        # Remove any trailing session info that might be on the same line
        # e.g., "response text Finished session abc123"
        cleaned_output = re.sub(
            r"\s*Finished session\s+[a-f0-9-]+\s*$",
            "",
            cleaned_output,
            flags=re.IGNORECASE,
        )

        # Handle duplicate responses (DevMate sometimes outputs response twice)
        # Look for `---` separator that might indicate duplication
        if "---\n" in cleaned_output:
            parts = cleaned_output.split("---\n")
            if len(parts) >= 2:
                # Check if first and second parts are similar (duplicate)
                first_part = parts[0].strip()
                second_part = parts[1].strip() if len(parts) > 1 else ""

                # If they look similar (both start/end similarly), take just the first
                if first_part and second_part:
                    # Simple heuristic: if second part starts like first part
                    first_lines = first_part.split("\n")[:3]
                    second_lines = second_part.split("\n")[:3]

                    if first_lines == second_lines:
                        # It's a duplicate, return just the first part
                        cleaned_output = first_part

        return cleaned_output

    def get_response_text(self, result: Dict[str, Any]) -> str:
        """
        Extract just the response text from a result dictionary.

        This is a convenience method for getting the main output.

        Args:
            result: The result dictionary from infer().

        Returns:
            The main response text, or error message if failed.
        """
        if result.get("success"):
            return result.get("output", "")
        else:
            return result.get("error", "Unknown error occurred")

    async def ainfer(
        self, inference_input: Any, inference_config: Any = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Async inference using CLI subprocess.

        This method provides async execution of the DevMate CLI command,
        enabling non-blocking I/O during command execution.

        Args:
            inference_input: The prompt string or dict with 'prompt' key.
            inference_config: Optional configuration (unused).
            **kwargs: Additional arguments:
                - session_id: Session ID for continuation
                - resume: Whether to resume a previous session
                - new_session: If True, forces a new session

        Returns:
            Result dictionary with output, session_id, etc.
        """
        # Apply SessionMode policy at start-of-call (BEFORE resolving session_id).
        #   - PER_CALL: every call is fresh
        #   - ON_CONSECUTIVE_ERRORS with threshold reached: reset + reset counter
        #   - ON_ERROR: reactive (handled below in error branch)
        #   - SAME (default): no-op here
        if self.session_mode == SessionMode.NEW_SESSION_PER_CALL:
            kwargs["new_session"] = True
            logger.info(
                "[DevmateCliInferencer] SessionMode=NEW_SESSION_PER_CALL: "
                "starting fresh devmate session for this call.",
            )
        elif (
            self.session_mode == SessionMode.NEW_SESSION_ON_CONSECUTIVE_ERRORS
            and self._consecutive_error_count >= self.consecutive_error_threshold
        ):
            kwargs["new_session"] = True
            logger.info(
                "[DevmateCliInferencer] SessionMode=NEW_SESSION_ON_CONSECUTIVE_ERRORS "
                "threshold (%d) reached; starting fresh devmate session.",
                self.consecutive_error_threshold,
            )
            self._consecutive_error_count = 0

        # Handle new_session flag
        new_session = kwargs.pop("new_session", False)
        if new_session:
            self.active_session_id = None

        # Determine session context (same logic as sync _infer)
        session_id = kwargs.get("session_id", self.active_session_id)
        is_resume = kwargs.get("resume", True)

        # If no session to resume and auto_resume is enabled, check for active session
        if session_id is None:
            if self.auto_resume and self.active_session_id:
                session_id = self.active_session_id
            else:
                is_resume = False

        # Update kwargs with session info for construct_command
        kwargs["session_id"] = session_id
        kwargs["resume"] = is_resume and session_id is not None

        # Use parent's _ainfer which calls construct_command and _execute_command_async.
        # Wrap in a task so we can race it against the devmate-internal-failure
        # watcher (which detects fatal devmate-daemon errors and shortens the
        # call's effective deadline). Watcher only fires when both signals
        # agree: known-fatal pattern in devmate.stderr AND our cache silent
        # for >120s. See ``_watch_for_devmate_internal_failure`` for design.
        self._internal_failure_detected = False
        self._internal_failure_reason = ""
        call_start_ts = time.time()
        inference_task = asyncio.ensure_future(
            self._ainfer(inference_input, inference_config, **kwargs)
        )
        watcher_task: Optional[asyncio.Task] = None
        if self.total_timeout_on_internal_error_detection_seconds > 0:
            watcher_task = asyncio.ensure_future(
                self._watch_for_devmate_internal_failure(
                    inference_task=inference_task,
                    call_start_ts=call_start_ts,
                )
            )
        try:
            result = await inference_task
        except asyncio.CancelledError:
            # Distinguish: was this our watcher's planned cancellation, or an
            # external cancel (e.g., user interrupt, parent task shutdown)?
            if self._internal_failure_detected:
                raise InferencerExecutionError(
                    tool="devmate",
                    return_code=124,  # standard "killed by timeout" exit code
                    error=(
                        "Cancelled by devmate-internal-failure watcher: "
                        + self._internal_failure_reason
                    ),
                )
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                # Suppress cancellation noise — watcher's only job is to
                # signal us; once we're done it has no value.
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

        # Update active session if we got a new session ID
        result_session_id = (
            result.get("session_id") if isinstance(result, dict) else None
        )
        if result_session_id and result_session_id != self.active_session_id:
            self.active_session_id = result_session_id
            self.log_debug(
                f"Updated active session to: {result_session_id[:8]}...", "Async"
            )

        # SessionMode counter: reset on any success (used by
        # NEW_SESSION_ON_CONSECUTIVE_ERRORS threshold logic).
        if isinstance(result, dict) and result.get("success", True):
            self._consecutive_error_count = 0

        # Surface terminal-inferencer failure to InferencerBase's
        # async_execute_with_retry envelope by raising. Returning a
        # ``{success: False, ...}`` dict here would slip past the retry
        # layer and only fail much later inside ``extract_response_text``,
        # bypassing the codebase's existing transient-failure recovery.
        if isinstance(result, dict) and not result.get("success", True):
            # SessionMode counter: increment on any failure (used by
            # NEW_SESSION_ON_CONSECUTIVE_ERRORS threshold + reset-on-success).
            self._consecutive_error_count += 1
            err = (result.get("error") or "").strip()
            # SessionMode.NEW_SESSION_ON_ERROR: catchall — clear active_session_id
            # on ANY error so the retry layer's next attempt creates a fresh
            # devmate session. Generalizes the existing _looks_like_*
            # specific recoveries below to any error class.
            if self.session_mode == SessionMode.NEW_SESSION_ON_ERROR:
                bad = (self.active_session_id or "<none>")[:8]
                logger.warning(
                    "[DevmateCliInferencer] SessionMode=NEW_SESSION_ON_ERROR: "
                    "clearing active_session_id %s on any error so retry starts "
                    "fresh.",
                    bad,
                )
                self.active_session_id = None
            if _looks_like_port_file_race(err):
                logger.warning(
                    "[DevmateCliInferencer] Devmate port-file race detected; "
                    "sleeping %.1fs before re-raising so the retry layer "
                    "doesn't immediately re-hit the cold-start window.",
                    _PORT_FILE_RACE_BACKOFF_SECONDS,
                )
                await asyncio.sleep(_PORT_FILE_RACE_BACKOFF_SECONDS)
            elif _looks_like_tool_use_corruption(err):
                # Structural session-state corruption (orphan tool_use in the
                # conversation history). The retry layer's lambda re-reads
                # self._ainfer on each attempt — clearing active_session_id
                # here forces the next call's `kwargs.get("session_id",
                # self.active_session_id)` (line ~562) to fall back to None,
                # which routes through the `is_resume = False` branch and
                # produces a fresh devmate session. No backoff: this is
                # structural corruption, not a transient race; sleeping
                # would only delay recovery without changing the outcome.
                bad = (self.active_session_id or "<none>")[:8]
                logger.warning(
                    "[DevmateCliInferencer] Anthropic tool_use/tool_result "
                    "corruption detected in devmate session %s — clearing "
                    "active_session_id so the retry starts fresh.",
                    bad,
                )
                self.active_session_id = None
            elif _looks_like_max_iterations(err):
                # Devmate's per-session iteration counter is exhausted. The
                # counter is per-session cumulative; a fresh session resets it.
                # Same recovery pattern as tool_use_corruption above: clear
                # active_session_id so the retry layer's next attempt creates
                # a fresh devmate session. The prompt is self-contained
                # (verified via dual_inferencer prompt-self-containment audit),
                # so no logical context is lost.
                bad_session = self.active_session_id
                bad = (bad_session or "<none>")[:8]
                logger.warning(
                    "[DevmateCliInferencer] Devmate MAX_ITERATIONS cap reached "
                    "in session %s — clearing active_session_id so retry starts "
                    "fresh (prompt is self-contained; no context loss).",
                    bad,
                )
                self.active_session_id = None
                # Parse the cap value from the error message for diagnostics.
                m = re.search(r"Max iterations of (\d+) reached", err)
                raise MaxIterationsExhaustedError(
                    tool="devmate",
                    return_code=result.get("return_code"),
                    stderr=(result.get("stderr") or ""),
                    error=err,
                    max_iterations=int(m.group(1)) if m else None,
                    session_id=bad_session,
                )
            raise InferencerExecutionError(
                tool="devmate",
                return_code=result.get("return_code"),
                stderr=(result.get("stderr") or ""),
                error=err,
            )

        return result

    async def ainfer_streaming(
        self,
        inference_input: Any,
        inference_config: Any = None,
        *,
        filter_session_info: bool = True,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Async streaming inference: yields output lines as they arrive.

        Args:
            inference_input: Prompt string OR dict with "prompt" key (per
                StreamingInferencerBase contract).
            inference_config: Optional config (unused; accepted for signature
                parity with the base class).
            filter_session_info: If True (default), filters out session header/footer.
            **kwargs: Additional arguments:
                - session_id: Session ID for continuation
                - resume: Whether to resume a previous session
                - new_session: If True, forces a new session

        Yields:
            Lines of DevMate output as they become available.

        Example:
            async for line in inferencer.ainfer_streaming("Explain this code"):
                print(line, end="")
        """
        # Honor StreamingInferencerBase contract: inference_input may be a str
        # OR a dict with "prompt". Extract once here so the rest of the body
        # (and downstream _ainfer_streaming/construct_command) see a string.
        prompt = self._extract_prompt(inference_input)

        # Temporarily disable dump_output for streaming (incompatible)
        original_dump_output = self.dump_output
        if self.dump_output:
            self.log_debug(
                "dump_output=True is incompatible with streaming; disabled for this call.",
                "AsyncStream",
            )
            self.dump_output = False

        try:
            # Handle new_session flag
            new_session = kwargs.pop("new_session", False)
            if new_session:
                self.active_session_id = None

            # Determine session context
            session_id = kwargs.get("session_id", self.active_session_id)
            is_resume = kwargs.get("resume", True)

            if session_id is None:
                if self.auto_resume and self.active_session_id:
                    session_id = self.active_session_id
                else:
                    is_resume = False

            kwargs["session_id"] = session_id
            kwargs["resume"] = is_resume and session_id is not None

            # Track state for filtering
            content_started = False
            pending_empty_lines = []

            # Open cache file if configured
            cache_file = self._open_cache_file(prompt) if self.cache_folder else None
            success = False
            error = None

            try:
                async for line in self._ainfer_streaming(prompt, **kwargs):
                    self._append_to_cache(cache_file, line)
                    if filter_session_info:
                        if self._is_session_info_line(line):
                            continue

                        stripped = line.strip()
                        if not stripped:
                            if content_started:
                                pending_empty_lines.append(line)
                            continue

                        content_started = True

                        for empty_line in pending_empty_lines:
                            yield empty_line
                        pending_empty_lines = []

                        yield line
                    else:
                        yield line

                success = True
            except Exception as e:
                error = e
                raise
            finally:
                self._finalize_cache(cache_file, success, error)

        finally:
            self.dump_output = original_dump_output

    # === Streaming Methods ===

    def _is_session_info_line(self, line: str) -> bool:
        """
        Check if a line is session-related info that should be filtered.

        Args:
            line: The line to check.

        Returns:
            True if the line should be filtered out (session header/footer).
        """
        import re

        stripped = line.strip()

        # Empty lines pass through (will be filtered later if needed)
        if not stripped:
            return False

        # Patterns for session info lines to filter
        session_patterns = [
            r"^Starting Devmate server",
            r"^Finished starting Devmate server",
            r"^Started session",
            r"^Finished session",
            r"^Session ID:",
            r"^Trajectory:",
            r"^Server logs available at:",
            r"^Client logs available at:",
            r"^=+$",  # Separator lines (================)
        ]

        for pattern in session_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                return True

        return False

    def infer_streaming(
        self,
        prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        output_stream: Optional[TextIO] = None,
        filter_session_info: bool = True,
        **kwargs,
    ) -> Iterator[str]:
        """
        Execute DevMate inference with streaming output.

        This method yields output lines as they become available from the
        DevMate CLI, allowing real-time display of responses.

        Note: dump_output mode is incompatible with streaming. If dump_output=True,
        the dump file will NOT be created during streaming (to prevent temp file leaks).
        Use standard infer() method for dump_output functionality.

        Note: The try/finally pattern in generators has a timing subtlety - the finally
        block only runs when the generator is fully consumed, explicitly closed, or
        garbage collected. In CPython this typically happens promptly due to reference
        counting. This is an inherent Python limitation.

        Args:
            prompt: The prompt to send to DevMate.
            stream_callback: Optional callback invoked for each output line.
            output_stream: Optional TextIO stream to write output to.
            filter_session_info: If True (default), filters out session ID,
                trajectory URL, and other session header/footer info from
                the streaming output. The session info is still available
                via get_streaming_result() after streaming completes.
            **kwargs: Additional arguments:
                - model_name: Override model name
                - max_tokens: Override max tokens
                - context_files: Override context files
                - session_id: Session ID for continuation
                - resume: Whether to resume a previous session
                - new_session: If True, forces a new session

        Yields:
            Lines of DevMate output as they become available.

        Note:
            After iteration completes, call get_streaming_result() to get
            the parsed output with session ID and other metadata.

        Example:
            >>> inferencer = DevmateCliInferencer()
            >>> for line in inferencer.infer_streaming("Explain this code"):
            ...     print(line, end="")  # Print as it streams
            >>> result = inferencer.get_streaming_result()
            >>> print(f"Session ID: {result.get('session_id')}")
        """
        # Temporarily disable dump_output for streaming (incompatible)
        original_dump_output = self.dump_output
        if self.dump_output:
            self.log_debug(
                "dump_output=True is incompatible with streaming; disabled for this call. "
                "Use infer() for dump_output functionality.",
                "Stream",
            )
            self.dump_output = False

        try:
            # Handle new_session flag
            new_session = kwargs.pop("new_session", False)
            if new_session:
                self.active_session_id = None

            # Determine session context (same logic as parent's _infer)
            session_id = kwargs.get("session_id", self.active_session_id)
            is_resume = kwargs.get("resume", True)

            # If no session to resume, this will be a new session
            if session_id is None:
                is_resume = False

            # Update kwargs with session info for construct_command
            kwargs["session_id"] = session_id
            kwargs["resume"] = is_resume

            if is_resume and session_id:
                self.log_debug(
                    f"Streaming with session resume: {session_id[:8]}...", "Stream"
                )
            else:
                self.log_debug("Streaming new session", "Stream")

            # Track state for filtering
            content_started = False
            pending_empty_lines = []

            # Open cache file if configured
            cache_file = self._open_cache_file(prompt) if self.cache_folder else None
            cache_success = False
            cache_error = None

            try:
                # Use the parent's _infer_streaming method with filtering
                for line in self._infer_streaming(
                    {"prompt": prompt},
                    stream_callback=None,  # We handle callback ourselves after filtering
                    output_stream=None,  # We handle output stream ourselves after filtering
                    **kwargs,
                ):
                    # Cache raw line before filtering
                    self._append_to_cache(cache_file, line)

                    if filter_session_info:
                        # Check if this is a session info line
                        if self._is_session_info_line(line):
                            # Skip session info lines
                            continue

                        # Handle empty lines
                        stripped = line.strip()
                        if not stripped:
                            # Buffer empty lines - only output them if content follows
                            if content_started:
                                pending_empty_lines.append(line)
                            continue

                        # This is actual content
                        content_started = True

                        # Output any pending empty lines first
                        for empty_line in pending_empty_lines:
                            if stream_callback:
                                stream_callback(empty_line)
                            if output_stream:
                                output_stream.write(empty_line)
                                output_stream.flush()
                            yield empty_line
                        pending_empty_lines = []

                        # Output the content line
                        if stream_callback:
                            stream_callback(line)
                        if output_stream:
                            output_stream.write(line)
                            output_stream.flush()
                        yield line
                    else:
                        # No filtering - pass through everything
                        if stream_callback:
                            stream_callback(line)
                        if output_stream:
                            output_stream.write(line)
                            output_stream.flush()
                        yield line

                cache_success = True
            except Exception as e:
                cache_error = e
                raise
            finally:
                self._finalize_cache(cache_file, cache_success, cache_error)

        finally:
            # Restore original setting
            self.dump_output = original_dump_output

    def get_streaming_result(self) -> Dict[str, Any]:
        """
        Get the final parsed result after streaming completes.

        Call this method after exhausting the iterator from infer_streaming()
        to get the parsed output with session ID, trajectory URL, and other
        metadata extracted.

        Returns:
            Dictionary with:
                - output (str): The cleaned main response content
                - raw_output (str): The original unprocessed output
                - stderr (str): Any error output (empty for streaming)
                - return_code (int): Process return code
                - success (bool): True if command succeeded
                - session_id (str, optional): Extracted session ID
                - trajectory_url (str, optional): Extracted trajectory URL

        Example:
            >>> inferencer = DevmateCliInferencer()
            >>> # Consume the streaming iterator
            >>> output = "".join(inferencer.infer_streaming("Hello"))
            >>> # Now get the parsed result
            >>> result = inferencer.get_streaming_result()
            >>> session_id = result.get("session_id")
        """
        stdout = getattr(self, "_last_streaming_output", "")
        return_code = getattr(self, "_last_streaming_return_code", 0)

        # Use the existing parse_output method
        result = self.parse_output(stdout, "", return_code)

        # Update active session if we got a new session ID
        session_id = result.get("session_id")
        if session_id and session_id != self.active_session_id:
            self.active_session_id = session_id
            self.log_debug(f"Updated active session to: {session_id[:8]}...", "Stream")

        return result

    # ------------------------------------------------------------------
    # Devmate-internal-failure detection (watcher + helpers)
    # ------------------------------------------------------------------
    # See module-level ``_FATAL_DEVMATE_PATTERNS`` for the design rationale.
    # The watcher is spawned in ``ainfer()``. It polls devmate's daemon
    # stderr every 60s. When it sees a known-fatal pattern AND our cache
    # file has been silent for >120s, it shortens the deadline. SOFT signal:
    # only adjusts the timeout; doesn't immediately abort. Devmate may still
    # self-recover within the shortened window.

    def _devmate_log_path(self) -> Optional[Path]:
        """Locate the devmate-server daemon's stderr file.

        Convention (Meta internal):
            ``~/.local/state/devmate/data/<USER>/<root_basename>/devmate.stderr``
        where ``<root_basename>`` is the basename of devmate's CWD (which
        matches ``self.root_folder``, set at inferencer construction time).

        Returns None if the path can't be derived OR the file doesn't exist
        (graceful degradation: watcher silently skips, total_timeout still
        applies as the safety net).
        """
        user = os.environ.get("USER")
        if not user or not self.root_folder:
            return None
        try:
            root = Path(self.root_folder).resolve()
        except (OSError, ValueError):
            return None
        log_path = (
            Path.home()
            / ".local"
            / "state"
            / "devmate"
            / "data"
            / user
            / root.name
            / "devmate.stderr"
        )
        if not log_path.exists():
            return None
        return log_path

    def _scan_devmate_log_for_fatal_pattern(
        self, log_path: Path, since_ts: float
    ) -> Optional[str]:
        """Tail-scan ``log_path`` for any line matching ``_FATAL_DEVMATE_PATTERNS``.

        Returns the first matching line (truncated to 200 chars) or None.
        Reads at most ``_DEVMATE_LOG_TAIL_BYTES`` to keep this cheap on huge
        log files. ``since_ts`` is used as a coarse filter via file mtime —
        if the log file hasn't been written since ``since_ts``, no match.
        """
        try:
            st = log_path.stat()
        except OSError:
            return None
        if st.st_mtime < since_ts:
            return None  # Log hasn't been written since our call started
        try:
            size = st.st_size
            with open(log_path, "rb") as f:
                seek_to = max(0, size - _DEVMATE_LOG_TAIL_BYTES)
                f.seek(seek_to)
                content = f.read().decode("utf-8", errors="replace")
        except OSError:
            return None
        for pattern in _FATAL_DEVMATE_PATTERNS:
            m = pattern.search(content)
            if not m:
                continue
            line_start = content.rfind("\n", 0, m.start()) + 1
            line_end = content.find("\n", m.end())
            if line_end < 0:
                line_end = len(content)
            line = content[line_start:line_end].strip()
            return line[:200]
        return None

    def _get_active_cache_file_path(self) -> Optional[Path]:
        """Return the cache stream file currently being written by the
        in-flight ``ainfer()`` call, or None if not findable.

        Only one call per inferencer instance is in-flight at a time, so the
        most-recently-modified ``stream_*.txt`` under ``cache_folder`` is ours.
        """
        if not self.cache_folder:
            return None
        cache_dir = Path(self.cache_folder)
        if not cache_dir.exists():
            return None
        try:
            streams = list(cache_dir.glob("**/stream_*.txt"))
        except OSError:
            return None
        if not streams:
            return None
        try:
            return max(streams, key=lambda p: p.stat().st_mtime)
        except OSError:
            return None

    async def _watch_for_devmate_internal_failure(
        self,
        inference_task: asyncio.Task,
        call_start_ts: float,
    ) -> None:
        """Background watcher: polls devmate.stderr for fatal patterns.

        On match (AND cache silent for >120s confirming the failure affects
        OUR call), schedules cancellation of ``inference_task`` at the
        shortened deadline ``total_timeout_on_internal_error_detection_seconds``
        from ``call_start_ts``. ``inference_task`` may complete normally
        before the cancellation fires (devmate self-recovers).

        One-shot: returns after scheduling (or after detecting an
        unrecoverable condition that means no detection is possible —
        e.g., log path doesn't exist). Cancelled by ``ainfer``'s finally
        block on normal completion.
        """
        log_path = self._devmate_log_path()
        if log_path is None:
            logger.debug(
                "[DevmateCliInferencer] devmate log path not derivable; "
                "internal-failure watcher disabled for this call."
            )
            return

        while True:
            try:
                await asyncio.sleep(_INTERNAL_FAILURE_WATCHER_POLL_SECONDS)
            except asyncio.CancelledError:
                return

            if inference_task.done():
                return

            match_line = self._scan_devmate_log_for_fatal_pattern(
                log_path, since_ts=call_start_ts
            )
            if not match_line:
                continue

            # Confirmation guard: only act if OUR call is also stuck. The
            # daemon's stderr is shared across all concurrent devmate calls;
            # if our cache is still growing, the matched line is from a
            # different session and we shouldn't penalize ours.
            cache_path = self._get_active_cache_file_path()
            if cache_path is None:
                continue
            try:
                cache_silence = time.time() - cache_path.stat().st_mtime
            except OSError:
                continue
            if cache_silence < _INTERNAL_FAILURE_CACHE_SILENCE_THRESHOLD_SECONDS:
                # Our stream is still actively producing — false positive
                # from a concurrent session sharing the daemon. Keep watching;
                # don't adjust deadline.
                continue

            # Both signals agree. Schedule cancellation at the shortened
            # deadline (or immediately if we're already past it).
            elapsed = time.time() - call_start_ts
            time_until_new_deadline = (
                self.total_timeout_on_internal_error_detection_seconds - elapsed
            )
            self._internal_failure_detected = True
            self._internal_failure_reason = (
                f"matched pattern in devmate.stderr; cache silent for "
                f"{cache_silence:.0f}s; matched line: {match_line!r}"
            )
            if time_until_new_deadline <= 0:
                logger.warning(
                    "[DevmateCliInferencer] Devmate-internal failure detected "
                    "(pattern + cache silence). Already past shortened deadline "
                    "(%.0fs); cancelling inference now. Match: %s",
                    self.total_timeout_on_internal_error_detection_seconds,
                    match_line,
                )
                inference_task.cancel()
            else:
                logger.warning(
                    "[DevmateCliInferencer] Devmate-internal failure detected "
                    "(pattern + cache silence). Tightening deadline from %.0fs to "
                    "%.0fs (%.0fs from now). Devmate may still self-recover. "
                    "Match: %s",
                    getattr(self, "total_timeout_seconds", 3600),
                    self.total_timeout_on_internal_error_detection_seconds,
                    time_until_new_deadline,
                    match_line,
                )
                asyncio.get_running_loop().call_later(
                    time_until_new_deadline,
                    inference_task.cancel,
                )
            return  # one-shot — only adjust deadline once
