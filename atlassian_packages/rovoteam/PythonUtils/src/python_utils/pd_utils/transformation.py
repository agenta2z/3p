from typing import Union, Iterable

from pandas import DataFrame

from python_utils.common_utils import iter_


def shift(df: DataFrame, colnames: Union[str, Iterable[str]], num_rows: int) -> DataFrame:
    for colname in iter_(colnames):
        df[colname] = df[colname].shift(num_rows)
    return df