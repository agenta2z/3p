from enum import Enum


class Languages(str, Enum):
    English = 'en',
    German = 'de'
    Spanish = 'es'
    French = 'fr'
    MultiLanguage = 'multi'


class PreDefinedNlpToolNames:
    NLTK = 'nltk'
    FLAIR = 'flair'


def get_language_for_nltk_tokenizer(language: Languages):
    if language == Languages.English:
        return 'english'
    else:
        raise ValueError(f"language '{language}' is not supported")


def get_language_for_nltk_pos_tagger(language: Languages):
    if language == Languages.English:
        return 'eng'
    else:
        raise ValueError(f"language '{language}' is not supported")
