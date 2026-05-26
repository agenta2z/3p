import os
import re
from collections import Mapping
from functools import partial
from typing import Union, Iterator

import nltk
from pyspark.sql import SparkSession

from python_utils.nlp_utils.common import PreDefinedNlpToolNames, Languages
from python_utils.nlp_utils._dev._archived.ner.spark_batch import ner_spark_batch
from python_utils.nlp_utils.part_of_speech.common import get_pos_tagging_method

NLTK_DATA_PATH_ENV_NAME = 'NLTK_DATA_PATH'

if NLTK_DATA_PATH_ENV_NAME in os.environ:
    nltk.data.path = [os.environ[NLTK_DATA_PATH_ENV_NAME]]

DEFAULT_POS_MAP_FOR_ENTITY_EXTRACTION = {
    'JJ': 'j',
    "JJR": "j",
    "JJS": "j",
    "NN": "n",
    "NNS": "n",
    "NNP": "n",
    "NNPS": "n",
    "CD": "c",
    "IN": "i",
    "VBG": "v",
    "VBN": "v"
}

DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION = re.compile(r'((j|(nv?)|c)*ni)?(j|(nv?)|c)*n')


def iter_entities_by_pos_pattern(
        text: Union[str, Iterator[str]],
        pos_map: Mapping = DEFAULT_POS_MAP_FOR_ENTITY_EXTRACTION,
        pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION,
        join_tokens=False,
        language: Languages = Languages.English,
        tool: PreDefinedNlpToolNames = PreDefinedNlpToolNames.NLTK,
        **pos_tagging_args
):
    """
    Iterates through possible entities in the given text that match the specified part-of-speech pattern.
    This function uses `pos_map` to map the original part-of-speech tags to simpler characters that makes the formulation of `pos_pattern` easier.
    For example, `pos_map = {'NN': 'n', 'NNS': 'n', 'NNP': 'n', 'NNPS': 'n'}`, then the text `this is the New York City` with its original part-of-speech tags 'DT VBZ NNP NNP NNP' will be mapped to `___nnn`, where pos-tags not in `pos_map` will be mapped to `_`.
    Then you can use a simple pattern `n+` to extract the entity `New York City`.

    Using the default.
    ------------------
    >>> text = "This case total doesn't reflect the number of active cases, but rather the total number of people infected since the start of the pandemic. That means, according to official statistics, New York City alone now has had more infections than the whole of China, which has reported 81,907 cases, according to the Chinese National Health Commission."
    >>> list(iter_entities_by_pos_pattern(text, join_tokens=True))
    ['case total', 'number of active cases', 'total number of people', 'start', 'pandemic', 'official statistics', 'New York City', 'more infections', 'whole of China', '81,907 cases', 'Chinese National Health Commission']

    Only extracts consecutive Nones.
    --------------------------------
    >>> list(iter_entities_by_pos_pattern(text, pos_map={'NN': 'n', 'NNS': 'n', 'NNP': 'n', 'NNPS': 'n'}, pos_pattern='n{2,3}', join_tokens=True))
    ['case total', 'New York City', 'Chinese National Health']

    More Examples.
    --------------
    >>> text = "what is the birthday of taylor swift"
    >>> list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True))
    ['birthday', 'taylor swift']
    >>> list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True, tool='flair'))
    ['birthday', 'taylor swift']

    >>> text = "what's the fox news briefing today"
    >>> list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True))
    ['fox news briefing today']
    >>> list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True, tool='flair'))
    ['fox news briefing today']

    >>> text = ["what is the birthday of taylor swift", "what's the fox news briefing today"]
    >>> list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True))
    [['birthday', 'taylor swift'], ['fox news briefing today']]
    >>> list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True, tool='flair'))
    [['birthday', 'taylor swift'], ['fox news briefing today']]

    :param text: can pass the text, or the tokens.
    :param pos_map: a dictionary that maps the original part-of-speech tags to single characters for easier formulation of `pos_pattern`.
    :param pos_pattern: the part-of-speech pattern.
    :param join_tokens: `True` to join extracted entity tokens; `False` to yield the tokens of each entity.
    :return: the extracted entities that match the specified part-of-speech pattern.
    """
    pos_tag_ = get_pos_tagging_method(tool, **pos_tagging_args)
    pos_tag_result = pos_tag_(text, language=language)

    def _get_ner_result(_pos_tag_result):
        tokens, tags = tuple(zip(*_pos_tag_result))
        tag_str = ''.join(pos_map.get(x, '_') for x in tags)
        if join_tokens:
            for match in re.finditer(pos_pattern, tag_str):
                start, end = match.span()
                yield ' '.join(tokens[start:end])
        else:
            for match in re.finditer(pos_pattern, tag_str):
                start, end = match.span()
                yield tokens[start:end]

    if isinstance(text, str):
        yield from _get_ner_result(pos_tag_result)
    else:
        for _pos_tag_result in pos_tag_result:
            yield list(_get_ner_result(_pos_tag_result))


def iter_entities_by_pos_pattern_(
        text: Union[str, Iterator[str]],
        pos_map: Mapping = DEFAULT_POS_MAP_FOR_ENTITY_EXTRACTION,
        pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION,
        join_tokens=True,
        language: Languages = Languages.English,
        tool: PreDefinedNlpToolNames = PreDefinedNlpToolNames.NLTK,
        **pos_tagging_args
):
    """
    The same as `iter_entities_by_pos_pattern`,
    but returns the a 3-tuple, the entity, the part-of-speech tags of that entity,
    and the entity's token index in the input `text_or_tokens`.
    """
    pos_tag_ = get_pos_tagging_method(tool, **pos_tagging_args)
    pos_tag_result = pos_tag_(text, language=language)

    def _get_ner_result(_pos_tag_result):
        tokens, tags = tuple(zip(*pos_tag_result))
        tag_str = ''.join(pos_map.get(x, '_') for x in tags)
        if join_tokens:
            for match in pos_pattern.finditer(tag_str):
                start, end = match.span()
                yield ' '.join(tokens[start:end]), tags[start:end], start
        else:
            for match in pos_pattern.finditer(tag_str):
                start, end = match.span()
                yield tokens[start:end], tags[start:end], start

    if isinstance(text, str):
        yield from _get_ner_result(pos_tag_result)
    else:
        for _pos_tag_result in pos_tag_result:
            yield list(_get_ner_result(_pos_tag_result))


def get_entities_by_pos_pattern(
        text: Union[str, Iterator[str]],
        pos_map: Mapping = DEFAULT_POS_MAP_FOR_ENTITY_EXTRACTION,
        pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION,
        join_tokens=False,
        language: Languages = Languages.English,
        tool: PreDefinedNlpToolNames = PreDefinedNlpToolNames.NLTK,
        **pos_tagging_args
):
    return list(iter_entities_by_pos_pattern(
        text=text,
        pos_map=pos_map,
        pos_pattern=pos_pattern,
        join_tokens=join_tokens,
        language=language,
        tool=tool,
        **pos_tagging_args
    ))


def get_entities_by_pos_pattern_udf(
        text,
        pos_map: Mapping = DEFAULT_POS_MAP_FOR_ENTITY_EXTRACTION,
        pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION,
        language: Languages = Languages.English,
        tool: PreDefinedNlpToolNames = PreDefinedNlpToolNames.NLTK,
        **pos_tagging_args
):
    from pyspark.sql.functions import udf
    from pyspark.sql.types import ArrayType, StringType
    return udf(
        partial(
            get_entities_by_pos_pattern,
            pos_map=pos_map,
            pos_pattern=pos_pattern,
            join_tokens=True,
            language=language,
            tool=tool,
            **pos_tagging_args
        ),
        returnType=ArrayType(elementType=StringType())
    )(text)


def ner_by_pos_pattern_spark_batch(
        df_text,
        text_field_name: str,
        ner_result_field_name: str,
        output_path: str,
        repartition: Union[int, bool],
        pos_map: Mapping = DEFAULT_POS_MAP_FOR_ENTITY_EXTRACTION,
        pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION,
        language: Languages = Languages.English,
        tool: PreDefinedNlpToolNames = PreDefinedNlpToolNames.NLTK,
        **pos_tagging_args
):
    return ner_spark_batch(
        df_text=df_text,
        text_field_name=text_field_name,
        ner_result_field_name=ner_result_field_name,
        output_path=output_path,
        repartition=repartition,
        ner_batch=partial(
            get_entities_by_pos_pattern,
            pos_map=pos_map,
            pos_pattern=pos_pattern,
            join_tokens=True,
            language=language,
            tool=tool,
            **pos_tagging_args
        )
    )


if __name__ == '__main__':
    text = "how long can a hamster live"
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))

    text = "WBEN two everywhere"
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))

    text = "turn living room lights"
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))

    text = "turn on the song catboy on p. j. masks"
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))

    text = "what's the fastest breeding today"
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=r'((j|n|c)*n)?(j|n|c)*n', join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))
    print(list(iter_entities_by_pos_pattern(text, pos_pattern=DEFAULT_PATTERN_FOR_ENTITY_EXTRACTION, join_tokens=True, tool=PreDefinedNlpToolNames.FLAIR)))
