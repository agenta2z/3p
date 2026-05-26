import warnings
from os import environ
from pathlib import Path

_IS_NLTK_LOADED = False
_IS_FLAIR_LOADED = False

ENV_PATH_NLTK_DATA = 'NLTK_DATA_PATH'
ENV_PATH_FLAIR_CACHE = 'FLAIR_CACHE_PATH'

if ENV_PATH_NLTK_DATA in environ and environ[ENV_PATH_NLTK_DATA]:

    try:
        import nltk

        _IS_NLTK_LOADED = True
    except Exception as err:
        warnings.warn(f"package 'nltk' cannot be loaded; error '{err}'")

    if _IS_FLAIR_LOADED:
        nltk.data.path = [environ[ENV_PATH_NLTK_DATA]]

if ENV_PATH_FLAIR_CACHE in environ and environ[ENV_PATH_FLAIR_CACHE]:
    try:
        import flair

        _IS_FLAIR_LOADED = True
    except Exception as err:
        warnings.warn(f"package 'flair' cannot be loaded; error '{err}'")

    if _IS_FLAIR_LOADED:
        flair.cache_root = Path(environ[ENV_PATH_FLAIR_CACHE])
