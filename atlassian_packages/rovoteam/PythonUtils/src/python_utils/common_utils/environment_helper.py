import importlib
import os
from contextlib import contextmanager


def is_ipython():
    try:
        __IPYTHON__
        return True
    except NameError:
        return False


@contextmanager
def add_to_path(p):
    """
    Allows temporarily adding a path to environment for the context.
    """
    import sys
    old_path = sys.path
    sys.path = sys.path[:]
    sys.path.insert(0, p)
    try:
        yield
    finally:
        sys.path = old_path


def path_import(pathstr):
    """
    Loads a module from the specified path.
    """
    from python_utils.path_utils.path_string_operations import abspath_
    pathstr = abspath_(pathstr)
    with add_to_path(os.path.dirname(pathstr)):
        spec = importlib.util.spec_from_file_location(pathstr, pathstr)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
