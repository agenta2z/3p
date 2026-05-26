import uuid
from multiprocessing import Queue
from os import path
from time import sleep
from typing import Union, Callable, Any, Iterator, Sequence, List

from attr import attrs, attrib
from tqdm import tqdm

from python_utils.console_utils import hprint_message
from python_utils.io_utils.pickle_io import pickle_save
from python_utils.io_utils.text_io import iter_all_lines_from_all_files
from python_utils.path_utils.common import ensure_dir_existence
from python_utils.path_utils.path_string_operations import append_timestamp


class MPResultTuple(tuple):
    # Use a dummy data type `MPResultTuple` (just a tuple) to indicate
    # a multi-processing output contains results from multiple data items.
    pass


@attrs(slots=True)
class MPActiveQueueFlag:
    """
    Represents a flag indicating the active status of a queue used in multi-processing operations.

    Attributes:
        flag (Union[int, bool]): The flag value indicating the active status of the queue.
            - If set to 0 or False, it indicates that the queue is no longer active and processing should stop.
            - If set to any other value (non-zero or True), it indicates that the queue is still active and processing should continue.
    """
    flag = attrib(type=Union[int, bool])


@attrs(slots=True)
class MPTarget:
    """
    Encapsulates a multi-processing target callable, providing rich configuration
    for multi-processing operations.

    Attributes:
        target (Callable): The callable to be executed in the multi-processing environment.
        name (str): A descriptive name for this multi-processing target, used in progress bars and error messages.
        pass_pid_to_target (bool): If True, the process ID will be passed to the target function.
        pass_each_data_item_to_target (bool): If True, each item from the input is passed individually to the `target` function,
            rather than as a list of items.
        result_dump_path (str): Path to save the output of the multi-processing target.
        result_dump_file_pattern (str): File pattern for the saved output files. If not provided,
            a UUID will be used as the file name.
        result_dump_method (Callable): Custom function to save the output. Default is to use pickle.
        use_queue (bool): If True, indicates that the input and output will use queues.
            The input queue contains task assignments, each process retrieves a task from the input queue,
            processes it, and places the result in the output queue.
            When using queue, the first argument in `args` must be the output queue,
            and the second argument in `args` must be a flag indicating if the queue is still active (see `__call__` method).
        queue_refill_wait_time (float): Time in seconds to wait before processing the next batch of items from the queue when `use_queue` is True.
            When the queue is empty, it means all existing items in the queue have been processed, but new items might still arrive after some time.
            This is the amount of time in seconds to wait for new items.
        data_item_iter (Union[bool, Callable[[Any], Iterator]]): If True, or provided with a custom iterator,
            reads data items from the input and passes them to the `target` callable.
            By default (when this parameter is simply set True), assumes input are file paths of text files,
            treating each line as a data item.
        unpack_single_result (bool): If True, unpacks the result from its container if only a single item is processed.
        remove_none_from_output (bool): If True, removes None values from the output.
        return_output (bool): If True, always returns the output of the target function; otherwise, returns the path to the saved output.
        common_func (bool): Convenience parameter; if True, sets `pass_pid_to_target` to False, `pass_each_data_item_to_target` to True,
            and `unpack_single_result` to True.
        is_target_iter (bool): If True, indicates that the target callable returns an iterator.

    """

    _target = attrib(type=Callable)
    name = attrib(type=str, default=None)
    pass_pid_to_target = attrib(type=bool, default=True)
    pass_each_data_item_to_target = attrib(type=bool, default=True)
    result_dump_path = attrib(type=str, default=None)
    result_dump_file_pattern = attrib(type=str, default=None)
    result_dump_method = attrib(type=Callable, default=pickle_save)
    use_queue = attrib(type=bool, default=False)
    queue_refill_wait_time = attrib(type=float, default=0.5)
    data_item_iter = attrib(type=Union[bool, Callable[[Any], Iterator]], default=False)
    unpack_single_result = attrib(type=bool, default=False)
    remove_none_from_output = attrib(type=bool, default=False)
    return_output = attrib(type=bool, default=False)
    common_func = attrib(type=bool, default=False)
    is_target_iter = attrib(type=bool, default=False)

    def __attrs_post_init__(self):
        self._validate_parameters()
        if self.result_dump_path:
            ensure_dir_existence(self.result_dump_path)
        if self.common_func:
            self.pass_pid_to_target = False
            self.pass_each_data_item_to_target = True
            self.unpack_single_result = True

    def _validate_parameters(self):
        if self.result_dump_path and self.use_queue:
            raise ValueError("Cannot use queue when 'result_dump_path' is set.")

    def target(self, pid, data, *args):
        if self._target is not None:
            if self.pass_pid_to_target:
                rst = self._target(pid, data, *args)
            else:
                rst = self._target(data, *args)
            return list(rst) if self.is_target_iter else rst
        else:
            raise NotImplementedError

    def _get_name(self):
        return self.name or str(self._target)

    def _has_data_iter(self):
        return (
                self.data_item_iter is not None and
                self.data_item_iter is not False
        )

    def _process_input_data(self, data):
        return (
            iter_all_lines_from_all_files(input_paths=data, use_tqdm=True)
            if self.data_item_iter is True
            else tqdm(self.data_item_iter(data))
        )

    def _process_result_no_unpack(self, result):
        return MPResultTuple(
            (x for x in result if x is not None)
            if self.remove_none_from_output
            else result
        )

    def _process_result(self, result):
        return result[0] if (
                self.unpack_single_result and
                (
                        isinstance(result, Sequence) or
                        (
                                hasattr(result, '__len__') and
                                hasattr(result, '__getitem__')
                        )
                ) and len(result) == 1
        ) else self._process_result_no_unpack(result)

    @staticmethod
    def _check_active_queue_flag(queue_completion_flag) -> bool:
        # use False to indicate queue completes
        if not queue_completion_flag:
            return False
        if isinstance(queue_completion_flag, List):
            return bool(queue_completion_flag[0])
        if isinstance(queue_completion_flag, MPActiveQueueFlag):
            return bool(queue_completion_flag.flag)

        return True

    def __call__(self, pid, data, *args):
        """
        Executes the target callable with the provided data and arguments in a multi-processing environment.

        Args:
            pid (int): The process ID.
            data (Any): The input data for the target callable. If `use_queue` is True, this is expected to be an input queue.
            args (Any): Additional arguments for the target callable. If `use_queue` is True, the first argument must be the output queue,
                        and the second argument must be a flag indicating if the queue is still active.

        Returns:
            Any: The output of the target callable or the path to the saved output, depending on the configuration.
        """
        self._validate_parameters()

        hprint_message(
            'initialized',
            f'{self.name}{pid}'
        )
        no_job_cnt = 0
        if self.pass_each_data_item_to_target:
            # If `pass_each_data_item_to_target` is True,
            # it indicates `data` should not be processed by the target callable as a whole,
            # instead each item in the `data` will be passed to the target callable
            if self.use_queue:
                input_queue: Queue = data
                output_queue: Queue = args[0]
                queue_completion_flag = args[1]
                while True:
                    #  Keeps taking assignment from the queue until the queue is labeled non-active
                    while not input_queue.empty():
                        data = input_queue.get()
                        if self._has_data_iter():
                            output_queue.put(
                                self._process_result_no_unpack((
                                    self.target(pid, dataitem, *args[2:])
                                    for dataitem in self._process_input_data(data)
                                ))
                            )
                        else:
                            output_queue.put(self._process_result(tuple(
                                self.target(pid, dataitem, *args[2:]) for dataitem in data
                            )))

                    if not self._check_active_queue_flag(queue_completion_flag):
                        return

                    no_job_cnt += 1
                    if no_job_cnt % 10 == 0:
                        hprint_message(
                            'job', f'{self._get_name()}: {pid}',
                            'wait for', self.queue_refill_wait_time
                        )
                    sleep(self.queue_refill_wait_time)
            else:
                # Process input data and output results without queue
                if self._has_data_iter():
                    output = self._process_result_no_unpack((
                        self.target(pid, dataitem, *args)
                        for dataitem in self._process_input_data(data)
                    ))
                else:
                    data = tqdm(data, desc=f'{self._get_name()}: {pid}')
                    output = self._process_result(tuple(
                        (self.target(pid, dataitem, *args) for dataitem in data)
                    ))
        else:
            # If `pass_each_data_item_to_target` is False,
            # then `data` is processed by the target callable as a whole.
            if self.use_queue:
                #  Keeps taking assignment from the queue until the queue is labeled non-active
                input_queue: Queue = data
                output_queue: Queue = args[0]
                queue_completion_flag = args[1]
                while True:
                    while not input_queue.empty():
                        data = input_queue.get()
                        if self._has_data_iter():
                            data = self._process_input_data(data)
                        result = self.target(pid, data, *args[2:])
                        output_queue.put(self._process_result(result))

                    if not self._check_active_queue_flag(queue_completion_flag):
                        return

                    no_job_cnt += 1
                    if no_job_cnt % 10 == 0:
                        hprint_message(
                            'job', f'{self._get_name()}: {pid}',
                            'wait for', self.queue_refill_wait_time
                        )
                    sleep(self.queue_refill_wait_time)
            else:
                # Process input data and output results without queue
                if self._has_data_iter():
                    data = self._process_input_data(data)
                output = self._process_result(self.target(pid, data, *args))

        if self.result_dump_path:
            # Dump results if result_dump_path is specified
            dump_path = path.join(
                self.result_dump_path,
                (
                    f'{pid:05}-{append_timestamp(str(uuid.uuid4()))}.mpb'
                    if self.result_dump_file_pattern is None
                    else self.result_dump_file_pattern.format(pid))
            )

            hprint_message('dumping results to', dump_path)
            self.result_dump_method(output, dump_path)
            if self.return_output:
                return output
            else:
                del output
                return dump_path
        else:
            return output
