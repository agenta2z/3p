import csv
from io import TextIOWrapper
from itertools import chain, islice
from os import path
from typing import Any, Type, Sequence
from typing import Dict, Union, Iterable, Iterator, Optional

from python_utils.common_utils.iter_helper import tqdm_wrap
from python_utils.common_utils.typing_helper import str2val_, all_str, is_str
from python_utils.path_utils.path_listing import get_sorted_files_from_all_sub_dirs
from python_utils.path_utils.common import ensure_dir_existence


def write_csv(tup_iter, output_csv_path, sep='\t', header=None, append=False, encoding='utf-8', create_dir=True, flatten=False):
    """
    Writes tuples/lists to a csv file.

    :param tup_iter: an iterator of tuples or lists.
    :param output_csv_path: the output csv file will be saved at this path.
    :param sep: the csv field separator.
    :param header: provide the header for the csv file; the header will be written as the first line of the csv file if `append` is set `False`.
    :param append: `True` to use append mode; otherwise, `False`.
    :param encoding: specifies the csv file encoding; the default is 'utf-8'.
    """
    if create_dir:
        ensure_dir_existence(path.dirname(output_csv_path), verbose=False)

    with open(output_csv_path, 'a' if append else 'w', encoding=encoding) as csv_f:
        if flatten:
            if header is not None and append is False:
                csv_f.write(sep.join(((sep.join(x) if isinstance(x, (tuple, list)) else x) for x in header)))
                csv_f.write('\n')
            for tup in tup_iter:
                csv_f.write(sep.join(((sep.join(map(str, x)) if isinstance(x, (tuple, list)) else str(x)) for x in tup)))
                csv_f.write('\n')
        else:
            if header is not None and append is False:
                csv_f.write(sep.join(header))
                csv_f.write('\n')
            for tup in tup_iter:
                csv_f.write(sep.join(str(x) for x in tup))
                csv_f.write('\n')


def iter_csv(
        csv_input: Union[str, TextIOWrapper],
        selection: Optional[Union[int, Iterable[int], str, Iterable[str]]] = None,
        sep: str = '\t',
        quotechar: str = '"',
        quoting: int = csv.QUOTE_MINIMAL,
        encoding: str = 'utf-8',
        header: Union[bool, str] = True,
        parse: bool = False,
        result_type: Type = tuple,
        allow_missing_cols: bool = False,
        top: int = None,
        use_tqdm: bool = True,
        disp_msg: Optional[str] = None,
        verbose: bool = __debug__,
        **kwargs
) -> Iterable[Any]:
    """
    Iterates through each line of a CSV file.

    Args:
        csv_input: The path to the CSV file or a file object.
        selection: Only reads specific columns of the CSV file. Defaults to None.
        sep: The separator for the CSV file. Defaults to '\t'.
        quotechar: A one-character string used to quote fields containing special characters. Defaults to '"'.
        quoting: Controls when quotes should be recognized in the input. Can be one of csv.QUOTE_MINIMAL,
        csv.QUOTE_ALL, csv.QUOTE_NONNUMERIC, or csv.QUOTE_NONE. Defaults to csv.QUOTE_MINIMAL.
        encoding: The encoding for the CSV file. Defaults to 'utf-8'.
        header: `True` to indicate the CSV file has a header line; otherwise `False`; specially,
            can specify 'skip' to skip the first line, no matter whether it is a header. Defaults to True.
        parse: `True` to parse the strings in each field as their likely Python values. Defaults to False.
        result_type: The type of container to return for each row. Must be one of: list, tuple, or dict.
            When using 'dict', the CSV file must have a header. Defaults to tuple.
        allow_missing_cols: `True` to allow missing columns in the CSV file. Defaults to False.
        top: The maximum number of rows to read from the CSV file.
            If None or not specified, all rows will be read.
        use_tqdm: `True` to display a progress bar while iterating through the CSV file; otherwise `False`..
        disp_msg: The message to display on the tqdm progress bar.
        verbose: `True` to display debugging information; otherwise `False`.
        kwargs: additional named argument for `csv.reader`

    Returns:
        Iterable[Any]: An iterator that yields a container (list, tuple, or dict) at a time,
            corresponding to one line of the CSV file.

    Examples:
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        ...     _ = f.write('''name,age
        ... Alice,30
        ... Bob,25''')
        ...     _ = f.seek(0)
        ...     for row in iter_csv(f.name, sep=",", result_type=dict):
        ...         print(row)
        ...
        {'name': 'Alice', 'age': '30'}
        {'name': 'Bob', 'age': '25'}


        >>> with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        ...     _ = f.write('''name,age
        ... Alice,30
        ... Bob,25''')
        ...     _ = f.seek(0)
        ...     for row in iter_csv(f.name, selection=[0], sep=",", header=True, parse=True, result_type=tuple):
        ...         print(row)
        ...
        ('Alice',)
        ('Bob',)


        >>> with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        ...     _ = f.write('''name,age
        ... Alice,30
        ... Bob,25''')
        ...     _ = f.seek(0)
        ...     for row in iter_csv(f.name, selection=[1], sep=",", header=True, parse=True, top=1, result_type=list):
        ...         print(row)
        ...
        [30]

        >>> with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        ...     _ = f.write('''name,age
        ... Alice,30
        ... Bob,25''')
        ...     _ = f.seek(0)
        ...     for row in iter_csv(f.name, selection=['age'], sep=",", header=True, parse=True, result_type=list):
        ...         print(row)
        ...
        [30]
        [25]

    """

    if result_type not in (list, tuple, dict):
        raise ValueError("result_type must be one of the following: list, tuple, or dict")

    if isinstance(csv_input, str):
        f = open(csv_input, 'r', encoding=encoding)
    else:
        f = csv_input

    csv_reader = csv.reader(f, delimiter=sep, quotechar=quotechar, quoting=quoting, **kwargs)

    try:
        if header is True or header == 'skip':
            header_fields = next(csv_reader)

            if isinstance(selection, str):
                if selection in header_fields:
                    selection = header_fields.index(selection)
                else:
                    raise ValueError(f"key '{selection}' does not exist in the header")
            elif isinstance(selection, Sequence):
                col_index_or_key2 = []
                for _col_index_or_key in selection:
                    if isinstance(_col_index_or_key, str):
                        if _col_index_or_key in header_fields:
                            col_index_or_key2.append(header_fields.index(_col_index_or_key))
                        else:
                            raise ValueError(f"key '{_col_index_or_key}' does not exist in the header")
                    else:
                        col_index_or_key2.append(_col_index_or_key)
                selection = col_index_or_key2
        if top:
            csv_reader = islice(csv_reader, top)

        csv_reader = tqdm_wrap(
            csv_reader,
            use_tqdm=use_tqdm,
            tqdm_msg=disp_msg,
            verbose=verbose
        )

        def process_line(splits):
            if parse:
                processed_splits = [str2val_(s.strip()) for s in splits]
            else:
                processed_splits = [s.strip() for s in splits]

            if len(processed_splits) == 1 and not processed_splits[0]:
                return

            if selection is None:
                return processed_splits
            elif isinstance(selection, int):
                return processed_splits[selection] if selection < len(splits) else None,
            else:
                if allow_missing_cols:
                    return [
                        processed_splits[col_idx]
                        if (col_idx is not None and col_idx < len(splits))
                        else None for col_idx in selection
                    ]
                else:
                    return [processed_splits[col_idx] for col_idx in selection]

        if result_type == dict:
            if header is not True:
                raise ValueError("result_type 'dict' requires a header")

            for line in csv_reader:
                processed_data = process_line(line)
                if processed_data is not None:
                    yield {header_fields[i]: processed_data[i] for i in range(len(header_fields))}
        else:
            for line in csv_reader:
                processed_data = process_line(line)
                if processed_data is not None:
                    yield result_type(processed_data)

    finally:
        if isinstance(csv_input, str):
            f.close()


def iter_all_csv_objs_from_all_sub_dirs(
        input_path_or_paths: Union[str, Iterable[str]],
        pattern: str = '*.csv',
        use_tqdm: bool = False,
        display_msg: str = None,
        verbose: bool = __debug__,
        encoding: str = None,
        selection: Union[int, Iterable[int], str, Iterable[str]] = None,
        sep: str = '\t',
        quotechar: str = '"',
        quoting: int = csv.QUOTE_MINIMAL,
        header: Union[bool, str] = True,
        parse: bool = False,
        result_type: Type = tuple,
        allow_missing_cols: bool = False,
        top: int = None,
        top_per_input_path: int = None
) -> Iterator[Dict]:
    """
        Iterate through all CSV objects from all subdirectories of a given directory or directories,
    matching a specified pattern.

    Args:
        input_path_or_paths: Path to the parent directory containing the subdirectories or path to the
                             CSV file(s), or a list of such paths.
        pattern: Search for files of this pattern, e.g., '*.csv'. Default is '*.csv'.
        use_tqdm: If True, use tqdm to display reading progress. Default is False.
        display_msg: Message to display for this reading.
        verbose: If True, print out the display_msg regardless of use_tqdm. Default is __debug__.
        encoding: File encoding. Default is None.
        selection: Index(s) or key(s) of the column(s) to select.
            Default is None (select all columns).
        sep: The delimiter used in the CSV file. Default is '\t'.
        quotechar: The character used to quote fields containing special characters. Default is '"'.
        quoting: The quoting mode, as specified in the csv module. Default is csv.QUOTE_MINIMAL.
        header: If True, the first row is treated as the header. If False, no header row is expected.
                If given a string, it will be used as the header row. Default is True.
        parse: If True, try to parse the data into the appropriate data types. Default is False.
        result_type: Type of the result objects. Default is tuple.
        allow_missing_cols: If True, allow rows with fewer columns than the header. Default is False.
        top: Total number of CSV objects to read from all input files. Default is None.
        top_per_input_path: Number of CSV objects to read from each input path;
            not effective if there is only one input path.

    Returns:
        An iterator yielding CSV objects found in all subdirectories of the given parent directory
        or directories.

    Example:
        In this example, we create a temporary directory with two subdirectories, each containing
        a CSV file with two rows of data. The iter_all_csv_objs_from_all_sub_dirs function is then
        called to iterate through all CSV objects in these files.

        >>> import os
        >>> import tempfile
        >>> from pathlib import Path

        >>> with tempfile.TemporaryDirectory() as temp_dir:
        ...     sub_dir1 = Path(temp_dir, "subdir1")
        ...     sub_dir1.mkdir()
        ...     sub_dir2 = Path(temp_dir, "subdir2")
        ...     sub_dir2.mkdir()
        ...
        ...     csv_content1 = '''Name,Age
        ...     Alice,30
        ...     Bob,25
        ...     '''
        ...     csv_content2 = '''Name,Age
        ...     Carol,33
        ...     Dave,29
        ...     '''
        ...
        ...     with open(os.path.join(sub_dir1, "data1.csv"), "w") as f1:
        ...         _ = f1.write(csv_content1)
        ...
        ...     with open(os.path.join(sub_dir2, "data2.csv"), "w") as f2:
        ...         _ = f2.write(csv_content2)
        ...
        ...     # Now we will use the iter_all_csv_objs_from_all_sub_dirs function to read the CSV objects
        ...     for csv_obj in iter_all_csv_objs_from_all_sub_dirs(
        ...         input_path_or_paths=temp_dir,
        ...         pattern="*.csv",
        ...         sep=",",
        ...         header=True,
        ...         parse=True
        ...     ):
        ...         print(csv_obj)
        ...
        ('Alice', 30)
        ('Bob', 25)
        ('Carol', 33)
        ('Dave', 29)
    """

    def _iter_all_csv_objs_from_single_input_path(input_path: str):
        if path.isfile(input_path):
            all_files = [input_path]
        else:
            all_files = get_sorted_files_from_all_sub_dirs(dir_path=input_path, pattern=pattern)

        for csv_file in all_files:
            yield from iter_csv(
                csv_input=csv_file,
                use_tqdm=use_tqdm,
                disp_msg=display_msg,
                verbose=verbose,
                encoding=encoding,
                selection=selection,
                sep=sep,
                quotechar=quotechar,
                quoting=quoting,
                header=header,
                parse=parse,
                result_type=result_type,
                allow_missing_cols=allow_missing_cols,
                top=top_per_input_path
            )

    if isinstance(input_path_or_paths, str):
        return _iter_all_csv_objs_from_single_input_path(input_path=input_path_or_paths)
    else:
        _it = chain(
            *(
                _iter_all_csv_objs_from_single_input_path(input_path=input_path)
                for input_path in input_path_or_paths
            )
        )
        if top:
            _it = islice(_it, top)
        return _it
