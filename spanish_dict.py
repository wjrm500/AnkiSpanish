import argparse
import asyncio
import re
from collections import Counter
from http import HTTPStatus
from typing import List, Tuple

import aiohttp
import async_lru
from bs4 import BeautifulSoup
from bs4.element import Tag

from exceptions import RateLimitException

class SpanishDictScraper:
    requests_made = 0

    def __init__(self):
        self.base_url = "https://www.spanishdict.com"
        self.session = None

    """
    Starts an asynchronous HTTP session.
    """
    async def start_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    """
    Closes the asynchronous HTTP session.
    """
    async def close_session(self):
        if self.session:
            await self.session.close()

    """
    Checks if the scraper is rate-limited by the SpanishDict server.

    This method makes a GET request to the base URL of SpanishDict to determine if the response
    status is TOO_MANY_REQUESTS (429), indicating rate-limiting.
    """
    async def rate_limited(self) -> bool:
        if not self.session or self.session.closed:
            await self.start_session()
        async with self.session.get(self.base_url) as response:
            return response.status == HTTPStatus.TOO_MANY_REQUESTS

    """
    Returns a BeautifulSoup object from a given URL.
    """
    async def _get_soup(self, url: str) -> BeautifulSoup:
        if not self.session or self.session.closed:
            await self.start_session()
        async with self.session.get(url) as response:
            self.requests_made += 1
            if response.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise RateLimitException()
            return BeautifulSoup(await response.text(), "html.parser")

    """
    For a given Spanish word, returns a list of English translations taken from the SpanishDict
    dictionary.
    """
    async def direct_translate(self, spanish_word: str) -> List[str]:
        url = f"{self.base_url}/translate/{spanish_word}"
        soup = await self._get_soup(url)
        translation_divs: List[Tag] = soup.find_all("div", id=re.compile(r"quickdef\d+-es"))
        return [div.text for div in translation_divs]
    
    """
    For a given Spanish word, retrieves a list of HTML table row elements from SpanishDict, each
    containing an example Spanish sentence containing the word and the English translation for that
    sentence.
    """
    @async_lru.alru_cache(maxsize=128)
    async def _example_rows(self, spanish_word: str) -> List[Tag]:
        url = f"{self.base_url}/examples/{spanish_word}?lang=es"
        soup = await self._get_soup(url)
        return soup.find_all("tr", {"data-testid": "example-row"})
    
    """
    Standardises a given translation by converting it to lowercase and removing any leading or
    trailing punctuation or whitespace.
    """
    def _standardise_translation(self, translation: str) -> str:
        return translation.lower().strip(".,;:!?")

    """
    For a given Spanish word, returns a list of English translations taken from example sentences.
    A maximum of twenty example sentences are considered, and only translations that appear in at
    least five sentences are included in the returned list. If no translations appear in at least
    five sentences, the most common translation is returned.
    """
    async def example_translate(self, spanish_word: str) -> List[str]:
        example_rows = await self._example_rows(spanish_word)
        translations = []
        for example in example_rows:
            english_sentence = example.find("div", {"lang": "en"})
            if english_sentence:
                strong_tag = english_sentence.find("strong")
                if strong_tag:
                    translations.append(strong_tag.text)
        if not translations:
            return []
        translations = list(map(self._standardise_translation, translations))
        translations_counter = Counter(translations)
        most_common_translations = [x for x, y in translations_counter.items() if y >= 5]
        return most_common_translations or [translations_counter.most_common(1)[0][0]]
    
    """
    For a given Spanish word and English translation, iterates over the sentence examples given for
    the Spanish word by SpanishDict until one is found where the translated word in the English
    sentence equals the English translation inputted into the method, then returns the corresponding
    sentence example as a tuple of the form ("Spanish sentence", "English sentence"). The idea is
    to filter to a sentence example that uses the specific translation of the Spanish word that we
    are interested in.
    """
    async def sentence_example(self, spanish_word: str, english_translation: str) -> Tuple[str, str]:
        example_rows = await self._example_rows(spanish_word)
        for row in example_rows:
            english_sentence = row.find("div", {"lang": "en"})
            if english_sentence:
                strong_tag = english_sentence.find("strong")
                if strong_tag and strong_tag.text == english_translation:
                    spanish_sentence = row.find("div", {"lang": "es"})
                    if spanish_sentence:
                        return spanish_sentence.text, english_sentence.text
        return "", ""

async def main(spanish_word: str = "hola"):
    scraper = SpanishDictScraper()
    direct_translations = await scraper.direct_translate(spanish_word)
    print(f"Direct translations: {direct_translations}")
    example_translations = await scraper.example_translate(spanish_word)
    print(f"Example translations: {example_translations}")
    for example_translation in example_translations:
        spanish_sentence, english_sentence = await scraper.sentence_example(spanish_word, example_translation)
        print(f"Example Spanish sentence for '{spanish_word}' / '{example_translation}': {spanish_sentence}")
        print(f"Example English sentence for '{spanish_word}' / '{example_translation}': {english_sentence}")
    print(f"Requests made: {scraper.requests_made}")
    await scraper.close_session()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate Spanish words to English.")
    parser.add_argument("--word", type=str, help="Spanish word to translate")
    args = parser.parse_args()
    args.word = args.word or "hola"

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(args.word))