from typing import Union, Iterable, Callable

import nltk

from python_utils.nlp_utils.common import (
    Languages, get_language_for_nltk_tokenizer, get_language_for_nltk_pos_tagger, PreDefinedNlpToolNames
)
from python_utils.nlp_utils.part_of_speech.common import get_pos_tagger


def pos_tag_(
        text: Union[str, Iterable[str]],
        break_into_sentences: bool = False,
        language: Union[str, Languages] = Languages.English,
        tagger: Callable = None
):
    """

    Args:
        text: one or more pieces of texts to tag with part-of-speech labels.
        break_into_sentences: `True` if to break a string input `text` into sentences
            before part-of-speech tagging.
        language: the language of the text.
        tagger: specifies a NLTK part-of-speech tagger;
            if not specified, a default NLTK part-of-speech tagger
            for the specified `language` will be used.

    Returns: a sequence of tuples of token and their part-of-speech labels.

    Examples:
        >>> pos_tag_('turn on living room lights')
        [('turn', 'NN'), ('on', 'IN'), ('living', 'NN'), ('room', 'NN'), ('lights', 'NNS')]

    """

    language_tokenizer = get_language_for_nltk_tokenizer(language)
    if tagger is None:
        tagger = get_pos_tagger(
            tool=PreDefinedNlpToolNames.NLTK,
            language=language
        )

    if isinstance(text, str) and break_into_sentences:
        # tokenize the article into sentences, then tokenize each sentence into words
        text = [
            nltk.word_tokenize(sent, language=language_tokenizer)
            for sent in nltk.sent_tokenize(text, language=language_tokenizer)
        ]
        # tag each tokenized sentence into parts of speech: pos_sentences
    elif isinstance(text, (list, tuple)):
        text = [
            (
                nltk.word_tokenize(sent, language=language_tokenizer)
                if isinstance(sent, str)
                else sent
            )
            for sent in text
        ]

    if isinstance(text, str):
        return tagger(nltk.word_tokenize(text, language=language_tokenizer))
    else:
        return [tagger(sent) for sent in text]
