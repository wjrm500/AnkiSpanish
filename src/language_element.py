from __future__ import annotations

from constant import PrintColour as PC
from synonym import SynonymChecker


def truncate_string(string: str, max_length: int = 20) -> str:
    return string[:max_length] + "..." if len(string) > max_length else string


class SentencePair:
    """
    A class representing a pair of sentences, one in a source language and the translated version in
    the target language. These sentence pairs are used to provide context for the definitions of a
    word.
    """

    source_sentence: str
    target_sentence: str
    definition: "Definition"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SentencePair):
            return NotImplemented
        return (
            self.source_sentence == other.source_sentence
            and self.target_sentence == other.target_sentence
        )

    def __hash__(self) -> int:
        return hash((self.source_sentence, self.target_sentence))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source_sentence={truncate_string(self.source_sentence)}, english_sentence={truncate_string(self.target_sentence)})"  # noqa: E501

    def __init__(self, source_sentence: str, target_sentence: str) -> None:
        self.source_sentence = source_sentence
        self.target_sentence = target_sentence

    def set_definition(self, definition: "Definition") -> None:
        self.definition = definition

    def stringify(self, verbose: bool = False) -> str:
        return (
            f"{PC.BLUE}{self.source_sentence}{PC.RESET} - {PC.PURPLE}{self.target_sentence}{PC.RESET}"  # noqa: E501
            if verbose
            else self.target_sentence
        )


class Definition:
    """
    A class representing a definition of a word. A definition is a string of text, and is
    accompanied by one or more sentence pairs, which provide context for the definition.

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
            - The intransitive verb translation, with two definitions - "to wake up" and "to stay up
            all night".
    - The Spanish word "banco"
        - This is an example of a word that has only a single translation but multiple definitions.
        "Banco" can only be translated as a masculine noun, but has at least two definitions:
            - "bank" (financial institution)
            - "bench" (seat)
    """

    text: str
    sentence_pairs: list[SentencePair]
    translation: "Translation"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Definition):
            return NotImplemented
        return self.text == other.text and self.sentence_pairs == other.sentence_pairs

    def __hash__(self) -> int:
        return hash((self.text, tuple(self.sentence_pairs)))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(text={self.text})"

    def __init__(self, text: str, sentence_pairs: list[SentencePair]) -> None:
        if not text:
            raise ValueError("Text cannot be empty.")
        if not sentence_pairs:
            raise ValueError("Sentence pairs cannot be empty.")
        self.text = text
        self.sentence_pairs = sentence_pairs
        for sentence_pair in self.sentence_pairs:
            sentence_pair.set_definition(self)

    def set_translation(self, translation: "Translation") -> None:
        self.translation = translation

    def stringify(self, verbose: bool = False) -> str:
        s = f"{PC.YELLOW}{self.text}{PC.RESET}"
        if verbose:
            for sentence_pair in self.sentence_pairs:
                s += f"\n   {sentence_pair.stringify(verbose)}"
        return s


class Translation:
    """
    A class representing a translation of a word. A translation consists of the word to translate,
    the part of speech to which the word belongs, and a list of definitions. A word can have
    multiple translations if it belongs to multiple parts of speech, while a translation can have
    multiple definitions if the word has multiple meanings within that part of speech.

    See the Definition class docstring for an explanation of the difference between a definition and
    a translation.
    """

    # Class variables
    remove_synonymous_definitions: bool = False

    # Instance variables
    retriever: "Retriever"  # type: ignore  # noqa: F821
    word_to_translate: str
    part_of_speech: str
    definitions: list[Definition]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Translation):
            return NotImplemented
        return (
            self.word_to_translate == other.word_to_translate
            and self.part_of_speech == other.part_of_speech
            and self.definitions == other.definitions
        )

    def __hash__(self) -> int:
        return hash((self.word_to_translate, self.part_of_speech, tuple(self.definitions)))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(word_to_translate={self.word_to_translate}, part_of_speech={self.part_of_speech})"  # noqa: E501

    def __init__(
        self,
        retriever: "Retriever",  # type: ignore  # noqa: F821
        word_to_translate: str,
        part_of_speech: str,
        definitions: list[Definition],
        max_definitions: int = 3,
    ) -> None:
        if not word_to_translate:
            raise ValueError("Word to translate cannot be empty.")
        if not part_of_speech:
            raise ValueError("Part of speech cannot be empty.")
        if not definitions:
            raise ValueError("Definitions cannot be empty.")
        self.retriever = retriever
        self.word_to_translate = word_to_translate
        self.part_of_speech = part_of_speech
        self.definitions = definitions[:max_definitions]
        for definition in self.definitions:
            definition.set_translation(self)
        if self.remove_synonymous_definitions:
            marks = SynonymChecker.mark_synonymous_words(
                [definition.text for definition in self.definitions],
                pos=self.part_of_speech,
            )
            self.definitions = [
                definition for definition, mark in zip(self.definitions, marks) if not mark
            ]

    def stringify(self, verbose: bool = False) -> str:
        s = f"{PC.GREEN}{self.word_to_translate} ({self.part_of_speech}) - {', '.join([definition.text for definition in self.definitions])}{PC.RESET}"  # noqa: E501
        if verbose:
            for definition in self.definitions:
                s += f"\n{definition.stringify(verbose)}"
        return s
