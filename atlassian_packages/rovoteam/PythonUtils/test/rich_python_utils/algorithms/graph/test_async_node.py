"""
Unit tests for AsyncNode.

Tests cover construction, direct-mode delivery, queue-mode delivery,
broadcast vs targeted send, mixed modes, and error handling.
"""

import asyncio

import pytest

from python_utils.algorithms.graph.async_node import AsyncNode
from python_utils.algorithms.graph.node import Node


# ---------------------------------------------------------------------------
# Helper subclass that records received messages (direct mode)
# ---------------------------------------------------------------------------

class RecordingNode(AsyncNode):
    """AsyncNode subclass that records messages received via on_receive."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received = []

    async def on_receive(self, message):
        self.received.append(message)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestAsyncNodeConstruction:

    def test_inherits_node(self):
        node = AsyncNode("A")
        assert isinstance(node, Node)

    def test_default_mode_is_direct(self):
        node = AsyncNode("A")
        assert node._queue is None

    def test_queue_mode_creates_queue(self):
        node = AsyncNode("A", use_queue=True)
        assert isinstance(node._queue, asyncio.Queue)

    def test_value_preserved(self):
        node = AsyncNode("hello")
        assert node.value == "hello"

    def test_add_next_works(self):
        a = AsyncNode("A")
        b = AsyncNode("B")
        a.add_next(b)
        assert b in a.next
        assert a in b.previous


# ---------------------------------------------------------------------------
# Direct mode
# ---------------------------------------------------------------------------

class TestDirectMode:

    def test_send_triggers_on_receive(self):
        async def _test():
            a = AsyncNode("A")
            b = RecordingNode("B")
            a.add_next(b)
            await a.send("hello")
            assert b.received == ["hello"]
        asyncio.run(_test())

    def test_send_multiple_messages(self):
        async def _test():
            a = AsyncNode("A")
            b = RecordingNode("B")
            a.add_next(b)
            await a.send("m1")
            await a.send("m2")
            await a.send("m3")
            assert b.received == ["m1", "m2", "m3"]
        asyncio.run(_test())

    def test_default_on_receive_is_noop(self):
        """Default on_receive does nothing and doesn't raise."""
        async def _test():
            a = AsyncNode("A")
            b = AsyncNode("B")
            a.add_next(b)
            await a.send("ignored")
        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Queue mode
# ---------------------------------------------------------------------------

class TestQueueMode:

    def test_send_enqueues(self):
        async def _test():
            a = AsyncNode("A")
            b = AsyncNode("B", use_queue=True)
            a.add_next(b)
            await a.send("msg")
            assert not b._queue.empty()
        asyncio.run(_test())

    def test_receive_dequeues(self):
        async def _test():
            a = AsyncNode("A")
            b = AsyncNode("B", use_queue=True)
            a.add_next(b)
            await a.send("msg")
            result = await b.receive()
            assert result == "msg"
            assert b._queue.empty()
        asyncio.run(_test())

    def test_fifo_order(self):
        async def _test():
            a = AsyncNode("A")
            b = AsyncNode("B", use_queue=True)
            a.add_next(b)
            await a.send("first")
            await a.send("second")
            await a.send("third")
            assert await b.receive() == "first"
            assert await b.receive() == "second"
            assert await b.receive() == "third"
        asyncio.run(_test())

    def test_receive_without_queue_raises(self):
        async def _test():
            node = AsyncNode("A")
            with pytest.raises(RuntimeError, match="queue mode"):
                await node.receive()
        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Broadcast vs targeted send
# ---------------------------------------------------------------------------

class TestBroadcastAndTargeted:

    def test_broadcast_to_all_next(self):
        async def _test():
            a = AsyncNode("A")
            b = RecordingNode("B")
            c = RecordingNode("C")
            a.add_next(b)
            a.add_next(c)
            await a.send("broadcast")
            assert b.received == ["broadcast"]
            assert c.received == ["broadcast"]
        asyncio.run(_test())

    def test_targeted_single_node(self):
        async def _test():
            a = AsyncNode("A")
            b = RecordingNode("B")
            c = RecordingNode("C")
            a.add_next(b)
            a.add_next(c)
            await a.send("only-b", target=b)
            assert b.received == ["only-b"]
            assert c.received == []
        asyncio.run(_test())

    def test_targeted_list_of_nodes(self):
        async def _test():
            a = AsyncNode("A")
            b = RecordingNode("B")
            c = RecordingNode("C")
            d = RecordingNode("D")
            a.add_next(b)
            a.add_next(c)
            a.add_next(d)
            await a.send("subset", target=[b, d])
            assert b.received == ["subset"]
            assert c.received == []
            assert d.received == ["subset"]
        asyncio.run(_test())

    def test_send_with_no_next_nodes(self):
        """send() on a node with no next nodes should be a no-op."""
        async def _test():
            a = AsyncNode("A")
            await a.send("void")
        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Mixed modes
# ---------------------------------------------------------------------------

class TestMixedModes:

    def test_mixed_queue_and_direct_targets(self):
        async def _test():
            a = AsyncNode("A")
            b = RecordingNode("B")  # direct mode
            c = AsyncNode("C", use_queue=True)  # queue mode
            a.add_next(b)
            a.add_next(c)
            await a.send("mixed")
            assert b.received == ["mixed"]
            assert await c.receive() == "mixed"
        asyncio.run(_test())

    def test_plain_node_neighbors_are_skipped(self):
        """Plain Node instances in next list should be silently skipped."""
        async def _test():
            a = AsyncNode("A")
            plain = Node("plain")
            b = RecordingNode("B")
            a.add_next(plain)
            a.add_next(b)
            await a.send("hello")
            assert b.received == ["hello"]
        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Node inheritance behavior
# ---------------------------------------------------------------------------

class TestInheritedBehavior:

    def test_bfs_still_works(self):
        a = AsyncNode("A")
        b = AsyncNode("B")
        c = AsyncNode("C")
        a.add_next(b)
        b.add_next(c)
        assert a.bfs("C") is True
        assert a.bfs("X") is False

    def test_str_all_descendants(self):
        a = AsyncNode("A")
        b = AsyncNode("B")
        a.add_next(b)
        output = a.str_all_descendants(ascii_tree=True).strip()
        assert "A" in output
        assert "B" in output

    def test_identity_equality(self):
        a = AsyncNode("A")
        b = AsyncNode("A")
        assert a != b
        assert a == a
