from typing import Dict, List

from language_element import Translation
from retriever import Retriever


class Dictionary:
    retriever: Retriever
    words: Dict[str, List[Translation]]

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever
        self.words = {}

    async def translate(self, word: str) -> List[Translation]:
        if word not in self.words:
            self.words[word] = await self.retriever.retrieve_translations(word)
        return self.words[word]
