from collections import defaultdict, Counter
from multiprocessing import cpu_count
from time import sleep
from typing import Union, Iterator, Iterable, List, Tuple, Set, Mapping

from tqdm import tqdm

from python_utils.common_utils import split_iter, merge_mappings, merge_list_valued_mappings, merge_set_valued_mappings, merge_counter_valued_mappings, sum_dicts
from python_utils.console_utils import hprint_message
from python_utils.datetime_utils.tictoc import tic, toc


def _check_num_p(num_p: int):
    if num_p <= 0:
        raise ValueError(f"The number of processes specified in `num_p` must be positive; "
                         f"got {num_p}.")


def get_suggested_num_workers(num_p: int = None):
    """
    Gets a suggested number of workers considering both the specified number by `num_p`,
    and the number of available CPUs. If `num_p` is `None` or 0 or a negative number,
    the number of CPUs minus 1 or 2 will be returned.
    Otherwise, the smaller number between `num_p` and the number of CPUs will be returned.

    Args:
        num_p: specify a desired number of workers.

    Returns: the suggested number of workers considering both the specified `num_p`
        and the number of available CPUs.

    """
    if num_p is None or num_p <= 0:
        num_workers = cpu_count()
        if num_workers <= 8:
            return num_workers - 1
        else:
            return num_workers - 2
    else:
        return min(num_p, cpu_count())


def dispatch_data(
        num_p: int,
        data_iter: Union[Iterator, Iterable, List],
        args: Tuple,
        verbose: bool = __debug__
) -> List[Tuple]:
    """
    Splits the provided data into chunks and prepares arguments for parallel processing.

    Args:
        num_p (int): The number of processes to split the data for.
        data_iter (Union[Iterator, Iterable, List]): The data to be split and dispatched.
        args (Tuple): Additional arguments to be passed to each process.
        verbose (bool): If True, prints progress and debug information.

    Returns:
        List[Tuple]: A list of tuples where each tuple contains the process ID, a chunk of the data,
                     and the additional arguments.

    Raises:
        ValueError: If `num_p` is not positive or if no data splits are created.

    Examples:
        >>> data = [1, 2, 3, 4, 5, 6]
        >>> num_p = 2
        >>> args = ('arg1', 'arg2')
        >>> job_args = dispatch_data(num_p, iter(data), args)
        >>> for job in job_args:
        ...     print(job)
        (0, [1, 2, 3], 'arg1', 'arg2')
        (1, [4, 5, 6], 'arg1', 'arg2')

        >>> num_p = 3
        >>> job_args = dispatch_data(num_p, iter(data), args)
        >>> for job in job_args:
        ...     print(job)
        (0, [1, 2], 'arg1', 'arg2')
        (1, [3, 4], 'arg1', 'arg2')
        (2, [5, 6], 'arg1', 'arg2')
    """
    _check_num_p(num_p)

    tic("Splitting task", verbose=verbose)
    splits = split_iter(
        it=data_iter,
        num_splits=num_p,
        use_tqdm=verbose
    )
    toc(verbose=verbose)

    num_p = len(splits)
    if num_p == 0:
        raise ValueError(f"The number of data splits is zero. "
                         f"Possibly no data was read from the provided iterator.")
    else:
        job_args = [None] * num_p
        for pidx in range(num_p):
            if verbose:
                hprint_message(
                    'pid', pidx,
                    'workload', len(splits[pidx])
                )
            job_args[pidx] = (pidx, splits[pidx], *args)
        return job_args


def start_jobs(jobs: Union[List, Tuple], interval: float = 0.01):
    """
    Starts a list of jobs (processes) with an optional interval between each start.

    Args:
        jobs (Union[List, Tuple]): A list or tuple of jobs (processes) to be started.
        interval (float): The interval in seconds to wait between starting each job. Defaults to 0.01 seconds.

    Examples:
        >>> import multiprocessing
        >>> def example_job(n):
        ...     print(f"Job {n} started")
        >>> jobs = [multiprocessing.Process(target=example_job, args=(i,)) for i in range(3)]
        >>> start_jobs(jobs)
        Job 0 started
        Job 1 started
        Job 2 started
    """
    for p in jobs:
        p.start()
        if interval != 0:
            sleep(interval)


def start_and_wait_jobs(jobs: [Union[List, Tuple]], interval: float = 0.01):
    """
    Starts a list of jobs (processes) with an optional interval between each start and waits for them to complete.

    Args:
        jobs (Union[List, Tuple]): A list or tuple of jobs (processes) to be started and waited on.
        interval (float): The interval in seconds to wait between starting each job. Defaults to 0.01 seconds.

    Examples:
        >>> import multiprocessing
        >>> def example_job(n):
        ...     print(f"Job {n} started")
        >>> jobs = [multiprocessing.Process(target=example_job, args=(i,)) for i in range(3)]
        >>> start_and_wait_jobs(jobs)
        Job 0 started
        Job 1 started
        Job 2 started
    """
    start_jobs(jobs, interval=interval)
    for p in jobs:
        p.join()


def _merge_list(results):
    return sum(results, [])

def _sum(results):
    return sum(results)

def get_merger(merge_method):
    if merge_method == 'list':
        return _merge_list
    elif merge_method == 'dict':
        return merge_mappings
    elif merge_method == 'list_dict':
        return merge_list_valued_mappings
    elif merge_method == 'set_dict':
        return merge_set_valued_mappings
    elif merge_method == 'counter_dict':
        return merge_counter_valued_mappings
    elif merge_method == 'sum':
        return _sum
    raise ValueError(
        f"The provided results does not support the default merge method {merge_method}."
    )

def merge_results(result_collection, mergers: Union[List, Tuple] = None, _in_place: bool = True):
    """
    Merges a collection of results using specified merge methods or default merge logic.

    Args:
        result_collection (Iterable): A collection of results to be merged.
        mergers (Union[List, Tuple], optional): A list or tuple of merge methods. Each merge method can be a callable
            or a string specifying a default merge method. Defaults to None.

            Pre-Defined Merge Methods:
            - 'list': Merges lists by concatenating them.
            - 'dict': Merges dictionaries by updating them. Keys from later dictionaries overwrite earlier ones.
            - 'list_dict': Merges dictionaries with list values by extending the lists.
            - 'set_dict': Merges dictionaries with set values by updating the sets.
            - 'counter_dict': Merges dictionaries with Counter values by updating the Counters.
            - 'sum': Sums numeric results.

    Returns:
        Tuple: A tuple of merged results.

    Examples:
        >>> from collections import Counter, defaultdict
        >>> result_collection = [
        ...     [[1, 2], [3, 4]],
        ...     [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}],
        ...     [Counter(a=1, b=2), Counter(a=3, b=4)]
        ... ]
        >>> merge_results(result_collection)
        ([1, 2, 3, 4], {'a': 4, 'b': 6}, Counter({'b': 6, 'a': 4}))

        >>> result_collection = [
        ...     [[1, 2], [3, 4]],
        ...     [{'a': [1, 2]}, {'a': [3, 4]}],
        ...     [defaultdict(set, a={1, 2}), defaultdict(set, a={3, 4})]
        ... ]
        >>> merge_results(result_collection)
        ([1, 2, 3, 4], defaultdict(<class 'list'>, {'a': [1, 2, 3, 4]}), defaultdict(<class 'set'>, {'a': {1, 2, 3, 4}}))

        >>> result_collection = [
        ...     [[1, 2], [3, 4]],
        ...     [{'a': [1, 2]}, {'a': [3, 4]}],
        ...     [defaultdict(set, a={1, 2}), defaultdict(set, a={3, 4})]
        ... ]
        >>> merge_results(result_collection, mergers=['list', 'list_dict', 'set_dict'])
        ([1, 2, 3, 4], defaultdict(<class 'list'>, {'a': [1, 2, 3, 4]}), defaultdict(<class 'set'>, {'a': {1, 2, 3, 4}}))
    """

    def _default_merger_1(results, merge_method: str):
        if merge_method == 'list':
            return sum(results, [])
        elif merge_method == 'dict':
            return merge_mappings(results, in_place=_in_place)
        elif merge_method == 'list_dict':
            return merge_list_valued_mappings(results, in_place=_in_place)
        elif merge_method == 'set_dict':
            return merge_set_valued_mappings(results, in_place=_in_place)
        elif merge_method == 'counter_dict':
            return merge_counter_valued_mappings(results, in_place=_in_place)
        elif merge_method == 'sum':
            return sum(results)
        raise ValueError(
            f"The provided results does not support the default merge method {merge_method}."
        )

    def _default_merger_2(results):
        size_results = len(results)
        if size_results == 0:
            return results
        err = None

        first_result = results[0]
        if isinstance(first_result, (int, float, bool)):
            return sum(results)
        elif isinstance(first_result, List):
            return sum(results, [])
        elif isinstance(first_result, Tuple):
            return sum(results, ())
        elif isinstance(first_result, Counter):
            return merge_counter_valued_mappings(results, in_place=_in_place)
        elif isinstance(first_result, Mapping):
            peek_value = None
            for i in range(size_results):
                if len(results[i]) != 0:
                    peek_value = next(iter(results[i].values()))
                    break
            if isinstance(peek_value, List):
                return merge_list_valued_mappings(results[i:], in_place=_in_place)
            elif isinstance(peek_value, Set):
                return merge_set_valued_mappings(results[i:], in_place=_in_place)
            elif isinstance(peek_value, Counter):
                return merge_counter_valued_mappings(results[i:], in_place=_in_place)
            else:
                try:
                    return sum_dicts(results[i:], in_place=_in_place)
                except Exception as err:
                    pass
        raise ValueError(
            f"The provided results does not support the default merge. "
            f"Error: {err or f'type {type(first_result)} not supported'}."
        )

    return (
        tuple(
            (
                merger(results)
                if callable(merger)
                else _default_merger_1(results, merger)
            )
            for results, merger in zip(result_collection, mergers)
        )
        if mergers
        else tuple(_default_merger_2(results) for results in tqdm(result_collection))
    )
