from typing import List

from consts import PrintColour as PC

def truncate_string(string: str, max_length: int = 20) -> str:
    return string[:max_length] + "..." if len(string) > max_length else string

class SentencePair:
    source_sentence: str
    target_sentence: str

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source_sentence={truncate_string(self.source_sentence)}, english_sentence={truncate_string(self.target_sentence)})"

    def __init__(self, source_sentence: str, target_sentence: str) -> None:
        self.source_sentence = source_sentence
        self.target_sentence = target_sentence

    def stringify(self, verbose: bool = False) -> str:
        return f"{PC.BLUE}{self.source_sentence}{PC.END} - {PC.PURPLE}{self.target_sentence}{PC.END}" if verbose else self.target_sentence
    
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
        s = f"{PC.YELLOW}{self.text}{PC.END}"
        if verbose:
            for sentence_pair in self.sentence_pairs:
                s += f"\n   {sentence_pair.stringify(verbose)}"
        return s
    
class Translation:
    word_to_translate: str
    part_of_speech: str
    definitions: List[Definition]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(word_to_translate={self.word_to_translate}, part_of_speech={self.part_of_speech})"
    
    def __init__(
        self, word_to_translate: str, part_of_speech: str, definitions: List[Definition]
    ) -> None:
        if not word_to_translate:
            raise ValueError("Word to translate cannot be empty.")
        if not part_of_speech:
            raise ValueError("Part of speech cannot be empty.")
        if not definitions:
            raise ValueError("Definitions cannot be empty.")
        self.word_to_translate = word_to_translate
        self.part_of_speech = part_of_speech
        self.definitions = definitions
    
    def stringify(self, verbose: bool = False) -> str:
        s = f"{PC.GREEN}{self.word_to_translate} ({self.part_of_speech}) - {', '.join([definition.text for definition in self.definitions])}{PC.END}"
        if verbose:
            for definition in self.definitions:
                s += f"\n{definition.stringify(verbose)}"
        return s