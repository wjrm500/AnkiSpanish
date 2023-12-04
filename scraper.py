import abc
import argparse
import asyncio
import re
import urllib.parse
from http import HTTPStatus
from typing import List

import aiohttp
import async_lru
from bs4 import BeautifulSoup
from bs4.element import Tag

from exceptions import RateLimitException
from translation import Definition, SentencePair, Translation

"""
An abstract base class for scrapers. Scrapers are used to scrape translation data from a website
to return a list of translations given a word to translate. This class contains some standard
functionality around asynchronous HTTP requests and rate-limiting.
"""
class Scraper(abc.ABC):
    base_url: str
    requests_made = 0

    def __init__(self):
        self.session = None
    
    """
    Returns a BeautifulSoup object from a given URL. The URL is first encoded to ensure that it is
    valid, and the response is checked for rate-limiting. If the response is rate-limited, a
    RateLimitException is raised.
    """
    @async_lru.alru_cache(maxsize=128)
    async def _get_soup(self, url: str) -> BeautifulSoup:
        url = urllib.parse.quote(url, safe=":/?&=")
        if not self.session or self.session.closed:
            await self.start_session()
        async with self.session.get(url) as response:
            self.requests_made += 1
            if response.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise RateLimitException()
            return BeautifulSoup(await response.text(), "html.parser")
    
    """
    Standardizes a given text by removing punctuation, whitespace, and capitalization.
    """
    def _standardize(self, text: str) -> str:
        text = re.sub(r"[.,;:!?-]", "", text)
        return text.strip().lower()

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
    Checks if the scraper is rate-limited by the server.

    This method makes a GET request to the base URL to determine if the response status is
    TOO_MANY_REQUESTS (429), indicating rate-limiting.
    """
    async def rate_limited(self) -> bool:
        if not self.session or self.session.closed:
            await self.start_session()
        async with self.session.get(self.base_url) as response:
            self.requests_made += 1
            return response.status == HTTPStatus.TOO_MANY_REQUESTS
    
    """
    Translates a given word.
    """
    @abc.abstractmethod
    async def translate(self, word_to_translate: str) -> List[Translation]:
        raise NotImplementedError()

"""
A scraper for SpanishDict.com, which translates Spanish words into English by accessing the
dictionary page for the given word, and then creating a separate Translation object for each part of
speech listed in the "Dictionary" pane.
"""
class SpanishDictScraper(Scraper):
    base_url = "https://www.spanishdict.com"

    """
    Returns a Translation object from a given part of speech div. If the part of speech div does not
    contains only "No direct translation" definitions, or only definitions with no complete sentence
    pairs, None is returned.
    """
    def _get_translation_from_part_of_speech_div(
        self, spanish_word: str, part_of_speech_div: Tag
    ) -> Translation | None:
        part_of_speech = part_of_speech_div.find(
            class_=["VlFhSoPR", "L0ywlHB1", "cNX9vGLU", "CDAsok0l", "VEBez1ed"]
        ).find(["a", "span"]).text  # type: ignore
        definition_divs: List[Tag] = part_of_speech_div.find_all(class_="tmBfjszm")
        definitions: List[Definition] = []
        for definition_div in definition_divs:
            signal_tag = definition_div.find("a")
            if not signal_tag:  # E.g., "no direct translation" has no hyperlink
                continue
            text = signal_tag.text
            sentence_pairs = []
            for marker_tag in definition_div.find_all("a"):
                assert isinstance(marker_tag, Tag)
                marker_tag_parent = marker_tag.parent
                marker_tag_grandparent = marker_tag_parent.parent  # type: ignore[union-attr]
                spanish_sentence_span = marker_tag_grandparent.find("span", {"lang": "es"})  # type: ignore[union-attr]
                english_sentence_span = marker_tag_grandparent.find("span", {"lang": "en"})  # type: ignore[union-attr]
                if not spanish_sentence_span or not english_sentence_span:
                    continue
                spanish_sentence = spanish_sentence_span.text
                english_sentence = english_sentence_span.text
                sentence_pair = SentencePair(spanish_sentence, english_sentence)
                sentence_pairs.append(sentence_pair)
            if not sentence_pairs:
                continue
            definition = Definition(text, sentence_pairs)
            definitions.append(definition)
        seen = set()
        unique_definitions = []
        for definition in definitions:
            if definition.text not in seen:
                seen.add(definition.text)
                unique_definitions.append(definition)
        if not unique_definitions:
            return None
        return Translation(spanish_word, part_of_speech, unique_definitions)

    """
    Translates a given Spanish word by accessing the dictionary page for the word, and then creating
    a separate Translation object for each part of speech listed in the "Dictionary" pane.
    """
    async def translate(self, spanish_word: str) -> List[Translation]:
        url = f"{self.base_url}/translate/{self._standardize(spanish_word)}?langFrom=es"
        soup = await self._get_soup(url)
        dictionary_neodict_es_div = soup.find("div", id="dictionary-neodict-es")
        part_of_speech_divs = dictionary_neodict_es_div.find_all(class_="W4_X2sG1")  # type: ignore[union-attr]
        all_translations: List[Translation] = []
        for part_of_speech_div in part_of_speech_divs:
            translation = self._get_translation_from_part_of_speech_div(
                spanish_word, part_of_speech_div
            )
            if translation:
                all_translations.append(translation)
        return all_translations

"""
A demonstration of the SpanishDictScraper class. The Spanish word "hola" is used by default, but
another word can be specified using the spanish_word argument.
"""
async def main(spanish_word: str = "hola"):
    scraper = SpanishDictScraper()

    print(f"Spanish word: {spanish_word}\n")

    translations = await scraper.translate(spanish_word)
    for translation in translations:
        print(translation.stringify(verbose=True))
        print()
    await scraper.close_session()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate Spanish words to English.")
    parser.add_argument("--word", type=str, help="Spanish word to translate")
    args = parser.parse_args()
    args.word = args.word or "hola"

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(spanish_word=args.word))