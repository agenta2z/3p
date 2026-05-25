# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""Terminal Session Inferencer Base.

Extends StreamingInferencerBase with subprocess-based command execution.
Subclasses implement ``construct_command()``, ``parse_output()``, and
``_build_session_args()`` for their specific CLI tools.
"""

import asyncio
import enum
import logging
import os
import subprocess
import tempfile
from abc import abstractmethod
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Tuple, Union

from attr import attrib, attrs
from rankevolve.src.agentic_foundation.common.inferencers.streaming_inferencer_base import (
    StreamingInferencerBase,
)

logger: logging.Logger = logging.getLogger(__name__)

_DEFAULT_LARGE_ARG_THRESHOLD: int = 65_536  # 64 KB

# Per-line buffer limit for asyncio's subprocess StreamReader. The asyncio
# default is 64 KB, which fires ``asyncio.LimitOverrunError`` whenever a
# subprocess emits a single line larger than that — common for CLI tools
# that dump JSON or long markdown blocks without internal newlines (e.g. a
# Devmate dump file or a ``str(dict)`` corruption). Push the per-line limit
# to 16 MB so realistic outputs stream cleanly. ``_ainfer_streaming``
# additionally falls back to a chunked ``read()`` if even this is exceeded.
_MAX_STDOUT_LINE_BYTES: int = 16 * 1024 * 1024  # 16 MB


class LargeInputMode(enum.Enum):
    """How to pass the prompt to the CLI subprocess.

    INLINE: prompt embedded in the command line (risks E2BIG for large prompts).
    STDIN:  prompt piped via stdin (safe for any size).
    FILE:   prompt offloaded to a temp file when it exceeds a threshold.
    """

    INLINE = "inline"
    STDIN = "stdin"
    FILE = "file"


def _convert_large_input_mode(value: Any) -> LargeInputMode:
    """Converter for ``large_input_mode`` attrib — accepts str or enum."""
    if isinstance(value, LargeInputMode):
        return value
    if isinstance(value, str):
        return LargeInputMode(value.lower())
    raise TypeError(
        f"large_input_mode must be LargeInputMode or str, got {type(value).__name__}"
    )


class TerminalInferencerResponse(dict):
    """Dict response with ``__str__`` returning clean output text.

    Follows the same pattern as ``SDKInferencerResponse``: ``str()`` returns
    the main content, while metadata (session_id, stderr, return_code, etc.)
    remains accessible via dict keys for backward compatibility.
    """

    def __str__(self) -> str:
        return self.get("output") or self.get("raw_output", "")


@attrs
class TerminalSessionInferencerBase(StreamingInferencerBase):
    """Base for CLI/terminal-based streaming inferencers.

    Executes commands via subprocess and streams stdout line-by-line.
    Subclasses implement ``construct_command()``, ``parse_output()``,
    and ``_build_session_args()``.

    Attributes:
        working_dir: Working directory for subprocess execution.
        pre_exec_scripts: Shell commands to run before the main command.
        session_arg_name: CLI argument name for session ID.
        resume_arg_name: CLI argument name for resume flag.
        large_input_mode: How to pass the prompt to the subprocess. See
            ``LargeInputMode`` enum. Default: ``INLINE``. When
            ``use_file_for_large_arg_exceeding_size`` is set at init time
            and ``large_input_mode`` is still ``INLINE``, the mode is
            auto-promoted to ``FILE`` (preserving backward compatibility).
        use_file_for_large_arg_exceeding_size: Controls automatic offloading
            of large arguments to temp files to avoid ARG_MAX / E2BIG errors.
            See class docstring for details on accepted value types.
        large_arg_file_template: Template for the replacement text when an
            argument is offloaded. Must contain ``{file_path}``.
        large_arg_temp_dir: Directory for temp files. If None, uses system
            temp dir. Callers should set this to the run's ``_runtime``
            folder for reliable cleanup and debugging.
        enable_shell: If True (default), the shell/command execution tool is
            enabled in the agent config. If False, shell is disabled entirely,
            and ``allowed_shell_commands`` is ignored.
        allowed_shell_commands: Optional list of additional shell commands to
            allow (e.g., ``["nvidia-smi", "nvcc"]``). For devmate backends,
            these are added to the config's ``allowed_commands`` list. For
            Claude Code backends, this logs an info message (no per-command
            allowlist API exists).
    """

    # Terminal-specific attributes
    working_dir: Optional[str] = attrib(default=None)
    pre_exec_scripts: Optional[List[str]] = attrib(default=None)
    session_arg_name: str = attrib(default="--session-id")
    resume_arg_name: str = attrib(default="--resume")

    # Shell control
    enable_shell: bool = attrib(default=True)
    allowed_shell_commands: Optional[List[str]] = attrib(default=None)

    # Large input handling
    large_input_mode: LargeInputMode = attrib(
        default=LargeInputMode.INLINE,
        converter=_convert_large_input_mode,
    )

    # Large argument file offload configuration
    use_file_for_large_arg_exceeding_size: Optional[
        Union[bool, int, List[str], Dict[str, int]]
    ] = attrib(default=None)
    large_arg_file_template: str = attrib(
        default="The content is saved in file at path: {file_path}. "
        "Please read from the file."
    )
    large_arg_temp_dir: Optional[str] = attrib(default=None)

    # Internal state for streaming result
    _last_streaming_output: str = attrib(default="", init=False, repr=False)
    _last_streaming_stderr: str = attrib(default="", init=False, repr=False)
    _last_streaming_return_code: int = attrib(default=0, init=False, repr=False)

    # First ``__attrs_post_init__`` at this level — subclasses MUST call
    # ``super().__attrs_post_init__()`` to preserve the chain.
    def __attrs_post_init__(self) -> None:
        """Auto-promote large_input_mode and validate shell config."""
        val = self.use_file_for_large_arg_exceeding_size
        if (
            val is not None
            and val is not False
            and self.large_input_mode == LargeInputMode.INLINE
        ):
            self.large_input_mode = LargeInputMode.FILE
        if not self.enable_shell and self.allowed_shell_commands:
            logger.warning(
                "[%s] enable_shell=False takes precedence; "
                "allowed_shell_commands=%s will be ignored.",
                self.__class__.__name__,
                self.allowed_shell_commands,
            )
        self._generator_cleanup_timeout = 10.0
        super().__attrs_post_init__()

    # === Abstract Methods ===

    @abstractmethod
    def construct_command(self, inference_input: Any, **kwargs: Any) -> str:
        """Build the shell command string.

        Args:
            inference_input: The input data (prompt string or dict).
            **kwargs: Additional arguments (session_id, resume, etc.).

        Returns:
            Shell command string.
        """
        raise NotImplementedError

    @abstractmethod
    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> TerminalInferencerResponse:
        """Parse command output into a response object.

        Args:
            stdout: Standard output from command.
            stderr: Standard error from command.
            return_code: Process return code.

        Returns:
            Response object (dict subclass with ``__str__`` returning
            the clean output text).
        """
        raise NotImplementedError

    @abstractmethod
    def _build_session_args(self, session_id: str, is_resume: bool) -> str:
        """Build CLI session arguments.

        Args:
            session_id: The session ID.
            is_resume: Whether this is a resume operation.

        Returns:
            CLI argument string.
        """
        raise NotImplementedError

    # === Subprocess timeout helper ===

    def _resolve_subprocess_timeout(
        self, subprocess_timeout_override: Optional[float] = None
    ) -> Optional[float]:
        """Resolve subprocess timeout.

        For sync ``_infer()`` which uses ``subprocess.run()`` (no streaming),
        use a generous floor of 1800s (30 min) to avoid killing legitimate
        long-running agent tasks.

        Args:
            subprocess_timeout_override: Per-call override. Callers should
                ``kwargs.pop("subprocess_timeout_seconds", None)`` and pass
                the result here so the key is consumed before reaching
                ``construct_command()``.

        Returns:
            Timeout in seconds, or None for no timeout.
        """
        if subprocess_timeout_override is not None:
            return (
                subprocess_timeout_override if subprocess_timeout_override > 0 else None
            )
        return (
            max(self.idle_timeout_seconds, 1800)
            if self.idle_timeout_seconds > 0
            else None
        )

    # === Timeout resolution for CLI ===

    def _resolve_timeouts(
        self,
        idle_timeout: float | None,
        tool_use_timeout: float | None,
    ) -> tuple[float | None, float | None]:
        """Pre-merge timeouts for CLI inferencers.

        CLI subprocesses stream raw stdout lines and cannot produce
        empty-string activity sentinels, so the dual-timer never switches.
        Pre-merge to ``max(idle, tool_use)`` as a single flat timeout.
        """
        if idle_timeout is not None and tool_use_timeout is not None:
            return max(idle_timeout, tool_use_timeout), None
        if tool_use_timeout is not None:
            return tool_use_timeout, None
        return idle_timeout, None

    # === Large-arg offload helpers ===

    def _resolve_large_arg_config(self) -> Optional[Dict[str, int]]:
        """Normalize ``use_file_for_large_arg_exceeding_size`` into ``{arg_name: threshold}``.

        Key ``"*"`` means "apply to all args in inference_input".

        Returns:
            Dict mapping arg names to byte thresholds, or ``None`` if disabled.

        Raises:
            ValueError: If a negative integer threshold is provided.
        """
        val = self.use_file_for_large_arg_exceeding_size
        if val is None or val is False:
            return None
        if val is True:
            return {"*": _DEFAULT_LARGE_ARG_THRESHOLD}
        # bool is a subclass of int in Python, but True/False are already
        # handled above via identity checks, so only actual ints reach here.
        if isinstance(val, int):
            if val < 0:
                raise ValueError(
                    f"use_file_for_large_arg_exceeding_size must be >= 0, got {val}"
                )
            return {"*": val}
        if isinstance(val, list):
            from rankevolve.src.utils.common_utils.system_helper import (
                get_available_arg_space,
                get_max_single_arg_size,
            )

            available = get_available_arg_space()
            # create_subprocess_shell passes the entire command as a
            # *single* argument to ``/bin/sh -c``.  Linux enforces a
            # per-argument limit (MAX_ARG_STRLEN = PAGE_SIZE*32, typically
            # 128 KB) that is much stricter than ARG_MAX (~2 MB).
            # Use the more restrictive of the two limits.
            max_single = get_max_single_arg_size()
            effective = min(available, max_single)
            per_arg = effective // max(len(val), 1)
            return {k: per_arg for k in val}
        if isinstance(val, dict):
            return val
        logger.warning(
            "[%s] use_file_for_large_arg_exceeding_size has unexpected type %s, "
            "disabling offload. Expected None, bool, int, list, or dict.",
            self.__class__.__name__,
            type(val).__name__,
        )
        return None

    def _maybe_offload_large_args_to_file(
        self, inference_input: Any
    ) -> Tuple[Any, List[str]]:
        """Write args exceeding their threshold to temp files, replacing with references.

        Args:
            inference_input: The original inference input (dict or string).

        Returns:
            Tuple of ``(modified_inference_input, list_of_temp_file_paths)``.
            The caller is responsible for calling ``_cleanup_temp_files``
            on the returned list.
        """
        config = self._resolve_large_arg_config()
        if config is None:
            return inference_input, []

        # Normalize to dict
        if isinstance(inference_input, str):
            input_dict: Dict[str, Any] = {"prompt": inference_input}
            was_string = True
        elif isinstance(inference_input, dict):
            input_dict = dict(inference_input)  # shallow copy
            was_string = False
        else:
            return inference_input, []

        wildcard_threshold = config.get("*")
        modified = False
        temp_files: List[str] = []

        for key, value in input_dict.items():
            if not isinstance(value, str):
                continue

            # Determine threshold: explicit key > wildcard.
            # Use dict membership, NOT ``or``, to handle falsy threshold=0.
            threshold = config[key] if key in config else wildcard_threshold
            if threshold is None:
                continue

            value_bytes = len(value.encode("utf-8"))
            if value_bytes <= threshold:
                continue

            # Write to temp file — use configured dir or system tmp
            try:
                temp_dir = self.large_arg_temp_dir
                if temp_dir:
                    os.makedirs(temp_dir, exist_ok=True)
                fd, file_path = tempfile.mkstemp(
                    suffix=".txt",
                    prefix=f"arg_offload_{key}_",
                    dir=temp_dir,
                )
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(value)
            except OSError as e:
                logger.warning(
                    "[%s] Failed to create temp file for arg '%s' (%d bytes): %s. "
                    "Falling back to inline arg (may hit ARG_MAX).",
                    self.__class__.__name__,
                    key,
                    value_bytes,
                    e,
                )
                continue

            temp_files.append(file_path)
            logger.info(
                "[%s] Arg '%s' offloaded to file: %d bytes > %d threshold -> %s",
                self.__class__.__name__,
                key,
                value_bytes,
                threshold,
                file_path,
            )

            input_dict[key] = self.large_arg_file_template.format(file_path=file_path)
            modified = True

        if not modified:
            return inference_input, []

        if was_string:
            return input_dict.get("prompt", inference_input), temp_files
        return input_dict, temp_files

    @staticmethod
    def _cleanup_temp_files(temp_files: List[str]) -> None:
        """Remove temp files created during arg offload."""
        for path in temp_files:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass

    # === Concrete: _ainfer_streaming (subprocess line streaming) ===

    async def _ainfer_streaming(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Yield lines from subprocess stdout.

        Satisfies the ``@abstractmethod`` contract from StreamingInferencerBase.
        Also captures stderr and return_code for use by ``_ainfer()``.

        Args:
            prompt: The prompt string.
            **kwargs: Additional arguments passed to ``construct_command()``.

        Yields:
            Lines from subprocess stdout.
        """
        temp_files: List[str] = []
        mode = kwargs.pop("large_input_mode", self.large_input_mode)

        if mode == LargeInputMode.STDIN:
            kwargs["use_stdin"] = True
            command = self.construct_command({"prompt": prompt}, **kwargs)
            full_command = self._build_full_command(command)
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                limit=_MAX_STDOUT_LINE_BYTES,
            )
            process.stdin.write(prompt.encode("utf-8"))  # pyre-ignore[16]
            await process.stdin.drain()  # pyre-ignore[16]
            process.stdin.close()  # pyre-ignore[16]
        elif mode == LargeInputMode.FILE:
            inference_input, temp_files = self._maybe_offload_large_args_to_file(
                {"prompt": prompt}
            )
            command = self.construct_command(inference_input, **kwargs)
            full_command = self._build_full_command(command)
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                limit=_MAX_STDOUT_LINE_BYTES,
            )
        else:
            # INLINE
            command = self.construct_command({"prompt": prompt}, **kwargs)
            full_command = self._build_full_command(command)
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                limit=_MAX_STDOUT_LINE_BYTES,
            )

        collected_stdout: list[str] = []
        try:
            # Use ``readuntil`` directly instead of ``async for line in stream``
            # so we can catch ``LimitOverrunError`` ourselves.  ``async for``
            # internally calls ``readline()`` which re-raises
            # ``LimitOverrunError`` as ``ValueError`` AND CLEARS the
            # over-the-limit data from the buffer — losing it irrecoverably.
            # ``readuntil()`` preserves the buffer on overflow, so we can
            # switch to chunked ``read()`` and stream the data out.
            while True:
                try:
                    line_bytes = await process.stdout.readuntil(  # pyre-ignore[16]
                        b"\n"
                    )
                except asyncio.IncompleteReadError as e:
                    # EOF without trailing newline — yield any partial
                    # content the subprocess emitted.
                    if e.partial:
                        line = e.partial.decode("utf-8", errors="replace")
                        collected_stdout.append(line)
                        yield line
                    break
                except asyncio.LimitOverrunError as e:
                    # A single stdout line exceeded ``_MAX_STDOUT_LINE_BYTES``
                    # (16 MB).  ``readuntil`` PRESERVES the over-the-limit
                    # data in the StreamReader buffer (unlike ``readline``
                    # which clears it on overflow), so we can switch to
                    # chunked ``read()`` to drain everything remaining
                    # without losing data.  Line semantics are sacrificed
                    # for the rest of this stream — caller still receives
                    # the full content via ``_last_streaming_output``.
                    # The retry layer in ``InferencerBase.ainfer`` treats
                    # ``LimitOverrunError`` as non-retryable (P4) — but we
                    # explicitly do NOT re-raise here because the chunked
                    # fallback successfully recovers the content.
                    logger.warning(
                        "[%s] subprocess stdout line exceeded %d-byte buffer "
                        "(consumed=%d); falling back to chunked read",
                        self.__class__.__name__,
                        _MAX_STDOUT_LINE_BYTES,
                        getattr(e, "consumed", -1),
                    )
                    while True:
                        chunk_bytes = await process.stdout.read(  # pyre-ignore[16]
                            _MAX_STDOUT_LINE_BYTES
                        )
                        if not chunk_bytes:
                            break
                        chunk = chunk_bytes.decode("utf-8", errors="replace")
                        collected_stdout.append(chunk)
                        yield chunk
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                collected_stdout.append(line)
                yield line
        finally:
            stderr_bytes = await process.stderr.read() if process.stderr else b""
            self._last_streaming_stderr = stderr_bytes.decode("utf-8", errors="replace")
            await process.wait()
            self._last_streaming_output = "".join(collected_stdout)
            self._last_streaming_return_code = process.returncode or 0
            self._cleanup_temp_files(temp_files)

    # === Concrete: _build_full_command ===

    def _build_full_command(self, command: str) -> str:
        """Prepend ``pre_exec_scripts`` to the main command.

        Args:
            command: The main command string.

        Returns:
            Full command string with pre-exec scripts chained via ``&&``.
        """
        parts: list[str] = []
        if self.pre_exec_scripts:
            parts.extend(self.pre_exec_scripts)
        parts.append(command)
        return " && ".join(parts)

    # === parse_output() wrapper — guarantees TerminalInferencerResponse return ===

    def _parse_output_wrapped(
        self, stdout: str, stderr: str, return_code: int
    ) -> "TerminalInferencerResponse":
        """``parse_output()`` with guaranteed ``TerminalInferencerResponse`` return.

        Subclass ``parse_output()`` may return a plain ``dict`` (e.g.,
        ``DevmateCliInferencer``, ``ClaudeCodeCliInferencer``). A plain
        ``dict``'s ``__str__`` falls back to ``dict.__repr__``, which escapes
        real newlines to literal ``\\n`` two-character sequences — corrupting
        any artifact persisted via ``f.write(str(response))`` (see
        ``DualInferencer`` propose/review/fix steps in
        ``flow_inferencers/dual_inferencer.py``). Wrapping in
        ``TerminalInferencerResponse`` (a ``dict`` subclass whose ``__str__``
        returns ``output``/``raw_output``) makes downstream ``str(response)``
        calls safe across all subclasses.

        Idempotent: already-wrapped responses (e.g., ``MetamateCliInferencer``
        which already returns ``TerminalInferencerResponse``) pass through
        unchanged.
        """
        result = self.parse_output(stdout, stderr, return_code)
        if isinstance(result, TerminalInferencerResponse):
            return result
        if isinstance(result, dict):
            return TerminalInferencerResponse(result)
        # Defensive: non-dict subclass returns become empty TIR with str(result)
        # in the ``output`` slot.  Should not happen given the abstractmethod
        # signature, but cheaper than crashing downstream consumers.
        return TerminalInferencerResponse(
            output=str(result) if result is not None else ""
        )

    # === Concrete: _ainfer and _infer (non-streaming execution) ===

    async def _ainfer(
        self, inference_input: Any, inference_config: Any = None, **kwargs: Any
    ) -> Any:
        """Execute command via streaming pipeline and return parsed output dict.

        Delegates to ``super()._ainfer()`` which goes through
        ``ainfer_streaming()`` → ``_ainfer_streaming()``, providing:
        - Cache file writing (if ``cache_folder`` is set)
        - Per-chunk idle timeout (via ``idle_timeout_seconds``)

        After streaming completes, ``_ainfer_streaming()`` stores stdout,
        stderr, and return_code in instance variables. These are then
        passed to ``parse_output()`` for structured result formatting.

        Args:
            inference_input: Input data for inference.
            inference_config: Optional configuration (unused).
            **kwargs: Additional arguments passed to ``construct_command()``.

        Returns:
            Parsed result dictionary from ``parse_output()``.
        """
        # Reset streaming state before each call
        self._last_streaming_output = ""
        self._last_streaming_stderr = ""
        self._last_streaming_return_code = 0

        # Use streaming pipeline (inherits cache + idle timeout)
        accumulated = await super()._ainfer(inference_input, inference_config, **kwargs)

        # _ainfer_streaming() stored stdout, stderr, return_code
        stdout = self._last_streaming_output or str(accumulated)
        stderr = self._last_streaming_stderr
        return_code = self._last_streaming_return_code

        return self._parse_output_wrapped(stdout, stderr, return_code)

    def _infer(
        self, inference_input: Any, inference_config: Any = None, **kwargs: Any
    ) -> Any:
        """Sync execution via subprocess.run().

        Args:
            inference_input: Input data for inference.
            inference_config: Optional configuration (unused).
            **kwargs: Additional arguments passed to ``construct_command()``.

        Returns:
            Parsed result dictionary from ``parse_output()``.
        """
        temp_files: List[str] = []
        mode = kwargs.pop("large_input_mode", self.large_input_mode)
        timeout = self._resolve_subprocess_timeout(
            kwargs.pop("subprocess_timeout_seconds", None)
        )

        if mode == LargeInputMode.STDIN:
            prompt = self._extract_prompt(inference_input)
            kwargs["use_stdin"] = True
            command = self.construct_command(inference_input, **kwargs)
            full_command = self._build_full_command(command)
            try:
                result = subprocess.run(
                    full_command,
                    shell=True,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    cwd=self.working_dir,
                    timeout=timeout,
                )
                return self._parse_output_wrapped(
                    result.stdout, result.stderr, result.returncode
                )
            finally:
                self._cleanup_temp_files(temp_files)
        elif mode == LargeInputMode.FILE:
            inference_input, temp_files = self._maybe_offload_large_args_to_file(
                inference_input
            )
            command = self.construct_command(inference_input, **kwargs)
            full_command = self._build_full_command(command)
            try:
                result = subprocess.run(
                    full_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.working_dir,
                    timeout=timeout,
                )
                return self._parse_output_wrapped(
                    result.stdout, result.stderr, result.returncode
                )
            finally:
                self._cleanup_temp_files(temp_files)
        else:
            # INLINE
            command = self.construct_command(inference_input, **kwargs)
            full_command = self._build_full_command(command)
            try:
                result = subprocess.run(
                    full_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.working_dir,
                    timeout=timeout,
                )
                return self._parse_output_wrapped(
                    result.stdout, result.stderr, result.returncode
                )
            finally:
                self._cleanup_temp_files(temp_files)

    # === Concrete: _infer_streaming (sync subprocess line streaming) ===

    def _infer_streaming(
        self,
        inference_input: Any,
        stream_callback: Any = None,
        output_stream: Any = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Sync subprocess streaming — yields stdout lines.

        Note: Sync streaming cannot enforce idle_timeout. Use
        ``ainfer_streaming()`` for timeout-guarded streaming.

        Known limitation: Opens ``stderr=subprocess.PIPE`` but only reads
        stderr after stdout is exhausted. If the subprocess writes more
        than ~64KB to stderr before stdout is consumed, the OS pipe buffer
        fills and the subprocess blocks — causing a deadlock. Non-trivial
        to fix in sync (reading stderr after stdout risks deadlock if
        process is already blocked; ``communicate()`` breaks line-by-line
        streaming). Recommend async path for large-stderr scenarios.

        Args:
            inference_input: Input data for inference.
            stream_callback: Optional callback for each line (unused by base).
            output_stream: Optional output stream (unused by base).
            **kwargs: Additional arguments passed to ``construct_command()``.

        Yields:
            Lines from subprocess stdout.
        """
        temp_files: List[str] = []
        mode = kwargs.pop("large_input_mode", self.large_input_mode)

        if mode == LargeInputMode.STDIN:
            prompt = self._extract_prompt(inference_input)
            kwargs["use_stdin"] = True
            command = self.construct_command(inference_input, **kwargs)
            full_command = self._build_full_command(command)
            # Note: For very large prompts (>64KB), stdin.write() may block
            # if the process produces stdout before consuming all of stdin,
            # causing a classic pipe deadlock. In practice this is low-risk
            # because DevMate defaults to FILE mode and most CLIs read all
            # stdin before producing output. Use async path or FILE mode
            # for large-prompt scenarios.
            process = subprocess.Popen(
                full_command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.working_dir,
            )
            process.stdin.write(prompt)  # pyre-ignore[16]
            process.stdin.close()  # pyre-ignore[16]
        elif mode == LargeInputMode.FILE:
            inference_input, temp_files = self._maybe_offload_large_args_to_file(
                inference_input
            )
            command = self.construct_command(inference_input, **kwargs)
            full_command = self._build_full_command(command)
            process = subprocess.Popen(
                full_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.working_dir,
            )
        else:
            # INLINE
            command = self.construct_command(inference_input, **kwargs)
            full_command = self._build_full_command(command)
            process = subprocess.Popen(
                full_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.working_dir,
            )

        collected: list[str] = []
        try:
            for line in process.stdout:  # pyre-ignore[16]
                collected.append(line)
                yield line
        finally:
            process.wait()
            self._last_streaming_output = "".join(collected)
            self._last_streaming_stderr = (
                process.stderr.read() if process.stderr else ""
            )
            self._last_streaming_return_code = process.returncode or 0
            self._cleanup_temp_files(temp_files)
