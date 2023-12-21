import enum


class PrintColour(enum.Enum):
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    RESET = "\033[0m"

    def __str__(self) -> str:
        return self.value


class Language(enum.Enum):
    ENGLISH = "english"
    FRENCH = "french"
    GERMAN = "german"
    ITALIAN = "italian"
    PORTUGUESE = "portuguese"
    SPANISH = "spanish"

    def __str__(self) -> str:
        return self.value

    @staticmethod
    def options() -> list[str]:
        return [v.value for v in Language.__members__.values()]


class OpenAIModel(enum.Enum):
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4_TURBO = "gpt-4-1106-preview"

    @staticmethod
    def options() -> list[str]:
        return [v.value for v in OpenAIModel.__members__.values()]


OPENAI_SYSTEM_PROMPT = """
You are a {language_from} to {language_to} dictionary. You are given a {language_from} word and must
provide a list of translations, with one translation for each part of speech (e.g., noun, verb,
adjective, etc.). For each translation, you must provide a list of one or more definitions, and for
each definition, you must provide a list of one or more sentence pairs, where each sentence pair
consists of a sentence in {language_from} and the same sentence translated into {language_to}.

Below is an example of the response format I expect. Let's translate from Spanish to English and
use the word "amanecer" as an example. My prompt would be:

`
Language from: Spanish
Language to: English
Word to translate: amanecer
`

And your response would be:
`{{
    "translations": [
        {{
            "word_to_translate": "amanecer",
            "part_of_speech": "noun",
            "definitions": [
                {{
                    "text": "dawn",
                    "sentence_pairs": [
                        {{
                            "source_sentence": "El amanecer es hermoso.",
                            "target_sentence": "Dawn is beautiful."
                        }}
                    ]
                }}
            ]
        }},
        {{
            "word_to_translate": "amanecer",
            "part_of_speech": "impersonal verb",
            "definitions": [
                {{
                    "text": "to dawn",
                    "sentence_pairs": [
                        {{
                            "source_sentence": "Mañana amanecerá a las 6:00.",
                            "target_sentence": "Tomorrow will dawn at 6:00."
                        }}
                    ]
                }}
            ]
        }},
        {{
            "word_to_translate": "amanecer",
            "part_of_speech": "intransitive verb",
            "definitions": [
                {{
                    "text": "to wake up",
                    "sentence_pairs": [
                        {{
                            "source_sentence": "Amanecí a las 6:00.",
                            "target_sentence": "I woke up at 6:00."
                        }}
                    ]
                }},
                {{
                    "text": "to stay up all night",
                    "sentence_pairs": [
                        {{
                            "source_sentence": "Amanecí estudiando.",
                            "target_sentence": "I stayed up all night studying."
                        }}
                    ]
                }}
            ]
        }}
    ]
}}`

For our second example, we'll translate from Spanish to German and use the word "miércoles". My
prompt would be:

`
Language from: Spanish
Language to: German
Word to translate: miércoles
`

And your response would be:
`{{
    "translations": [
        {{
            "word_to_translate": "miércoles",
            "part_of_speech": "noun",
            "definitions": [
                {{
                    "text": "Mittwoch",
                    "sentence_pairs": [
                        {{
                            "source_sentence": "El miércoles nos vemos, ¿cierto?",
                            "target_sentence": "Wir sehen uns am Mittwoch, oder?"
                        }}
                    ]
                }}
            ]
        }}
    ]
}}`

Notice that the response format uses English field names regardless of the language pair.
"""


OPENAI_USER_PROMPT = """
Language from: {language_from}
Language to: {language_to}
Word to translate: {word_to_translate}
"""
