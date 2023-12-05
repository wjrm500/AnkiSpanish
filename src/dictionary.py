from typing import Dict, List

from language_element import Translation
from retriever import Retriever


class Dictionary:
    """
    A class responsible for providing translations for words. It does this by first checking if it
    already has a translation for a given word, and if not, using a Retriever to retrieve a list of
    translations.
    """

    retriever: Retriever | None
    words: Dict[str, List[Translation]]

    def __init__(self, retriever: Retriever | None = None) -> None:
        self.retriever = retriever
        self.words = {}

    """
    Returns a list of Translation objects for a given word. If the word is not already in the
    dictionary, it uses the Retriever to retrieve a list of translations.
    """
    async def translate(self, word: str) -> List[Translation]:
        if word not in self.words:
            if self.retriever is None:
                return []
            self.words[word] = await self.retriever.retrieve_translations(word)
        return self.words[word]
