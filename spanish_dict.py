import argparse
import asyncio
import re
import urllib.parse
from collections import Counter
from http import HTTPStatus
from typing import Callable, List, Tuple

import aiohttp
import async_lru
from bs4 import BeautifulSoup
from bs4.element import Tag


from exceptions import RateLimitException
from sentences import Keyword, SentencePair, SpanishSentence, EnglishSentence

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
    async def _example_sentence_pairs_from_examples_pane(
        self, spanish_keyword: Keyword
    ) -> List[SentencePair]:
        url = f"{self.base_url}/examples/{spanish_keyword.text}?lang=es"
        # url = urllib.parse.quote(url)
        soup = await self._get_soup(url)
        example_rows: List[Tag] = soup.find_all("tr", {"data-testid": "example-row"})
        def find_keyword(sentence_div: Tag) -> Keyword:
            return Keyword(text=sentence_div.find("strong").text, verb=spanish_keyword.verb)
        sentence_pairs = []
        for example in example_rows:
            spanish_sentence_div = example.find("div", {"lang": "es"})
            english_sentence_div = example.find("div", {"lang": "en"})
            spanish_sentence = SpanishSentence(
                text=spanish_sentence_div.text, keyword=find_keyword(spanish_sentence_div)
            )
            english_sentence = EnglishSentence(
                text=english_sentence_div.text, keyword=find_keyword(english_sentence_div)
            )
            sentence_pairs.append(SentencePair(spanish_sentence, english_sentence))
        return sentence_pairs
    
    """
    For a given Spanish word, returns a list of English translations taken from example sentences.
    A maximum of twenty example sentences are considered, and only translations that appear in at
    least five sentences are included in the returned list. If no translations appear in at least
    five sentences, the most common translation is returned.
    """
    async def example_translate(self, spanish_keyword: Keyword) -> List[Keyword]:
        example_sentence_pairs = await self._example_sentence_pairs_from_examples_pane(
            spanish_keyword
        )
        english_keywords = [pair.english_sentence.keyword for pair in example_sentence_pairs]
        if not english_keywords:
            return []
        english_keywords_counter = Counter(english_keywords)
        most_common_english_keywords = [x for x, y in english_keywords_counter.items() if y >= 5]
        return most_common_english_keywords or [english_keywords_counter.most_common(1)[0][0]]
    
    """
    For a given Spanish word and English translation, iterates over the sentence examples given for
    the Spanish word by SpanishDict until one is found where the translated word in the English
    sentence equals the English translation inputted into the method, then returns the corresponding
    sentence example as a tuple of the form ("Spanish sentence", "English sentence"). The idea is
    to filter to a sentence example that uses the specific translation of the Spanish word that we
    are interested in.
    """
    async def example_sentence_pair_for_specific_keywords(
        self, spanish_keyword: Keyword, english_keyword: Keyword
    ) -> SentencePair | None:
        example_sentence_pairs = await self._example_sentence_pairs_from_examples_pane(
            spanish_keyword
        )
        for example_sentence_pair in example_sentence_pairs:
            english_sentence = example_sentence_pair.english_sentence
            if english_sentence.keyword == english_keyword:
                return example_sentence_pair
        return None

async def main(spanish_word: str = "hola", verb: bool = False):
    spanish_keyword = Keyword(text=spanish_word, verb=verb)
    scraper = SpanishDictScraper()
    direct_translations = await scraper.direct_translate(spanish_word)
    print(f"Direct translations: {direct_translations}")
    english_keywords = await scraper.example_translate(spanish_keyword)
    print(f"Example translations: {english_keywords}")
    for english_keyword in english_keywords:
        sentence_pair = await scraper.example_sentence_pair_for_specific_keywords(
            spanish_keyword, english_keyword
        )
        print(f"Example Spanish sentence for '{spanish_keyword}' / '{english_keyword}': {sentence_pair.spanish_sentence}")
        print(f"Example English sentence for '{spanish_keyword}' / '{english_keyword}': {sentence_pair.english_sentence}")
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
