from collections import defaultdict
from copy import copy
from functools import partial
from itertools import chain
from statistics import mean
from typing import Mapping, Iterable, Tuple, Sequence, Set
from typing import Union, Callable, List, Dict, Any

import numpy as np
import pandas as pd
from attr import attrib, attrs

from python_utils.common_utils import all_str, binary_min, binary_max
from python_utils.common_utils.iter_helper import concat, len_, zip__, product__, iter_, first
from python_utils.common_utils.map_helper import MAPPING_KEY_OR_CONVERSION, convert_map, explode_map_as_tuples, merge_list_valued_mappings, merge_mappings, get_


def agg_values_(*values, agg_method=mean, non_atom_types=(List, Tuple, Set)):
    """
     Aggregates values using a specified aggregation method. If the input is a single mapping,
     it recursively applies the aggregation method to the values. If the input is a collection
     of iterables, it applies the aggregation method to each iterable.

     Args:
         *values: Variable length argument list of values to be aggregated.
         agg_method (Callable, optional): The method to use for aggregation. Defaults to mean.
         non_atom_types (tuple, optional): A tuple of types that are considered non-atomic (iterables). Defaults to (List, Tuple, Set).

     Returns:
         The aggregated value, or a mapping with aggregated values for each key if the input is a mapping.

     Examples:
         >>> agg_values_([3, 5])
         4
         >>> agg_values_({'a': {'x': [1, 2], 'y': [3, 4]}, 'b': [5, 6]})
         {'a': {'x': 1.5, 'y': 3.5}, 'b': 5.5}
         >>> agg_values_({'a': [1, 2, 3], 'b': [4, 5, 6]}, agg_method=max)
         {'a': 3, 'b': 6}
         >>> agg_values_({'a': [[1, 2, 3], [4, 5, 6]], 'b': [4, 5, 6]}, agg_method=concat)
         {'a': [1, 2, 3, 4, 5, 6], 'b': [4, 5, 6]}
         >>> agg_values_(
         ...     {'a': [1, 2], 'b': [3]},
         ...     {'a': [3, 4], 'b': [4, 5], 'c': [6]},
         ...     {'a': [5], 'c': [7, 8]}
         ... )
         {'a': 3, 'b': 4, 'c': 7}
         >>> agg_values_(
         ...     {'a': [1, 2, 3], 'b': [4]},
         ...     {'a': [4, 5], 'b': [5, 6], 'c': [6, 7]},
         ...     {'a': [6], 'c': [8, 9]},
         ...     agg_method=sum
         ... )
         {'a': 21, 'b': 15, 'c': 30}
         >>> agg_values_(
         ...     {'a': [1, 2], 'b': [3]},
         ...     {'a': [3, 4], 'b': [4, 5], 'c': [6]},
         ...     {'a': [5], 'c': [7, 8]},
         ...     agg_method=max
         ... )
         {'a': 5, 'b': 5, 'c': 8}
         >>> agg_values_(
         ...     {'a': [[1, 2], [3, 4]], 'b': [5]},
         ...     {'a': [[5, 6]], 'b': [6, 7]},
         ...     {'a': [[7, 8]], 'c': [8, 9]},
         ...     agg_method=concat
         ... )
         {'a': [1, 2, 3, 4, 5, 6, 7, 8], 'b': [5, 6, 7], 'c': [8, 9]}
     """
    if len(values) == 1:
        values = values[0]

    if isinstance(values, Sequence):
        if not values:
            return []
        elif isinstance(values[0], Mapping):
            values: Mapping = merge_list_valued_mappings(values, non_atom_types=non_atom_types)

    if isinstance(values, Mapping):
        return {
            k: (
                agg_values_(v, agg_method=agg_method, non_atom_types=non_atom_types)
                if isinstance(v, Mapping) or (non_atom_types and isinstance(v, non_atom_types))
                else v
            )
            for k, v in values.items()
        }
    else:
        if non_atom_types and isinstance(values, non_atom_types):
            return agg_method(values)
        else:
            return values


mean_ = agg_values_
count_ = partial(agg_values_, agg_method=len_)
sum_ = partial(agg_values_, agg_method=sum)
max_ = partial(agg_values_, agg_method=max)
min_ = partial(agg_values_, agg_method=min)
bmax_ = partial(agg_values_, agg_method=binary_min)
bmin_ = partial(agg_values_, agg_method=binary_max)
concat_ = partial(agg_values_, agg_method=concat)

PREDEFINED_AGG_METHODS = {
    'size': len,
    'count': count_,
    'sum': sum_,
    'mean': mean_,
    'min': min_,
    'max': max_,
    'first': first,
    'bmin': bmin_,
    'bmax': bmax_,
    'concat': concat_,
    'group': list
}

PREDEFINED_EXPLOSION_METHODS = {
    'zip': zip__,
    'product': product__
}


@attrs(slots=True)
class Aggregation:
    target: MAPPING_KEY_OR_CONVERSION = attrib()
    agg: MAPPING_KEY_OR_CONVERSION = attrib(default='mean')
    groupby: MAPPING_KEY_OR_CONVERSION = attrib(default=None)
    explode_group: Union[bool, str, Callable[..., Tuple]] = attrib(default='product')


def aggregate(
        df: Iterable[Mapping],
        aggregations: Sequence[Aggregation],
        agg_aliases: Mapping[str, Callable] = PREDEFINED_AGG_METHODS,
        explosion_alias: Mapping[str, Callable] = PREDEFINED_EXPLOSION_METHODS,
        always_add_agg_alias_to_agg_results: bool = False,
        unpack_single_aggregation_result: bool = True
) -> Union[List[Mapping], List[List[Mapping]]]:
    """
    Performs aggregation operations on a dataset based on specified aggregation rules.

    This function takes an iterable of dictionaries (e.g., rows from a dataset) and applies
    specified aggregation operations, such as summing or counting values, potentially grouped
    by one or more fields. The function supports multiple aggregation methods, customizable
    aggregation aliases, and the option to explode or transform grouped data.

    Args:
        df (Iterable[Mapping]): The input dataset as an iterable of dictionaries, where each
            dictionary represents a record.
        aggregations (Sequence[Aggregation]): A sequence of `Aggregation` objects that define
            the aggregation operations to be applied to the dataset.
        agg_aliases (Mapping[str, Callable], optional): A mapping from aggregation function
            names to callable functions. Defaults to `PREDEFINED_AGG_METHODS`.
        explosion_alias (Mapping[str, Callable], optional): A mapping from explosion function
            names to callable functions. Defaults to `PREDEFINED_EXPLOSION_METHODS`.
        always_add_agg_alias_to_agg_results (bool, optional): If True, appends the aggregation
            alias to the keys in the aggregation results. Defaults to False.
        unpack_single_aggregation_result (bool, optional): If True and only one aggregation is
            performed, returns a single list of dictionaries. If False, returns a list of lists
            of dictionaries. Defaults to True.

    Returns:
        Union[List[Mapping], List[List[Mapping]]]: The result of the aggregation. If only one
        aggregation is performed and `unpack_single_aggregation_result` is True, returns a list
        of dictionaries. Otherwise, returns a list of lists of dictionaries, where each sublist
        corresponds to the results of one aggregation.

    Examples:
        >>> df = [
        ...     {'category': 'A', 'value': 10},
        ...     {'category': 'B', 'value': 20},
        ...     {'category': 'A', 'value': 30},
        ...     {'category': 'B', 'value': 40},
        ...     {'category': 'C', 'value': 50}
        ... ]
        >>> aggregations = [
        ...     Aggregation(target='value', agg='sum', groupby='category')
        ... ]
        >>> aggregate(df, aggregations)
        [{'category': 'A', 'value': 40}, {'category': 'B', 'value': 60}, {'category': 'C', 'value': 50}]

        >>> aggregations = [
        ...     Aggregation(target='value', agg='sum'),
        ...     Aggregation(target='value', agg='count', groupby='category')
        ... ]
        >>> aggregate(df, aggregations)
        [[{'value': 150}], [{'category': 'A', 'value': 2}, {'category': 'B', 'value': 2}, {'category': 'C', 'value': 1}]]

        >>> df = [
        ...     {'category': 'A', 'value': 10, 'type': 'X'},
        ...     {'category': 'B', 'value': 20, 'type': 'Y'},
        ...     {'category': 'A', 'value': 30, 'type': 'X'},
        ...     {'category': 'B', 'value': 40, 'type': 'Y'},
        ...     {'category': 'C', 'value': 50, 'type': 'Z'}
        ... ]
        >>> aggregations = [
        ...     Aggregation(target='value', agg='sum', groupby=['category', 'type']),
        ...     Aggregation(target='value', agg='max', groupby='category')
        ... ]
        >>> aggregate(df, aggregations)
        [[{'category': 'A', 'type': 'X', 'value': 40}, {'category': 'B', 'type': 'Y', 'value': 60}, {'category': 'C', 'type': 'Z', 'value': 50}], [{'category': 'A', 'value': 30}, {'category': 'B', 'value': 40}, {'category': 'C', 'value': 50}]]

        >>> df = [
        ...     {'group': 'G1', 'value1': 10, 'value2': 1},
        ...     {'group': 'G2', 'value1': 20, 'value2': 2},
        ...     {'group': 'G1', 'value1': 30, 'value2': 3},
        ...     {'group': 'G2', 'value1': 40, 'value2': 4},
        ...     {'group': 'G3', 'value1': 50, 'value2': 5}
        ... ]
        >>> aggregations = [
        ...     Aggregation(target=['value1', 'value2'], agg='sum', groupby='group')
        ... ]
        >>> aggregate(df, aggregations)
        [{'group': 'G1', 'value1': 40, 'value2': 4}, {'group': 'G2', 'value1': 60, 'value2': 6}, {'group': 'G3', 'value1': 50, 'value2': 5}]

        >>> df = [
        ...     {'id': 1, 'scores': [1, 2, 3]},
        ...     {'id': 2, 'scores': [4, 5]},
        ...     {'id': 3, 'scores': [6, 7, 8, 9]}
        ... ]
        >>> aggregations = [
        ...     Aggregation(target='scores', agg='concat', groupby='id')
        ... ]
        >>> aggregate(df, aggregations)
        [{'id': 1, 'scores': [1, 2, 3]}, {'id': 2, 'scores': [4, 5]}, {'id': 3, 'scores': [6, 7, 8, 9]}]
        >>> aggregations = [
        ...     Aggregation(target='scores', agg=['concat', 'size'], groupby='id')
        ... ]
        >>> aggregate(df, aggregations)
        [{'id': 1, 'scores': [1, 2, 3], 'size': 1}, {'id': 2, 'scores': [4, 5], 'size': 1}, {'id': 3, 'scores': [6, 7, 8, 9], 'size': 1}]
        >>> aggregations = [
        ...     Aggregation(target=['_index', 'scores'], agg='concat', groupby='id')
        ... ]
        >>> aggregate(df, aggregations)
        [{'id': 1, '_index': [0], 'scores': [1, 2, 3]}, {'id': 2, '_index': [1], 'scores': [4, 5]}, {'id': 3, '_index': [2], 'scores': [6, 7, 8, 9]}]

        >>> df = [
        ...     {'id': 1, 'nested': {'a': 1, 'b': 2}},
        ...     {'id': 1, 'nested': {'a': 3, 'b': 4}},
        ...     {'id': 3, 'nested': {'a': 5, 'b': 6}}
        ... ]
        >>> aggregations = [
        ...     Aggregation(target='nested', agg='sum', groupby='id')
        ... ]
        >>> aggregate(df, aggregations)
        [{'id': 1, 'nested': {'a': 4, 'b': 6}}, {'id': 3, 'nested': {'a': 5, 'b': 6}}]
        >>> aggregations = [
        ...     Aggregation(target='nested', agg=['sum', 'size'], groupby='id')
        ... ]
        >>> aggregate(df, aggregations)
        [{'id': 1, 'nested': {'a': 4, 'b': 6}, 'size': 2}, {'id': 3, 'nested': {'a': 5, 'b': 6}, 'size': 1}]
        >>> aggregations = [
        ...     Aggregation(target='nested', agg=['sum', 'size'], groupby='id'),
        ...     Aggregation(target='_index', agg=['concat'], groupby='id')
        ... ]
        >>> aggregate(df, aggregations)
        [[{'id': 1, 'nested': {'a': 4, 'b': 6}, 'size': 2}, {'id': 3, 'nested': {'a': 5, 'b': 6}, 'size': 1}], [{'id': 1, '_index': [0, 1]}, {'id': 3, '_index': [2]}]]

        >>> df = [
        ...     {'dialog_id': 1, 'metric.recall': 0.8, 'metric.precision': 0.6, 'metric.recall@1': 0.9, 'metric.precision@1': 0.7, '_data': {'some': 'data1'}},
        ...     {'dialog_id': 1, 'metric.recall': 0.85, 'metric.precision': 0.65, 'metric.recall@1': 0.92, 'metric.precision@1': 0.72, '_data': {'some': 'data2'}},
        ...     {'dialog_id': 2, 'metric.recall': 0.75, 'metric.precision': 0.55, 'metric.recall@1': 0.82, 'metric.precision@1': 0.62, '_data': {'some': 'data3'}},
        ...     {'dialog_id': 2, 'metric.recall': 0.78, 'metric.precision': 0.58, 'metric.recall@1': 0.85, 'metric.precision@1': 0.65, '_data': {'some': 'data4'}}
        ... ]
        >>> top_k = 1
        >>> aggregations = [
        ...     Aggregation(
        ...         target=[
        ...             [
        ...                 'metric.recall',
        ...                 'metric.precision',
        ...                 *(f'metric.recall@{i + 1}' for i in range(top_k)),
        ...                 *(f'metric.precision@{i + 1}' for i in range(top_k))
        ...             ],
        ...             [
        ...                 '_data'
        ...             ]
        ...         ],
        ...         agg=[[{'min_alias': 'min'}], ['group']],
        ...         groupby={'dialog_id': lambda x: x['dialog_id']}
        ...     )
        ... ]
        >>> aggregate(df, aggregations)
        [{'dialog_id': 1, 'metric.recall': 0.8, 'metric.precision': 0.6, 'metric.recall@1': 0.9, 'metric.precision@1': 0.7, 'group': [{'_data': {'some': 'data1'}}, {'_data': {'some': 'data2'}}]}, {'dialog_id': 2, 'metric.recall': 0.75, 'metric.precision': 0.55, 'metric.recall@1': 0.82, 'metric.precision@1': 0.62, 'group': [{'_data': {'some': 'data3'}}, {'_data': {'some': 'data4'}}]}]
        >>> aggregate(df, aggregations, always_add_agg_alias_to_agg_results=True)
        [{'dialog_id': 1, 'metric.recall.min_alias': 0.8, 'metric.precision.min_alias': 0.6, 'metric.recall@1.min_alias': 0.9, 'metric.precision@1.min_alias': 0.7, 'group': [{'_data': {'some': 'data1'}}, {'_data': {'some': 'data2'}}]}, {'dialog_id': 2, 'metric.recall.min_alias': 0.75, 'metric.precision.min_alias': 0.55, 'metric.recall@1.min_alias': 0.82, 'metric.precision@1.min_alias': 0.62, 'group': [{'_data': {'some': 'data3'}}, {'_data': {'some': 'data4'}}]}]

        >>> aggregations = [
        ...     Aggregation(
        ...         target=[
        ...             [
        ...                 'metric.recall',
        ...                 'metric.precision',
        ...                 *(f'metric.recall@{i + 1}' for i in range(top_k)),
        ...                 *(f'metric.precision@{i + 1}' for i in range(top_k))
        ...             ],
        ...             [
        ...                 '_data'
        ...             ]
        ...         ],
        ...         agg=[['.bmin'], ['group']],
        ...         groupby={'dialog_id': lambda x: x['dialog_id']}
        ...     )
        ... ]
        >>> aggregate(df, aggregations)
        [{'dialog_id': 1, 'metric.recall.bmin': 0, 'metric.precision.bmin': 0, 'metric.recall@1.bmin': 0, 'metric.precision@1.bmin': 0, 'group': [{'_data': {'some': 'data1'}}, {'_data': {'some': 'data2'}}]}, {'dialog_id': 2, 'metric.recall.bmin': 0, 'metric.precision.bmin': 0, 'metric.recall@1.bmin': 0, 'metric.precision@1.bmin': 0, 'group': [{'_data': {'some': 'data3'}}, {'_data': {'some': 'data4'}}]}]


    """

    # region helping functions
    def _is_single_agg(agg):
        return not (
                isinstance(agg, List)
                and any(isinstance(_agg, List) for _agg in agg)
        )

    def _resolve_agg(agg):
        if agg_aliases:
            if isinstance(agg, Mapping):
                for _agg_alias, _agg in agg.items():
                    agg_alias_in_use.append(_agg_alias)
                    if isinstance(_agg, str):
                        if _agg in agg_aliases:
                            yield agg_aliases[_agg]
                        else:
                            raise ValueError(f"'{_agg}' is not a recognized aggregation alias")
                    elif callable(_agg):
                        yield partial(agg_values_, agg_method=_agg)
                    else:
                        raise ValueError(f"'{_agg}' must be an aggregation alias or a callable")
            else:
                if isinstance(agg, str):
                    _agg = agg[1:] if agg[0] == '.' else agg
                    if _agg in agg_aliases:
                        agg_alias_in_use.append(agg)
                        yield agg_aliases[_agg]
                    else:
                        raise ValueError(f"'{agg}' is not a recognized aggregation alias")
                elif callable(agg):
                    agg_alias_in_use.append(str(agg))
                    yield partial(agg_values_, agg_method=agg)
                else:
                    raise ValueError(f"'{agg}' must be an aggregation alias or a callable")
        else:
            if isinstance(agg, Mapping):
                for _agg_alias, _agg in agg.items():
                    if isinstance(_agg, str):
                        raise ValueError(f"'{_agg}' is not a recognized aggregation alias")
                    elif callable(_agg):
                        agg_alias_in_use.append(_agg_alias)
                        yield partial(agg_values_, agg_method=_agg)
                    else:
                        raise ValueError(f"'{_agg}' must be an aggregation alias or a callable")
            else:
                if isinstance(agg, str):
                    raise ValueError(f"'{agg}' is not a recognized aggregation alias")
                elif callable(agg):
                    agg_alias_in_use.append(str(agg))
                    yield partial(agg_values_, agg_method=agg)
                else:
                    raise ValueError(f"'{agg}' must be an aggregation alias or a callable")

    def _resolve_target(target):
        if not isinstance(target, List) or all_str(target):
            return [target]
        return target

    def _resolve_explode(explode):
        if explode is not False:
            if explode is True:
                return partial(explode_map_as_tuples, explosion_method=zip__)
            elif explosion_alias and isinstance(explode, str) and explode in explosion_alias:
                return partial(explode_map_as_tuples, explosion_method=explosion_alias[explode])
            else:
                return partial(explode_map_as_tuples, explosion_method=explode)

    def _resolve_agg_result(agg_index, sub_agg_index, agg_method_index, agg_result):
        agg_alias = agg_alias_in_use_all_aggregations[agg_index][sub_agg_index][agg_method_index]

        if agg_alias[0] == '.':
            add_agg_alias_to_agg_results = True
            agg_alias = agg_alias[1:]
        else:
            add_agg_alias_to_agg_results = False
        add_agg_alias_to_agg_results = always_add_agg_alias_to_agg_results or add_agg_alias_to_agg_results

        if isinstance(agg_result, Mapping):
            if add_agg_alias_to_agg_results:
                return {
                    f'{k}.{agg_alias}': v
                    for k, v in agg_result.items()
                }
            else:
                return agg_result
        else:
            return {agg_alias: agg_result}

    # endregion

    # STEP1: resolves the `agg`, `explode` and `groupby` for each aggregation
    groups_per_aggregation = []
    agg_alias_in_use_all_aggregations = []
    len_aggregations = len(aggregations)
    processed_aggregations = [None] * len_aggregations
    for i in range(len_aggregations):
        aggregation = processed_aggregations[i] = copy(aggregations[i])
        aggregation_agg = aggregation.agg

        if _is_single_agg(aggregation_agg):
            agg_alias_in_use = []
            aggregation.agg = [list(chain(*(_resolve_agg(agg) for agg in iter_(aggregation_agg))))]
            agg_alias_in_use_all_aggregations.append([agg_alias_in_use])
        else:
            aggregation.agg = []
            agg_alias_in_use_all_aggregations.append([])
            for _aggregation_agg in aggregation_agg:
                agg_alias_in_use = []
                aggregation.agg.append(list(chain(*(_resolve_agg(agg) for agg in iter_(_aggregation_agg)))))
                agg_alias_in_use_all_aggregations[-1].append(agg_alias_in_use)

        aggregation.explode_group = _resolve_explode(aggregation.explode_group)

        if aggregation.groupby is not None:
            groups_per_aggregation.append(defaultdict(list))
        else:
            groups_per_aggregation.append([])
    # endregion

    # region STEP2: compute groups
    for _index, item in enumerate(df):
        for groups, aggregation in zip(groups_per_aggregation, processed_aggregations):
            aggregation_target = _resolve_target(aggregation.target)
            aggregation_target_values: List[Mapping] = [
                convert_map(item, target, _index=_index) for target in aggregation_target
            ]
            if aggregation.groupby is None:
                groups.append(aggregation_target_values)
            else:
                group_keys: Mapping = convert_map(item, aggregation.groupby)
                if aggregation.explode_group is not None:
                    for group_key in aggregation.explode_group(group_keys):
                        groups[group_key].append(aggregation_target_values)

                else:
                    groups[tuple(group_keys.items())].append(aggregation_target_values)

    for i, (groups, aggregation) in enumerate(zip(groups_per_aggregation, processed_aggregations)):
        if aggregation.groupby is None:
            groups_per_aggregation[i] = list(zip(*groups))
        else:
            for group_key in groups:
                groups[group_key] = list(zip(*groups[group_key]))

    # endregion

    # region STEP3: compute aggregations

    out_aggs = []
    for aggregation_index, (groups, aggregation) in enumerate(zip(groups_per_aggregation, processed_aggregations)):
        agg = []
        if isinstance(groups, Mapping):
            for group_key, group in groups.items():
                agg.append(merge_mappings(
                    (
                        dict(group_key),
                        *chain(
                            *(
                                [
                                    _resolve_agg_result(aggregation_index, sub_aggregation_index, individual_agg_method_index, agg_method(_group))
                                    for individual_agg_method_index, agg_method in enumerate(_agg)
                                ] for sub_aggregation_index, (_group, _agg) in enumerate(zip(group, aggregation.agg))
                            )
                        )
                    )
                ))
        else:
            single_group = groups
            agg.append(
                merge_mappings(
                    chain(
                        *(
                            [
                                _resolve_agg_result(aggregation_index, sub_aggregation_index, individual_agg_method_index, agg_method(_group))
                                for individual_agg_method_index, agg_method in enumerate(_agg)
                            ]
                            for sub_aggregation_index, (_group, _agg) in enumerate(zip(single_group, aggregation.agg))
                        )
                    )
                )
            )

        out_aggs.append(agg)
    # endregion

    if unpack_single_aggregation_result and len(out_aggs) == 1:
        return out_aggs[0]
    else:
        return out_aggs


def construct_confusion_examples(
        data: List[Dict[str, Any]],
        reference_key: Union[str, Callable] = 'reference',
        prediction_key: Union[str, Callable] = 'prediction',
        data_key: Union[str, Callable] = 'data',
        confusion_format: str = '{reference}-{prediction}',
        non_atom_types: tuple = (list,)
) -> Dict[str, List[Any]]:
    """
    Constructs a dictionary of confusion examples from a list of dictionaries containing predictions, references,
    and additional data (e.g., counts, or example items). This dictionary groups the examples based on the
    confusion format specified, which could be a reference-prediction pair.

    Args:
        data (List[Dict[str, Any]]): A list of dictionaries containing reference, prediction, and data keys.
        reference_key (Union[str, Callable]): The key or callable to retrieve the reference (true label) from the dictionary.
        prediction_key (Union[str, Callable]): The key or callable to retrieve the prediction (predicted label) from the dictionary.
        data_key (Union[str, Callable]): The key or callable to retrieve the actual data (e.g., count, example, etc.) from the dictionary.
        confusion_format (str): A string format to define how confusion examples should be represented,
                                using {reference} and {prediction} placeholders.
        non_atom_types (tuple): A tuple of types that are considered non-atomic (e.g., list, dict). These types
                                will be flattened into the final list of examples.

    Returns:
        Dict[str, List[Any]]: A dictionary where the keys are formatted confusion pairs and the values
                              are lists of corresponding examples/data.

    Examples:
        Basic example with strings as `data`:
        >>> data = [
        ...     {'reference': 'cat', 'prediction': 'dog', 'data': 'example1'},
        ...     {'reference': 'cat', 'prediction': 'dog', 'data': 'example2'},
        ...     {'reference': 'cat', 'prediction': 'cat', 'data': 'example3'},
        ...     {'reference': 'dog', 'prediction': 'cat', 'data': 'example4'}
        ... ]
        >>> confusion_examples = construct_confusion_examples(data)
        >>> print(confusion_examples)
        {'cat-dog': ['example1', 'example2'], 'cat-cat': ['example3'], 'dog-cat': ['example4']}

        Example with a list as `data`:
        >>> data = [
        ...     {'reference': 'cat', 'prediction': 'dog', 'data': ['example1', 'example5']},
        ...     {'reference': 'cat', 'prediction': 'dog', 'data': 'example2'},
        ...     {'reference': 'dog', 'prediction': 'cat', 'data': ['example3', 'example4']}
        ... ]
        >>> confusion_examples = construct_confusion_examples(data)
        >>> print(confusion_examples)
        {'cat-dog': ['example1', 'example5', 'example2'], 'dog-cat': ['example3', 'example4']}

        Example with mixed data types in `data`:
        >>> data = [
        ...     {'reference': 'cat', 'prediction': 'dog', 'data': ['example1', 'example2']},
        ...     {'reference': 'cat', 'prediction': 'dog', 'data': 'example3'},
        ...     {'reference': 'cat', 'prediction': 'cat', 'data': ['example4', 'example5']}
        ... ]
        >>> confusion_examples = construct_confusion_examples(data)
        >>> print(confusion_examples)
        {'cat-dog': ['example1', 'example2', 'example3'], 'cat-cat': ['example4', 'example5']}

        Using a callable for `reference_key` and `prediction_key`:
        >>> data = [
        ...     {'true_label': 'cat', 'pred_label': 'dog', 'data': 'example1'},
        ...     {'true_label': 'cat', 'pred_label': 'cat', 'data': 'example2'}
        ... ]
        >>> confusion_examples = construct_confusion_examples(
        ...     data,
        ...     reference_key=lambda x: x['true_label'],
        ...     prediction_key=lambda x: x['pred_label']
        ... )
        >>> print(confusion_examples)
        {'cat-dog': ['example1'], 'cat-cat': ['example2']}
    """
    confusion_examples = defaultdict(list)

    for entry in data:
        # Get the reference, prediction, and data values
        reference = get_(entry, reference_key)
        prediction = get_(entry, prediction_key)
        data_value = get_(entry, data_key)

        # Construct the confusion pair using the specified format
        confusion_pair = confusion_format.format(reference=reference, prediction=prediction)

        # Append the data to the corresponding confusion pair
        if isinstance(data_value, non_atom_types):
            confusion_examples[confusion_pair].extend(data_value)
        else:
            confusion_examples[confusion_pair].append(data_value)

    return dict(confusion_examples)


def pd_construct_confusion_matrix(
        data: List[Dict[str, Any]],
        reference_key: Union[str, Callable] = 'reference',
        prediction_key: Union[str, Callable] = 'prediction',
        count_key: Union[str, Callable] = 'count',
        add_totals: bool = True,
        add_precision: bool = True,
        add_recall: bool = True,
        sort_key: Callable[[Any], Any] = None
) -> pd.DataFrame:
    """
    Constructs a confusion matrix from a list of dictionaries containing predictions, references, and counts.
    Optionally adds 'Total', 'Precision', and 'Recall' columns and rows. The keys for reference, prediction, and count
    can be strings or callables that retrieve the appropriate value. Additionally, custom sorting of row and column
    labels is supported.

    Args:
        data (List[Dict[str, Any]]): A list of dictionaries with keys for reference, prediction, and count.
        reference_key (Union[str, Callable]): The key name or a callable to retrieve the true label (reference). Defaults to 'reference'.
        prediction_key (Union[str, Callable]): The key name or a callable to retrieve the predicted label (prediction). Defaults to 'prediction'.
        count_key (Union[str, Callable]): The key name or a callable to retrieve the count of occurrences. Defaults to 'count'.
        add_totals (bool): Whether to add 'Total' rows and columns. Defaults to True.
        add_precision (bool): Whether to add a 'Precision' row. Defaults to True.
        add_recall (bool): Whether to add a 'Recall' column. Defaults to True.
        sort_key (Callable[[Any], Any], optional): A callable that defines the sorting order of the row and column labels.

    Returns:
        pd.DataFrame: A confusion matrix as a pandas DataFrame with optional totals, precision, and recall.

    Examples:
        >>> data = [
        ...     {'reference': 'SmartHomeExpert', 'prediction': 'ContactsExpert', 'count': 4},
        ...     {'reference': 'SmartHomeExpert', 'prediction': 'ExploreWithAlexaExpert', 'count': 4},
        ...     {'reference': 'SmartHomeExpert', 'prediction': 'SmartHomeExpert', 'count': 37},
        ...     {'reference': 'SmartHomeExpert', 'prediction': 'PersonalMemoryBankExpert', 'count': 7},
        ...     {'reference': 'AlarmsExpert', 'prediction': 'AlarmsExpert', 'count': 249},
        ...     {'reference': 'AdvertisingExpert', 'prediction': 'AnnouncementExpert', 'count': 1},
        ... ]
        >>> cm = pd_construct_confusion_matrix(data)
        >>> print(cm.to_string(max_rows=None, max_cols=None))
                                  AdvertisingExpert  AlarmsExpert  AnnouncementExpert  ContactsExpert  ExploreWithAlexaExpert  PersonalMemoryBankExpert  SmartHomeExpert  Total    Recall
        AdvertisingExpert                       0.0           0.0                 1.0             0.0                     0.0                       0.0              0.0    1.0  0.000000
        AlarmsExpert                            0.0         249.0                 0.0             0.0                     0.0                       0.0              0.0  249.0  1.000000
        AnnouncementExpert                      0.0           0.0                 0.0             0.0                     0.0                       0.0              0.0    0.0       NaN
        ContactsExpert                          0.0           0.0                 0.0             0.0                     0.0                       0.0              0.0    0.0       NaN
        ExploreWithAlexaExpert                  0.0           0.0                 0.0             0.0                     0.0                       0.0              0.0    0.0       NaN
        PersonalMemoryBankExpert                0.0           0.0                 0.0             0.0                     0.0                       0.0              0.0    0.0       NaN
        SmartHomeExpert                         0.0           0.0                 0.0             4.0                     4.0                       7.0             37.0   52.0  0.711538
        Total                                   0.0         249.0                 1.0             4.0                     4.0                       7.0             37.0  302.0  1.000000
        Precision                               NaN           1.0                 0.0             0.0                     0.0                       0.0              1.0    NaN       NaN

        Using a custom sort function to reverse the order:
        >>> custom_sort = lambda x: x[::-1]
        >>> cm_sorted = pd_construct_confusion_matrix(data, sort_key=custom_sort)
        >>> print(cm_sorted.to_string(max_rows=None, max_cols=None))
                                  ExploreWithAlexaExpert  SmartHomeExpert  AdvertisingExpert  PersonalMemoryBankExpert  AlarmsExpert  ContactsExpert  AnnouncementExpert  Total    Recall
        ExploreWithAlexaExpert                       0.0              0.0                0.0                       0.0           0.0             0.0                 0.0    0.0       NaN
        SmartHomeExpert                              4.0             37.0                0.0                       7.0           0.0             4.0                 0.0   52.0  0.711538
        AdvertisingExpert                            0.0              0.0                0.0                       0.0           0.0             0.0                 1.0    1.0  0.000000
        PersonalMemoryBankExpert                     0.0              0.0                0.0                       0.0           0.0             0.0                 0.0    0.0       NaN
        AlarmsExpert                                 0.0              0.0                0.0                       0.0         249.0             0.0                 0.0  249.0  1.000000
        ContactsExpert                               0.0              0.0                0.0                       0.0           0.0             0.0                 0.0    0.0       NaN
        AnnouncementExpert                           0.0              0.0                0.0                       0.0           0.0             0.0                 0.0    0.0       NaN
        Total                                        4.0             37.0                0.0                       7.0         249.0             4.0                 1.0  302.0  1.000000
        Precision                                    0.0              1.0                NaN                       0.0           1.0             0.0                 0.0    NaN       NaN
    """
    # Initialize a set to hold all unique labels (references and predictions)
    labels = set()

    # Build a dictionary to hold the matrix data
    matrix_data = {}

    for entry in data:
        ref = get_(entry, reference_key)
        pred = get_(entry, prediction_key)
        size = get_(entry, count_key)

        labels.add(ref)
        labels.add(pred)

        if ref not in matrix_data:
            matrix_data[ref] = {}

        if pred not in matrix_data[ref]:
            matrix_data[ref][pred] = 0

        matrix_data[ref][pred] += size

    # Sort labels if a custom sort function is provided
    if sort_key:
        labels = sorted(labels, key=sort_key)
    else:
        labels = sorted(labels)

    # Create a DataFrame with consistent labels as both rows and columns
    df = pd.DataFrame(index=labels, columns=labels)

    # Fill the DataFrame with the matrix data
    for ref in labels:
        for pred in labels:
            df.at[ref, pred] = matrix_data.get(ref, {}).get(pred, 0)

    df = df.fillna(0)

    if add_totals:
        # Add a 'Total' row and column
        df['Total'] = df.sum(axis=1)
        total_row = pd.DataFrame(df.sum(axis=0)).T
        total_row.index = ['Total']
        df = pd.concat([df, total_row])

    if add_recall:
        # Add a 'Recall' column
        df['Recall'] = df.apply(lambda row: row[row.name] / row['Total'] if row['Total'] != 0 else np.nan, axis=1)

    if add_precision:
        # Add a 'Precision' row
        precision_values = df.apply(lambda col: col[col.name] / col['Total'] if col.name in labels and col['Total'] != 0 else np.nan, axis=0)
        precision_row = pd.DataFrame(precision_values).T
        precision_row.index = ['Precision']
        df = pd.concat([df, precision_row])

    return df


def pd_get_top_k_confusions(confusion_matrix: pd.DataFrame, k: int = 5, exclude: Sequence[str] = ("Total", "Recall", "Precision")):
    """
    Identifies the top k confusions for each ground truth class from a confusion matrix.

    Args:
        confusion_matrix (pd.DataFrame): A confusion matrix where rows are ground truth and columns are predictions.
        k (int, optional): The number of top confusions to save for each ground truth class. Defaults to 5.
        exclude (Sequence, optional): A list of column/row names to exclude from processing. Defaults to ['Total', 'Recall', 'Precision'].

    Returns:
        pd.DataFrame: A DataFrame containing the top k confusions for each ground truth class.

    Example:
        >>> data = {
        ...     'ClassA': [50, 1, 4, 55, 0.91],
        ...     'ClassB': [2, 47, 5, 54, 0.87],
        ...     'ClassC': [3, 1, 40, 44, 0.81],
        ...     'Total': [55, 54, 44, 153, None],
        ...     'Precision': [0.91, 0.87, 0.81, None, None]
        ... }
        >>> df = pd.DataFrame(data, index=['ClassA', 'ClassB', 'ClassC', 'Total', 'Recall']).T
        >>> pd_get_top_k_confusions(df, k=2)
          Ground Truth   Confusion 1   Confusion 2
        0       ClassA  ClassC (4.0)  ClassB (1.0)
        1       ClassB  ClassC (5.0)  ClassA (2.0)
        2       ClassC  ClassA (3.0)  ClassB (1.0)

        >>> data = {
        ...     'ClassX': [30, 7, 2, 39, 0.77],
        ...     'ClassY': [6, 33, 3, 42, 0.79],
        ...     'ClassZ': [1, 4, 28, 33, 0.85],
        ...     'Total': [37, 44, 33, 114, None],
        ...     'Precision': [0.81, 0.75, 0.85, None, None]
        ... }
        >>> df = pd.DataFrame(data, index=['ClassX', 'ClassY', 'ClassZ', 'Total', 'Recall']).T
        >>> pd_get_top_k_confusions(df, k=2)
          Ground Truth   Confusion 1   Confusion 2
        0       ClassX  ClassY (7.0)  ClassZ (2.0)
        1       ClassY  ClassX (6.0)  ClassZ (3.0)
        2       ClassZ  ClassY (4.0)  ClassX (1.0)
    """

    # Remove any statistics rows and columns based on the exclude parameter
    exclude = list(set(exclude))
    if exclude:
        confusion_data = confusion_matrix.drop(columns=exclude, errors='ignore')
        confusion_data = confusion_data.loc[~confusion_data.index.isin(exclude)]
    else:
        confusion_data = confusion_matrix

    results = []
    # Iterate over each row in the confusion matrix
    for groundtruth_class, row in confusion_data.iterrows():
        # Exclude the diagonal (true positives) by setting the corresponding value to NaN
        row_without_diag = row.copy()
        row_without_diag[groundtruth_class] = float('nan')

        # Sort the row by the number of confusions in descending order and select the top k
        top_k_confusions = row_without_diag.sort_values(ascending=False).head(k)

        # Create a row for the CSV
        csv_row = [groundtruth_class]
        for predicted_class, count in top_k_confusions.items():
            if count > 0:
                csv_row.append(f"{predicted_class} ({count})")
            else:
                csv_row.append("")

        # Ensure the row has exactly k + 1 elements (1 for the ground truth + k for confusions)
        while len(csv_row) < k + 1:
            csv_row.append("")

        results.append(csv_row)

    # Convert the results to a DataFrame and return
    columns = ['Ground Truth'] + [f'Confusion {i + 1}' for i in range(k)]
    results_df = pd.DataFrame(results, columns=columns)
    return results_df
