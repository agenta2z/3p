from collections import defaultdict
from datetime import datetime
from time import time
from uuid import uuid4

DEFAULT_TOC_MSG = 'Done!'
_tic_toc_dict = defaultdict(list)
_last_key = None


def tic(msg: str = None, key=None, newline=False, verbose=True):
    global _last_key
    cur_time = time()
    if key is None:
        _last_key = key = uuid4()
    time_stack = _tic_toc_dict[key]
    if time_stack:
        if not time_stack[-1][1]:
            print()
        time_stack[-1][3] = True  # sets nested flag
    time_stack.append([cur_time, newline, msg, False])

    if msg and verbose:
        print("{} ({}).".format((msg[:-1] if msg[-1] == '.' and (len(msg) == 1 or msg[-2] != '.') else msg), datetime.now().strftime("%I:%M %p on %B %d, %Y")), end='\n' if newline else ' ')
    return key


def toc(msg: str = DEFAULT_TOC_MSG, key=None, verbose=True):
    curr_time = time()
    key = key or _last_key

    if key in _tic_toc_dict:
        time_stack = _tic_toc_dict[key]
        if len(time_stack) == 0:
            del _tic_toc_dict[key]
            return
    else:
        return

    last_time, tic_new_line, tic_msg, nested = time_stack.pop()
    if time_stack:
        time_stack[-1][1] = True  # sets newline flag
    else:
        del _tic_toc_dict[key]
    time_diff = curr_time - last_time

    if verbose:
        if nested and tic_msg:
            print("{} ({}, {:.5f} secs elapsed).".format(msg, tic_msg, time_diff))
        elif msg:
            print("{} ({:.5f} secs elapsed).".format(msg, time_diff))
        else:
            print("{:.5f} secs elapsed.".format(time_diff))
    return time_diff
