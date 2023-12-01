import argparse
import asyncio
import re
from collections import Counter
from http import HTTPStatus
from typing import List

import aiohttp
import async_lru
from bs4 import BeautifulSoup
from bs4.element import Tag

from consts import Language
from exceptions import RateLimitException
from keywords import EnglishKeyword, Keyword, SpanishKeyword
from sentences import SentencePair, SentencePairCollection, SpanishSentence, EnglishSentence

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
            self.requests_made += 1
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
    For a given sentence div, returns a Keyword object containing the text of the keyword and
    whether the keyword is a verb.
    """
    def find_keyword(self, sentence_div: Tag, verb: bool, language: Language) -> Keyword:
        if language == Language.SPANISH:
            return SpanishKeyword(text=sentence_div.find("strong").text, verb=verb)
        elif language == Language.ENGLISH:
            return EnglishKeyword(text=sentence_div.find("strong").text, verb=verb)
        else:
            raise ValueError(f"Invalid language: {language}")

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
    async def sentence_pairs_from_examples_pane(
        self, spanish_keyword: SpanishKeyword
    ) -> List[SentencePair]:
        url = f"{self.base_url}/examples/{spanish_keyword.text}?lang=es"
        soup = await self._get_soup(url)
        example_rows: List[Tag] = soup.find_all("tr", {"data-testid": "example-row"})
        sentence_pairs = []
        for example in example_rows:
            spanish_sentence_div = example.find("div", {"lang": "es"})
            english_sentence_div = example.find("div", {"lang": "en"})
            spanish_sentence = SpanishSentence(
                text=spanish_sentence_div.text,
                keyword=self.find_keyword(
                    spanish_sentence_div, spanish_keyword.verb, Language.SPANISH
                )
            )
            english_sentence = EnglishSentence(
                text=english_sentence_div.text,
                keyword=self.find_keyword(
                    english_sentence_div, spanish_keyword.verb, Language.ENGLISH
                )
            )
            sentence_pairs.append(SentencePair(spanish_sentence, english_sentence))
        return sentence_pairs

    """
    For a given Spanish word, returns a list of English translations taken from example sentences.
    A maximum of twenty example sentences are considered, and only translations that appear in at
    least five sentences are included in the returned list. If no translations appear in at least
    five sentences, the most common translation is returned.
    """
    async def translate_from_examples(
        self, spanish_keyword: SpanishKeyword
    ) -> List[EnglishKeyword]:
        sentence_pairs = await self.sentence_pairs_from_examples_pane(spanish_keyword)
        sentence_pair_coll = SentencePairCollection(sentence_pairs)
        return sentence_pair_coll.most_common_english_keywords()
    
async def main(spanish_word: str = "hola", verb: bool = False):
    spanish_keyword = SpanishKeyword(text=spanish_word, verb=verb)
    scraper = SpanishDictScraper()

    print(f"Spanish word: {spanish_word}")

    direct_translations = await scraper.direct_translate(spanish_word)
    print(f"Direct translations: {direct_translations}")

    translations_from_examples = await scraper.translate_from_examples(spanish_keyword)
    print(f"Translations from examples: {translations_from_examples}")

    sentence_pairs = await scraper.sentence_pairs_from_examples_pane(spanish_keyword)
    sentence_pair_coll = SentencePairCollection(sentence_pairs)
    most_common_english_keywords = sentence_pair_coll.most_common_english_keywords()
    for english_keyword in most_common_english_keywords:
        filtered_sentence_pairs = sentence_pair_coll.filter_by_english_keyword(english_keyword)
        if not filtered_sentence_pairs:
            continue
        selected_sentence_pair = filtered_sentence_pairs[0]
        print(f"Example Spanish sentence for '{spanish_keyword}' / '{english_keyword}': {selected_sentence_pair.spanish_sentence}")
        print(f"Example English sentence for '{spanish_keyword}' / '{english_keyword}': {selected_sentence_pair.english_sentence}")
    print(f"Requests made: {scraper.requests_made}")
    await scraper.close_session()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate Spanish words to English.")
    parser.add_argument("--word", type=str, help="Spanish word to translate")
    parser.add_argument("--verb", action="store_true", help="Whether the word is a verb")
    args = parser.parse_args()
    args.word = args.word or "hola"

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(spanish_word=args.word, verb=args.verb))
