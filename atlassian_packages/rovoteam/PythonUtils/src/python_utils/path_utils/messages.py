# region IO/Path messages

def _ends_with_period(msg: str):
    return msg and msg[-1] == '.' and (len(msg) == 1 or msg[-2] != '.')


def extra_msg_wrap(func):
    def _wrap(*args, **kwargs):
        if 'extra_msg' in kwargs:
            extra_msg = kwargs.get('extra_msg')
            del kwargs['extra_msg']
            base_msg = func(*args, **kwargs)
            if _ends_with_period(base_msg):
                base_msg = base_msg[:-1]
            return (base_msg + (f'; {extra_msg}' if extra_msg else '.')) if base_msg else extra_msg
        else:
            return func(*args, **kwargs)

    return _wrap


@extra_msg_wrap
def msg_not_a_dir(path_str):
    return f"the specified path `{path_str}` is not a directory"


@extra_msg_wrap
def msg_arg_not_a_dir(path_str, arg_name):
    return f"the specified path `{path_str}` in argument `{arg_name}` is not a directory"


@extra_msg_wrap
def msg_arg_multi_path_not_exist(path_str, arg_name):
    return f"none of the path(s) specified in `{path_str}` in argument `{arg_name}` exist"


@extra_msg_wrap
def msg_arg_path_not_exist(path_str, arg_name):
    return f"the specified path `{path_str}` by argument/variable `{arg_name}` does not exist"


@extra_msg_wrap
def msg_batch_file_writing_to_dir(path_str, num_files):
    return f"total `{num_files}` files written to directory `{path_str}`"


@extra_msg_wrap
def msg_create_dir(path_str):
    return f"directory `{path_str}` does not exist; now create the directory"


@extra_msg_wrap
def msg_clear_dir(path_str):
    return f"directory `{path_str}` exists_path; clear any contents in it"


@extra_msg_wrap
def msg_skip_non_local_dir(path_str):
    return f"directory `{path_str}` seems non-local; unable to create or remove"

# endregion
