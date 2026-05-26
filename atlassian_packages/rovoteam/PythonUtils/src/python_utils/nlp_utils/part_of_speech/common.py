from functools import partial
from typing import Union

from python_utils.common_utils.function_helper import get_relevant_named_args
from python_utils.console_utils import hprint_message
from python_utils.nlp_utils.common import (
    Languages, get_language_for_nltk_pos_tagger, PreDefinedNlpToolNames
)


def get_flair_pos_tagger_name_by_language(language: Union[str, Languages], fast: bool = True):
    if fast:
        if language == Languages.English:
            return 'flair/pos-english-fast'
        elif language == Languages.MultiLanguage:
            return 'flair/upos-multi-fast'
        elif language == Languages.German:
            return 'de-pos'
        else:
            raise ValueError(f"language '{language}' is not supported "
                             f"for Flair part-of-speech tagging")
    else:
        if language == Languages.English:
            return 'pos'
        elif language == Languages.MultiLanguage:
            return 'flair/upos-multi'
        elif language == Languages.German:
            return 'de-pos'
        else:
            raise ValueError(f"language '{language}' is not supported "
                             f"for Flair part-of-speech tagging")


def get_pos_tagger(
        tool: PreDefinedNlpToolNames,
        language: Languages = Languages.English,
        **kwargs
):
    if tool == PreDefinedNlpToolNames.NLTK:
        from nltk.tag import _get_tagger, _pos_tag
        language_pos_tagger = get_language_for_nltk_pos_tagger(language)
        return partial(
            _pos_tag,
            tagger=_get_tagger(language_pos_tagger),
            lang=language_pos_tagger
        )
    elif tool == PreDefinedNlpToolNames.FLAIR:
        from flair.models import SequenceTagger
        pos_tagger_name = get_flair_pos_tagger_name_by_language(
            language=language,
            fast=kwargs.get('fast', True)
        )
        return SequenceTagger.load(pos_tagger_name)
    else:
        raise ValueError(f"{tool} is supported part-of-speech tagging")


def get_pos_tagging_method(tool: PreDefinedNlpToolNames, **kwargs):
    if tool == PreDefinedNlpToolNames.NLTK:
        from python_utils.nlp_utils.part_of_speech.nltk_pos import pos_tag_
    elif tool == PreDefinedNlpToolNames.FLAIR:
        from python_utils.nlp_utils.part_of_speech.flair_pos import pos_tag_
    else:
        raise ValueError(f"{tool} is supported part-of-speech tagging")

    _pos_tag_args = get_relevant_named_args(pos_tag_, **kwargs)
    hprint_message(
        ('pos_tag_method', pos_tag_),
        *_pos_tag_args.items(),
        title='pos_tag_args'
    )
    return partial(pos_tag_, **_pos_tag_args)
