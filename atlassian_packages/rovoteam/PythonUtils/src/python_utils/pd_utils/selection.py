from pandas import DataFrame


def select_range_inclusive(df: DataFrame, colname: str, start, end):
    return df[(df[colname] >= start) & (df[colname] <= end)]


def select_range(df: DataFrame, colname: str, start, end):
    return df[(df[colname] > start) & (df[colname] <= end)]
