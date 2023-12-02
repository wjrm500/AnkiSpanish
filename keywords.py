import re
from abc import ABC

from textblob import Word

class Keyword(ABC):
    text: str
    verb: bool

    """
    Standardizes by removing punctuation, whitespace, and capitalization.
    """
    def standardize(self) -> str:
        keyword = re.sub(r"[.,;:!?-]", "", self.text)
        keyword = keyword.strip().lower()
        return Word(keyword).lemmatize("v") if self.verb else keyword

    def __eq__(self, other: "Keyword") -> bool:
        return self.standardize() == other.standardize()
    
    def __hash__(self) -> int:
        return hash(self.standardize())
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(text={self.text}, verb={self.verb})"
    
    def __str__(self) -> str:
        return self.standardize()
    
    def __init__(self, text: str, verb: bool = False) -> None:
        if not text:
            raise ValueError("Text cannot be empty.")
        self.text = text
        self.verb = verb
    
class SpanishKeyword(Keyword):
    pass

class EnglishKeyword(Keyword):
    pass