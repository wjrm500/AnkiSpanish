from typing import List

from consts import PrintColour as PC

def truncate_string(string: str, max_length: int = 20) -> str:
    return string[:max_length] + "..." if len(string) > max_length else string

"""
A class representing a pair of sentences, one in a source language and the translated version in the
target language. These sentence pairs are used to provide context for the definitions of a word.
"""
class SentencePair:
    source_sentence: str
    target_sentence: str

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source_sentence={truncate_string(self.source_sentence)}, english_sentence={truncate_string(self.target_sentence)})"

    def __init__(self, source_sentence: str, target_sentence: str) -> None:
        self.source_sentence = source_sentence
        self.target_sentence = target_sentence

    def stringify(self, verbose: bool = False) -> str:
        return f"{PC.BLUE}{self.source_sentence}{PC.RESET} - {PC.PURPLE}{self.target_sentence}{PC.RESET}" if verbose else self.target_sentence

"""
A class representing a definition of a word. A definition is a string of text, and is accompanied by
one or more sentence pairs, which provide context for the definition.

If you are wondering what the difference is between a definition and a translation, consider the
following examples:
- The Spanish word "amanecer"
    - This can be translated as:
        - A masculine noun - "dawn"
        - An impersonal verb - "to dawn"
        - An intransitive verb - "to wake up", "to stay up all night"
    - Therefore the word "amanecer" has three translations, one for each part of speech:
        - The masculine noun translation, with one definition - "dawn"
        - The impersonal verb translation, with one definition - "to dawn"
        - The intransitive verb translation, with two definitions - "to wake up" and "to stay up all
        night".
- The Spanish word "banco"
    - This is an example of a word that has only a single translation but multiple definitions.
    "Banco" can only be translated as a masculine noun, but has at least two definitions:
        - "bank" (financial institution)
        - "bench" (seat)
"""
class Definition:
    text: str
    sentence_pairs: List[SentencePair]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(text={self.text})"

    def __init__(self, text: str, sentence_pairs: List[SentencePair]) -> None:
        if not text:
            raise ValueError("Text cannot be empty.")
        if not sentence_pairs:
            raise ValueError("Sentence pairs cannot be empty.")
        self.text = text
        self.sentence_pairs = sentence_pairs

    def stringify(self, verbose: bool = False) -> str:
        s = f"{PC.YELLOW}{self.text}{PC.RESET}"
        if verbose:
            for sentence_pair in self.sentence_pairs:
                s += f"\n   {sentence_pair.stringify(verbose)}"
        return s

"""
A class representing a translation of a word. A translation consists of the word to translate, the
part of speech to which the word belongs, and a list of definitions. A word can have multiple
translations if it belongs to multiple parts of speech, while a translation can have multiple
definitions if the word has multiple meanings within that part of speech.

See the Definition class docstring for an explanation of the difference between a definition and a
translation.
"""
class Translation:
    word_to_translate: str
    part_of_speech: str
    definitions: List[Definition]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(word_to_translate={self.word_to_translate}, part_of_speech={self.part_of_speech})"
    
    def __init__(
        self, word_to_translate: str, part_of_speech: str, definitions: List[Definition],
        max_definitions: int = 3
    ) -> None:
        if not word_to_translate:
            raise ValueError("Word to translate cannot be empty.")
        if not part_of_speech:
            raise ValueError("Part of speech cannot be empty.")
        if not definitions:
            raise ValueError("Definitions cannot be empty.")
        self.word_to_translate = word_to_translate
        self.part_of_speech = part_of_speech
        self.definitions = definitions[:max_definitions]
    
    def stringify(self, verbose: bool = False) -> str:
        s = f"{PC.GREEN}{self.word_to_translate} ({self.part_of_speech}) - {', '.join([definition.text for definition in self.definitions])}{PC.RESET}"
        if verbose:
            for definition in self.definitions:
                s += f"\n{definition.stringify(verbose)}"
        return s