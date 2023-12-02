from abc import ABC
from collections import Counter
from typing import List

from keywords import EnglishKeyword, Keyword, SpanishKeyword

class Sentence(ABC):
    text: str
    keyword: Keyword

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(text={self.text}, keyword={self.keyword})"

    def __str__(self) -> str:
        return self.text

    def __init__(self, text: str, keyword: Keyword) -> None:
        if not text:
            raise ValueError("Text cannot be empty.")
        if not keyword:
            raise ValueError("Keyword cannot be empty.")
        self.text = text 
        self.keyword = keyword

class SpanishSentence(Sentence):
    keyword: SpanishKeyword

class EnglishSentence(Sentence):
    keyword: EnglishKeyword

class SentencePair:
    spanish_sentence: SpanishSentence
    english_sentence: EnglishSentence

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(spanish_sentence={self.spanish_sentence}, english_sentence={self.english_sentence})"
    
    def __str__(self) -> str:
        return f"{self.spanish_sentence}\n{self.english_sentence}"

    def __init__(
        self, spanish_sentence: SpanishSentence, english_sentence: EnglishSentence
    ) -> None:
        self.spanish_sentence = spanish_sentence
        self.english_sentence = english_sentence

class SentencePairCollection:
    english_keywords: List[EnglishKeyword]
    english_keyword_counter: Counter
    sentence_pairs: List[SentencePair]

    def __init__(self, sentence_pairs: List[SentencePair]) -> None:
        self.sentence_pairs = sentence_pairs
        self.english_keywords = [pair.english_sentence.keyword for pair in self.sentence_pairs]
        self.english_keyword_counter = Counter(self.english_keywords)
    
    def _most_common_english_keyword(self) -> EnglishKeyword:
        return self.english_keyword_counter.most_common(1)[0][0]
    
    def most_common_english_keywords(self, min_count: int = 5) -> List[EnglishKeyword]:
        keywords = [
            keyword
            for keyword, count in self.english_keyword_counter.most_common()
            if count >= min_count
        ]
        return keywords or [self._most_common_english_keyword()]
    
    def filter_by_english_keyword(self, english_keyword: EnglishKeyword) -> List[SentencePair]:
        return [
            pair for pair in self.sentence_pairs if pair.english_sentence.keyword == english_keyword
        ]