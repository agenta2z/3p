import multiprocessing
import warnings
from itertools import islice
from multiprocessing import get_context
from multiprocessing.context import BaseContext
from os import path
from typing import Union, Iterator, Iterable, List, Callable, Tuple, Any, Sequence

from tqdm import tqdm

from python_utils.common_utils import split_list
from python_utils.console_utils import hprint_message
from python_utils.io_utils.pickle_io import pickle_load

from python_utils.mp_utils.common import dispatch_data, start_and_wait_jobs, get_suggested_num_workers, merge_results
from python_utils.mp_utils.mp_target import MPTarget


def parallel_process(
        num_p,
        data_iter: Union[Iterator, Iterable, List],
        target: Callable, args: Tuple,
        ctx: BaseContext = None,
        verbose=__debug__
):
    if isinstance(target, MPTarget):
        target.use_queue = False
    if ctx is None:
        ctx = get_context('spawn')
    job_args = dispatch_data(
        num_p=num_p,
        data_iter=data_iter,
        args=args,
        verbose=verbose
    )
    jobs = [None] * num_p
    for i in range(num_p):
        jobs[i] = ctx.Process(target=target, args=job_args[i])
    start_and_wait_jobs(jobs)


def parallel_process_by_pool(
        num_p: int,
        data_iter: Union[Iterator, Iterable],
        target: Union[List[Union[MPTarget, Callable]], Union[MPTarget, Callable]],
        target_weights: List[Union[int, float]] = None,
        args: Tuple = (),
        verbose: bool = __debug__,
        merge_output: bool = False,
        mergers: Union[List, Tuple] = None,
        vertical_merge: bool = True,
        debug: bool = False,
        return_job_splits: bool = False,
        load_dumped_results: bool = False,
        result_dump_load_method: Callable[[str], Any] = pickle_load,
        wait_for_pool_close: bool = True,
        start_method: str = None,
        multiprocessing_module=multiprocessing,
        pool_object=None,
):
    """
    Parallelizes a given function or callable using a multiprocessing pool.

    Args:
        num_p (int): The number of processes to initiate.
        data_iter (Union[Iterator, Iterable]): An iterable providing the data source for the multi-processing.
        target (Union[Callable, List[Callable]]): The function or callable(s) to be parallelized.
        target_weights (List[Union[int, float]], optional): Weights for distributing job arguments among multiple targets.
        args (Tuple): Additional arguments to be passed to the target function. Defaults to ().
        verbose (bool): If True, prints progress and debug information.
        merge_output (bool): If True, merges the output from all processes.
        mergers (Union[List, Tuple], optional): Custom merge functions for merging the results.
        vertical_merge (bool): If True, merges results vertically.
        debug (bool): If True or 1, runs in debug mode (no parallelism). If set to an integer > 1, runs a limited number of iterations.
        return_job_splits (bool): If True, returns the job splits along with the results.
        load_dumped_results (bool): If True, loads results from dumped files.
        result_dump_load_method (Callable[[str], Any], optional): Method to load dumped results.
        wait_for_pool_close (bool): If True, waits for the pool to close before returning results. Defaults to True.
        start_method (str, optional): Specifies the start method for the multiprocessing module. Typical values include 'fork', 'spawn'.
        multiprocessing_module (module): The multiprocessing module to use. Defaults to the built-in multiprocessing module.
        pool_object (object, optional): The pool object to use for multiprocessing. Defaults to the Pool object of `multiprocessing_module`.

    Returns:
        Union[Any, Tuple[Any, Iterator]]: The results of the parallel processing, or a tuple containing the results and job splits if `return_job_splits` is True.

    Raises:
        ValueError: If `debug` is set to True or 1 and `merge_output` is True.

    Examples:
        >>> def example_target(pid, data, *args):
        ...     return [d * 2 for d in data]
        >>> data = [1, 2, 3, 4, 5]
        >>> result = parallel_process_by_pool(2, data, example_target)
        >>> print(result)
        [[2, 4, 6], [8, 10]]
    """
    if debug == 1 and merge_output:
        raise ValueError('debug is set True or 1, '
                         'in this case the result merge will not work; '
                         'change debug to an integer higher than 2')

    if num_p is None or num_p <= 0:
        num_p = get_suggested_num_workers(num_p)

    if not isinstance(target, Sequence):
        target = [target]

    for _target in target:
        if isinstance(_target, MPTarget):
            _target.use_queue = False

    if num_p == 1:
        rst = target[0](0, data_iter, *args)
        if load_dumped_results:
            if isinstance(rst, str) and path.isfile(rst):
                rst = result_dump_load_method(rst)
            else:
                warnings.warn(f'Expected to load results from dumped files; '
                              f'in this case the returned result from each process '
                              f'must be a file path; '
                              f'got {type(rst)}')
        return rst

    if multiprocessing_module is None:
        multiprocessing_module = multiprocessing

    curr_start_method = multiprocessing_module.get_start_method(allow_none=True)
    if start_method is not None and start_method != curr_start_method:
        if start_method == 'spawn':
            multiprocessing_module.freeze_support()
        multiprocessing_module.set_start_method(start_method, force=True)
    elif curr_start_method == 'spawn':
        multiprocessing_module.freeze_support()

    if pool_object is None:
        pool_object = multiprocessing_module.Pool

    if isinstance(debug, int) and debug > 1:
        num_p = debug
        data_iter = islice(data_iter, 1000)

    job_args = dispatch_data(
        num_p=num_p,
        data_iter=data_iter,
        args=args,
        verbose=verbose
    )

    if debug is True or debug == 1:
        rst = target[0](*job_args[0])
    else:
        pool = pool_object(processes=num_p)
        try:
            if len(target) == 1:
                rst = pool.starmap(target[0], job_args)
            else:
                job_args_splits = split_list(job_args, target_weights or len(target))
                hprint_message(
                    'num_jobs', len(job_args),
                    'num_targets', len(target),
                    'num_jobj_splits', len(job_args_splits)
                )

                len_job_args_splits = len(job_args_splits)
                len_target = len(target)

                if len_job_args_splits < len_target:
                    target = target[:len(job_args_splits)]
                elif len_job_args_splits > len_target:
                    raise ValueError(f"Number of job splits must be less than or equal to the number of targets; got {job_args_splits} job splits but {target} targets")

                async_results = []
                for _target, _job_args in zip(target, job_args_splits):
                    async_results.append(pool.starmap_async(_target, _job_args))

                rst = []
                for async_result in async_results:
                    rst.extend(async_result.get())
        except Exception as err:
            pool.close()
            if wait_for_pool_close:
                warnings.warn(f"waiting for multi-process pool of size {num_p} to close "
                              f"due to error '{err}'")
                pool.join()
            raise err
        finally:
            pool.close()
            if wait_for_pool_close:
                hprint_message(f"waiting for multi-process pool of size {num_p} to close")
                pool.join()

    if load_dumped_results:
        if isinstance(rst[0], str) and path.isfile(rst[0]):
            rst = [
                result_dump_load_method(file_path)
                for file_path in tqdm(rst, desc='loading dumped files')
            ]
        else:
            warnings.warn(f'Expected to load results from dumped files; '
                          f'in this case the returned result from each process must be a file path; '
                          f'got {type(rst[0])}')

    if merge_output:
        rst = list(zip(*rst)) if vertical_merge else [rst]

        hprint_message(
            'mergers', mergers,
            'result types', [type(x) for x in rst],
            'result size', [(len(x) if hasattr(x, '__len__') else 'n/a') for x in rst]
        )
        rst = merge_results(result_collection=rst, mergers=mergers)
        if not vertical_merge:
            rst = rst[0]

    return (rst, (job_arg[1] for job_arg in job_args)) if return_job_splits else rst
