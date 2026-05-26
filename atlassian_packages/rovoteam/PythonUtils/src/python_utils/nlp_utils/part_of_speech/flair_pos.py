from typing import Union, Iterable, Callable

from flair.models import SequenceTagger
from flair.data import Sentence
import nltk

from python_utils.nlp_utils.common import (
    Languages, get_language_for_nltk_tokenizer, PreDefinedNlpToolNames
)
from python_utils.nlp_utils.part_of_speech.common import (
    get_flair_pos_tagger_name_by_language, get_pos_tagger
)


def pos_tag_(
        text: Union[str, Iterable[str]],
        break_into_sentences: bool = False,
        language: Union[str, Languages] = Languages.English,
        fast: bool = False,
        mini_batch_size=640,
        tagger: Callable = None
):
    """

    Args:
        text: one or more pieces of texts to tag with part-of-speech labels.
        break_into_sentences: `True` if to break a string input `text` into sentences
            before part-of-speech tagging.
        language: the language of the text.
        fast: True to use the fast version of tagger with less accuracy, if available.
        tagger: specifies a Flair part-of-speech tagger;
            if not specified, a default Flair part-of-speech tagger
            for the specified `language` will be used.

    Returns: a sequence of tuples of token and their part-of-speech labels.

    Examples:
        >>> pos_tag_(['turn living room lights', 'play NPO two radio'], fast=True)
        [[('turn', 'VB'), ('living', 'NN'), ('room', 'NN'), ('lights', 'NNS')], [('play', 'VB'), ('NPO', 'NNP'), ('two', 'CD'), ('radio', 'NN')]]

        >>> pos_tag_('turn living room lights')
        [('turn', 'VB'), ('living', 'NN'), ('room', 'NN'), ('lights', 'NNS')]

        >>> pos_tag_('turn living room lights', fast=True)
        [('turn', 'VB'), ('living', 'NN'), ('room', 'NN'), ('lights', 'NNS')]

        >>> pos_tag_('turn living room lights', language=Languages.MultiLanguage)
        [('turn', 'VERB'), ('living', 'VERB'), ('room', 'NOUN'), ('lights', 'NOUN')]

        >>> pos_tag_('wohnzimmerbeleuchtung einschalten', language=Languages.German)
        [('wohnzimmerbeleuchtung', 'NN'), ('einschalten', 'VVINF')]

    """
    if tagger is None:
        tagger: SequenceTagger = get_pos_tagger(
            tool=PreDefinedNlpToolNames.FLAIR,
            language=language,
            fast=fast
        )

    if isinstance(text, str) and break_into_sentences:
        text = nltk.sent_tokenize(text, language=get_language_for_nltk_tokenizer(language))

    def _get_pos_tag(_sentence):
        return [(token.text, token.tag) for token in _sentence.tokens]
        # labels = _sentence.get_labels('pos')
        # if labels:
        #     return [
        #         (label.data_point.text, label.data_point.tag)
        #         for label in labels
        #     ]
        # else:
        #     labels = sentence.labels
        #     return [
        #         (label.data_point.text, label.data_point.tag)
        #         for label in labels
        #     ]

    if isinstance(text, str):
        sentence = Sentence(text)
        tagger.predict(sentence)
        return _get_pos_tag(sentence)
    else:
        sentences = [Sentence(_text) for _text in text]
        tagger.predict(sentences, mini_batch_size=mini_batch_size, verbose=True)

        return [_get_pos_tag(sent) for sent in sentences]
