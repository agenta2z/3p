from bisect import insort_left, bisect_left
from heapq import heappop, heappush
from typing import List


class Scheduler:

    def __init__(self, num_servers):
        self.num_servers = num_servers
        # free servers, kept sorted for binary search
        self._free = list(range(num_servers))
        # busy servers: (finish_time, server_id)
        self._busy = []

        self._i = 0

    def next(self, time, workload):
        """
        Handle the next incoming request.

        Args:
            time (int): The arrival time of the request.
            workload (int): The time duration the request will occupy a server.

        Returns:
            int: The ID of the server that handles the request,
                 or -1 if no server is available.

        Examples:
            >>> sched = Scheduler(2)
            >>> # First request -> server 0
            >>> sched.next(0, 5)
            0
            >>> # Next arrives before server 0 frees, goes to server 1
            >>> sched.next(1, 3)
            1
            >>> # Both busy at time 2 -> drop (-1)
            >>> sched.next(2, 1)
            -1

        """
        # 1) reclaim...
        while self._busy and self._busy[0][0] <= time:
            finish_time, sid = heappop(self._busy)
            insort_left(self._free, sid)

        # 2) advance the request index
        start_idx = self._i % self.num_servers
        self._i += 1

        if not self._free:
            return -1

        # 3) find the free server >= start_idx
        j = bisect_left(self._free, start_idx)
        if j == len(self._free):
            j = 0
        sid = self._free.pop(j)

        # 4) schedule it as busy
        heappush(self._busy, (time + workload, sid))
        return sid


def busiest_servers(
        scheduler: Scheduler,
        arrival: List[int],
        workload: List[int]
) -> List[int]:
    """
    Determine which server(s) handled the most requests.

    This utility drives the scheduler through the full request stream,
    tallies assignments, and returns the IDs of the busiest server(s).

    Args:
        scheduler (Scheduler): An instance of the Scheduler class.
        arrival (List[int]): Arrival times of requests.
        workload (List[int]): Corresponding workloads (durations).

    Returns:
        List[int]: List of server IDs (0-indexed) with the maximum handled requests.

    Examples:
        >>> # Example 1 from LeetCode 1606
        >>> sched = Scheduler(3)
        >>> arrivals = [1,2,3,4,5]
        >>> loads    = [5,2,3,3,3]
        >>> busiest_servers(sched, arrivals, loads)
        [1]

        >>> # Custom Example
        >>> sched = Scheduler(3)
        >>> arrivals = [1,2,3,4,8,9,10]
        >>> loads    = [5,2,10,3,1,2,2]
        >>> busiest_servers(sched, arrivals, loads)
        [1]
    """
    # Count how many requests each server handles
    counts = [0] * scheduler.num_servers

    for time, _workload in zip(arrival, workload):
        sid = scheduler.next(time, _workload)
        if sid != -1:
            counts[sid] += 1

    # Find the maximum handled count and return all servers matching it
    max_count = max(counts)
    return [i for i, c in enumerate(counts) if c == max_count]
