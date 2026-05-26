from abc import ABC


class FilterConfig(ABC):
    def filter(self, x, *args, **kwargs):
        raise NotImplementedError


class FilterCondConfig(ABC):
    def get_filter_cond(self, **kwargs):
        raise NotImplementedError
