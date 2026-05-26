import asyncio
from typing import Any

from python_utils.algorithms.graph.async_node import AsyncNode
from python_utils.algorithms.tree.tree import Tree

_NUM_NODES_REQUEST = "__async_tree_num_nodes__"


class AsyncTree(AsyncNode, Tree):
    """An async-capable tree node.

    Combines Tree's encode/decode serialization with AsyncNode's
    send/receive communication. Inherits all behavior from both parents.
    """

    async def async_num_nodes(
            self,
            send_timeout: float = 5.0,
            receive_timeout: float = 5.0,
    ) -> int:
        """Count nodes using async send/receive. Dead nodes are excluded.

        Sends a count request to each child via ``send()``. Each child
        recursively counts its subtree and sends the result back to
        the parent via the ``previous`` link. Nodes that don't respond
        within the timeout are excluded (assumed dead).

        Args:
            send_timeout: Maximum seconds to wait for each send to complete.
            receive_timeout: Maximum seconds to wait for each response.

        Returns:
            int: The total node count (including this node), excluding
            dead subtrees.

        Examples:
            >>> import asyncio
            >>> async def demo():
            ...     root = AsyncTree("A")
            ...     root.add_next(AsyncTree("B"))
            ...     root.add_next(AsyncTree("C"))
            ...     root.next[0].add_next(AsyncTree("D"))
            ...     return await root.async_num_nodes()
            >>> asyncio.run(demo())
            4
        """
        count = 1
        children = self.get_next() or []
        async_children = [c for c in children if isinstance(c, AsyncTree)]

        if not async_children:
            return count

        if self._queue is not None:
            # Send request to all children, then collect from own queue
            expected = 0
            for child in async_children:
                try:
                    await asyncio.wait_for(
                        self.send(_NUM_NODES_REQUEST, target=child),
                        timeout=send_timeout,
                    )
                    expected += 1
                except (asyncio.TimeoutError, Exception):
                    pass

            remaining = receive_timeout
            for _ in range(expected):
                try:
                    start = asyncio.get_event_loop().time()
                    result = await asyncio.wait_for(
                        self.receive(), timeout=remaining
                    )
                    if isinstance(result, int):
                        count += result
                    elapsed = asyncio.get_event_loop().time() - start
                    remaining = max(0, remaining - elapsed)
                except (asyncio.TimeoutError, Exception):
                    break
        else:
            # Direct mode: on_receive completes before send returns,
            # so the child's result is available immediately.
            for child in async_children:
                try:
                    await asyncio.wait_for(
                        self.send(_NUM_NODES_REQUEST, target=child),
                        timeout=send_timeout,
                    )
                    count += child._num_nodes_result
                except (asyncio.TimeoutError, Exception):
                    pass

        return count

    async def _handle_tree_message(self, message: Any):
        """Process an AsyncTree protocol message."""
        if message == _NUM_NODES_REQUEST:
            self._num_nodes_result = await self.async_num_nodes()
            # If parent has a queue, send result there for collection
            parents = self.get_previous()
            if parents:
                for parent in parents:
                    if isinstance(parent, AsyncNode) and parent._queue is not None:
                        await self.send(self._num_nodes_result, target=parent)
                        
    async def on_receive(self, message: Any):
        """Handle incoming messages. Processes tree protocol messages.

        Subclasses can override and call ``await super().on_receive(message)``
        to preserve tree protocol handling while adding custom logic.
        """
        await self._handle_tree_message(message)
