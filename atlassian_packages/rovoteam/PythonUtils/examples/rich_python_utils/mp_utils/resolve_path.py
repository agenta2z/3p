import sys
from pathlib import Path

PIVOT_FOLDER_NAME = 'examples'
SRC_FOLDER_NAME = 'src'

def resolve_path():
    current = Path(__file__).resolve()
    while current != current.parent:  # Stop at filesystem root
        if current.name == PIVOT_FOLDER_NAME:
            src_path = current.parent / SRC_FOLDER_NAME
            if src_path.is_dir():
                sys.path.insert(0, str(src_path))
                break
        current = current.parent
    else:
        raise FileNotFoundError("Could not find 'examples' directory in path hierarchy")
