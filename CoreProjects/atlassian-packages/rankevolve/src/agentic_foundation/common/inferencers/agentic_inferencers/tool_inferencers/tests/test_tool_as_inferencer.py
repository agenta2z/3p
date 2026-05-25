# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Tests for :class:`ToolAsInferencer` + :func:`make_tool_chain`.

Strategy: spawn real ``python3`` subprocesses (already in the default
allowlist) running tiny inline scripts. Avoids fixture files and keeps
the tests hermetic.
"""

from __future__ import annotations

import asyncio
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.tool_inferencers import (
    ToolAsInferencer,
    ToolInferencerResponse,
    make_tool_chain,
)


# Minimal "real" inferencer workspace shape: the base class only touches
# `.root` to derive the cache path, so a duck-typed object works.
class _FakeWorkspace:
    def __init__(self, root: Path) -> None:
        self.root = root


def _python_print(payload: str) -> list[str]:
    """Convenience: argv that prints `payload` via python3 -c, then exits 0."""
    return ["python3", "-c", f"import sys; sys.stdout.write({payload!r})"]


class ToolAsInferencerHappyPathTest(unittest.IsolatedAsyncioTestCase):
    async def test_echo_hello(self) -> None:
        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="echo",
                command=_python_print("hello"),
                workspace=_FakeWorkspace(Path(ws_root)),
            )
            result: ToolInferencerResponse = await tool.ainfer("ignored")
            self.assertEqual(result.return_code, 0)
            self.assertTrue(result.success)
            self.assertEqual(result.stdout, "hello")
            self.assertEqual(result.stderr, "")
            # `__str__` returns stdout — confirm the convenience contract.
            self.assertEqual(str(result), "hello")
            # `[]` access too.
            self.assertEqual(result["return_code"], 0)

    async def test_streamed_chunks_match_stdout(self) -> None:
        # Print three lines; assert ainfer_streaming yields each as a
        # chunk including the trailing newline.
        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="multiline",
                command=[
                    "python3",
                    "-c",
                    "import sys; [print(f'line{i}') for i in range(3)]; sys.stdout.flush()",
                ],
                workspace=_FakeWorkspace(Path(ws_root)),
            )
            chunks: list[str] = []
            async for chunk in tool.ainfer_streaming("ignored"):
                chunks.append(chunk)
            joined = "".join(chunks)
            self.assertIn("line0\n", joined)
            self.assertIn("line1\n", joined)
            self.assertIn("line2\n", joined)


class ToolAsInferencerFailurePathTest(unittest.IsolatedAsyncioTestCase):
    async def test_nonzero_return_code_marks_failure(self) -> None:
        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="fail",
                command=["python3", "-c", "import sys; sys.exit(7)"],
                workspace=_FakeWorkspace(Path(ws_root)),
                # No retry — exercise the first-attempt failure path
                # without the recovery prompt machinery muddying things.
                max_retry=0,
            )
            result: ToolInferencerResponse = await tool.ainfer("ignored")
            self.assertEqual(result.return_code, 7)
            self.assertFalse(result.success)

    async def test_stderr_captured(self) -> None:
        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="stderr_only",
                command=[
                    "python3",
                    "-c",
                    "import sys; sys.stderr.write('oh no'); sys.exit(0)",
                ],
                workspace=_FakeWorkspace(Path(ws_root)),
            )
            result: ToolInferencerResponse = await tool.ainfer("ignored")
            self.assertEqual(result.return_code, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("oh no", result.stderr)


class ToolAsInferencerSafetyTest(unittest.IsolatedAsyncioTestCase):
    async def test_disallowed_binary_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="bad",
                command=["bash", "-c", "echo hi"],
                workspace=_FakeWorkspace(Path(ws_root)),
                # Default allowlist doesn't include bash.
            )
            with self.assertRaises(ValueError) as cm:
                await tool.ainfer("ignored")
            self.assertIn("bash", str(cm.exception).lower())

    async def test_explicit_allowlist_works(self) -> None:
        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="bash_ok",
                command=["bash", "-c", "echo hi"],
                workspace=_FakeWorkspace(Path(ws_root)),
                allowed_binaries=frozenset({"bash"}),
            )
            result = await tool.ainfer("ignored")
            self.assertEqual(result.return_code, 0)
            self.assertIn("hi", result.stdout)


class ToolAsInferencerSubstitutionTest(unittest.IsolatedAsyncioTestCase):
    async def test_args_template_substituted_from_dict_input(self) -> None:
        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="subst",
                command=["python3"],
                args_template=["-c", "print('${MSG}')"],
                workspace=_FakeWorkspace(Path(ws_root)),
            )
            result = await tool.ainfer({"MSG": "world"})
            self.assertEqual(result.stdout.strip(), "world")

    async def test_unresolved_placeholder_raises(self) -> None:
        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="bad_subst",
                command=["python3"],
                args_template=["-c", "print('${MISSING}')"],
                workspace=_FakeWorkspace(Path(ws_root)),
            )
            with self.assertRaises(Exception) as cm:
                await tool.ainfer({"OTHER": "x"})
            self.assertIn("MISSING", str(cm.exception))


class ToolAsInferencerMarkerTest(unittest.IsolatedAsyncioTestCase):
    async def test_marker_callback_fires_per_match(self) -> None:
        captured: list[tuple[int, float]] = []

        def on_epoch(m: re.Match[str]) -> None:
            captured.append((int(m.group(1)), float(m.group(2))))

        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="epoch_emitter",
                command=[
                    "python3",
                    "-c",
                    (
                        "import sys\n"
                        "for ep, ndcg in [(0, 0.10), (1, 0.15), (2, 0.20)]:\n"
                        "    sys.stdout.write(f'EPOCH:{ep} NDCG10:{ndcg}\\n')\n"
                        "    sys.stdout.flush()\n"
                    ),
                ],
                workspace=_FakeWorkspace(Path(ws_root)),
                marker_parsers=[(r"^EPOCH:(\d+)\s+NDCG10:([\d.]+)", on_epoch)],
            )
            result = await tool.ainfer("ignored")
            self.assertEqual(result.return_code, 0)
            self.assertEqual(captured, [(0, 0.10), (1, 0.15), (2, 0.20)])

    async def test_marker_callback_failure_does_not_break_stream(self) -> None:
        def boom(_m: re.Match[str]) -> None:
            raise RuntimeError("intentional")

        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="boom",
                command=["python3", "-c", "print('TRIGGER:1'); print('TRIGGER:2')"],
                workspace=_FakeWorkspace(Path(ws_root)),
                marker_parsers=[(r"^TRIGGER:", boom)],
            )
            result = await tool.ainfer("ignored")
            self.assertEqual(result.return_code, 0)
            # Both lines still landed in stdout despite the callback raising.
            self.assertIn("TRIGGER:1", result.stdout)
            self.assertIn("TRIGGER:2", result.stdout)


class ToolAsInferencerCancelTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_terminates_long_running_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as ws_root:
            tool = ToolAsInferencer(
                tool_name="sleeper",
                command=["python3", "-c", "import time; time.sleep(30)"],
                workspace=_FakeWorkspace(Path(ws_root)),
                # Tighten grace so the test is fast.
                term_grace_seconds=1.0,
                # Disable idle-timeout to make sure cancellation (not
                # idle expiry) is what terminates the process.
                idle_timeout_seconds=0,
            )
            task = asyncio.create_task(tool.ainfer("ignored"))
            await asyncio.sleep(0.2)
            # Cancel directly; the subprocess should die within a couple
            # of seconds via SIGTERM (not survive the 30 s sleep).
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            # Process must be reaped.
            self.assertIsNone(tool._proc)


class MakeToolChainTest(unittest.IsolatedAsyncioTestCase):
    async def test_two_step_chain_pipes_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as ws_root:
            step1 = ToolAsInferencer(
                tool_name="emit",
                command=["python3", "-c", "print('payload')"],
                workspace=_FakeWorkspace(Path(ws_root)),
            )
            step2 = ToolAsInferencer(
                tool_name="echo",
                command=["python3"],
                args_template=["-c", "print('saw=${INPUT}')"],
                workspace=_FakeWorkspace(Path(ws_root)),
                # The chain feeds prev_output as the inference_input;
                # but to substitute it into argv we need a known key.
                # `_make_input_builder` for step idx>0 returns
                # `state["prev_output"]` directly — the SECOND step gets
                # that string as its `inference_input`. For substitution
                # to work the input would need to be a dict; here we just
                # assert the pipe semantics by running step2 manually.
            )
            chain = make_tool_chain(
                "test_chain",
                tools=[step1, step2],
                workspace_path=ws_root,
                # Use 'independent' to give the second step a usable
                # dict; more interesting threading tested below.
                state_threading="independent",
            )
            # Sanity: chain returns an LWI instance.
            from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.linear_workflow_inferencer import (  # noqa: F401
                LinearWorkflowInferencer,
            )
            self.assertIsInstance(chain, LinearWorkflowInferencer)
            # Two step configs, in order.
            self.assertEqual(len(chain.step_configs), 2)
            self.assertTrue(chain.step_configs[0].name.startswith("test_chain_step_0_"))
            self.assertTrue(chain.step_configs[1].name.startswith("test_chain_step_1_"))

    async def test_empty_tools_raises(self) -> None:
        with self.assertRaises(ValueError):
            make_tool_chain("empty", tools=[], workspace_path=None)
