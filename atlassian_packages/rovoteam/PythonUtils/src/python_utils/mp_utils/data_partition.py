from collections import defaultdict
from typing import Union, Callable, Iterable, List

from python_utils.common_utils import get_


def partition_data(
        data_iters: List[Iterable],
        max_partition_size: int,
        data_key:Union[str, Callable] = None,
        partition_group_key: Union[str, Callable] = None,
        force_same_partition_key: Union[str, Callable] = None,
        save_data_partition: Callable = None,
        updated_data_output_paths: List[str] = None,
        output_path: str = None
):
    partition_groups = defaultdict(list)
    for data_iter in data_iters:

        for dp in data_iter:


            _partition_group_key = get_(dp, partition_group_key)
            partition_group = partition_groups[_partition_group_key]



            if not partition_group or len(partition_group[-1]) > max_partition_size:
                partition_group.append([])

            current_partition: list = partition_group[-1]
            current_partition.append(dp)
