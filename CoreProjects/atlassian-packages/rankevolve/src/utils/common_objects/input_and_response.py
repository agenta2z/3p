from typing import Any, NamedTuple


class InputAndResponse(NamedTuple):
    input: Any
    response: Any

    def __str__(self):
        return str(self.response)
