from app.language_element import Translation
from app.retriever import Retriever


class Dictionary:
    """
    A class responsible for providing translations for words. It does this by first checking if it
    already has a translation for a given word, and if not, using a Retriever to retrieve a list of
    translations.
    """

    retriever: Retriever | None
    translations: dict[str, list[Translation]]

    def __init__(self, retriever: Retriever | None = None) -> None:
        self.retriever = retriever
        self.translations = {}

    async def translate(self, word: str) -> list[Translation]:
        """
        Returns a list of Translation objects for a given word. If the word is not already in the
        dictionary, it uses its Retriever (if one is associated) to retrieve a list of translations.
        """
        if word not in self.translations:
            if self.retriever is None:
                return []
            self.translations[word] = await self.retriever.retrieve_translations(word)
        return self.translations[word]
