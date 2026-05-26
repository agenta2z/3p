import asyncio
from typing import Any, List, Optional, Union

from attr import attrs, attrib

from python_utils.algorithms.graph.node import Node


@attrs(slots=False, eq=False, hash=False)
class AsyncNode(Node):
    """An async-capable node that supports send/receive communication.

    Extends Node with asynchronous message passing between connected nodes.
    Supports two delivery modes:

    - **Direct mode** (default): ``send()`` directly awaits ``on_receive()``
      on each target node. Override ``on_receive`` in subclasses to handle
      incoming messages.
    - **Queue mode** (``use_queue=True``): ``send()`` enqueues messages into
      the target's internal ``asyncio.Queue``. The target consumes messages
      by awaiting ``receive()``.

    The delivery mode is determined per *target* node, so a graph can mix
    both styles freely.

    Attributes:
        value: The value associated with this node (inherited from Node).
        next: Successor node(s) (inherited from Node).
        previous: Predecessor node(s) (inherited from Node).

    Examples:
        Direct mode — override ``on_receive``:

        >>> import asyncio
        >>> class EchoNode(AsyncNode):
        ...     def __init__(self, *args, **kwargs):
        ...         super().__init__(*args, **kwargs)
        ...         self.received = []
        ...     async def on_receive(self, message):
        ...         self.received.append(message)

        >>> async def demo_direct():
        ...     a = EchoNode("A")
        ...     b = EchoNode("B")
        ...     a.add_next(b)
        ...     await a.send("hello")
        ...     return b.received
        >>> asyncio.run(demo_direct())
        ['hello']

        Queue mode — ``send`` enqueues, ``receive`` dequeues:

        >>> async def demo_queue():
        ...     a = AsyncNode("A")
        ...     b = AsyncNode("B", use_queue=True)
        ...     a.add_next(b)
        ...     await a.send("msg1")
        ...     await a.send("msg2")
        ...     first = await b.receive()
        ...     second = await b.receive()
        ...     return [first, second]
        >>> asyncio.run(demo_queue())
        ['msg1', 'msg2']
    """

    _use_queue: bool = attrib(default=False, repr=False, kw_only=True)
    _queue: Optional[asyncio.Queue] = attrib(default=None, init=False, repr=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self._use_queue:
            self._queue = asyncio.Queue()

    async def send(self, message: Any, target: Union['AsyncNode', List['AsyncNode']] = None):
        """Send a message to connected next node(s).

        Args:
            message: The message payload (any Python object).
            target: One or more ``AsyncNode`` instances to deliver to.
                If ``None``, broadcasts to all next nodes. Plain ``Node``
                instances in the target list are silently skipped.

        Examples:
            >>> import asyncio
            >>> async def demo():
            ...     a = AsyncNode("A")
            ...     b = AsyncNode("B", use_queue=True)
            ...     c = AsyncNode("C", use_queue=True)
            ...     a.add_next(b)
            ...     a.add_next(c)
            ...     # Broadcast
            ...     await a.send("broadcast")
            ...     assert await b.receive() == "broadcast"
            ...     assert await c.receive() == "broadcast"
            ...     # Targeted
            ...     await a.send("only-b", target=b)
            ...     assert await b.receive() == "only-b"
            ...     assert c._queue.empty()
            >>> asyncio.run(demo())
        """
        if target is not None:
            targets = target if isinstance(target, list) else [target]
        else:
            targets = self.get_next() or []

        for node in targets:
            if isinstance(node, AsyncNode):
                await node._deliver(message)

    async def _deliver(self, message: Any):
        """Route an incoming message to the queue or the on_receive handler."""
        if self._queue is not None:
            await self._queue.put(message)
        else:
            await self.on_receive(message)

    async def receive(self) -> Any:
        """Dequeue the next message. Requires queue mode.

        Returns:
            The next message from the internal queue.

        Raises:
            RuntimeError: If called on a node without queue mode enabled.

        Examples:
            >>> import asyncio
            >>> async def demo():
            ...     node = AsyncNode("N", use_queue=True)
            ...     await node._deliver("hello")
            ...     return await node.receive()
            >>> asyncio.run(demo())
            'hello'
        """
        if self._queue is None:
            raise RuntimeError("receive() requires queue mode (use_queue=True)")
        return await self._queue.get()

    async def on_receive(self, message: Any):
        """Handler invoked in direct mode when a message arrives.

        Override this method in subclasses to define custom message handling
        logic. The default implementation is a no-op.

        Args:
            message: The incoming message payload.
        """
        pass
