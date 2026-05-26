try:
    from enum import StrEnum


    class SearchFallbackOptions(StrEnum):
        EOS = 'eos',
        Empty = 'empty'
        RaiseError = 'error'
except:
    from enum import Enum


    class SearchFallbackOptions(str, Enum):
        EOS = 'eos',
        Empty = 'empty'
        RaiseError = 'error'