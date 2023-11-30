import argparse
from collections import Counter
from functools import lru_cache
from typing import List, Tuple

from bs4 import BeautifulSoup
from bs4.element import Tag
import requests

class SpanishDictScraper:
    requests_made = 0

    def __init__(self):
        self.base_url = "https://www.spanishdict.com"

    def _get_soup(self, url: str) -> BeautifulSoup:
        response = requests.get(url)
        self.requests_made += 1
        return BeautifulSoup(response.text, "html.parser")

    def direct_translate(self, spanish_word: str) -> List[str]:
        url = f"{self.base_url}/translate/{spanish_word}"
        soup = self._get_soup(url)
        translation_div = soup.find("div", id="quickdef1-es")
        if translation_div:
            return translation_div.text.split(",")
        return []
    
    @lru_cache(maxsize=64)
    def _example_rows(self, spanish_word: str) -> List[Tag]:
        url = f"{self.base_url}/examples/{spanish_word}?lang=es"
        soup = self._get_soup(url)
        return soup.find_all("tr", {"data-testid": "example-row"})

    def _translations_from_examples(self, spanish_word: str) -> List[str]:
        translations = []
        for example in self._example_rows(spanish_word):
            english_sentence = example.find("div", {"lang": "en"})
            if english_sentence:
                strong_tag = english_sentence.find("strong")
                if strong_tag:
                    translations.append(strong_tag.text)
        return translations
    
    def _standardise_word(self, word: str) -> str:
        return word.lower().strip("., ")

    def example_translate(self, spanish_word: str) -> List[str]:
        examples = self._translations_from_examples(spanish_word)
        words = " ".join(examples).split()
        words = list(map(self._standardise_word, words))
        words_counter = Counter(words)
        most_common_words = [x for x, y in words_counter.items() if y >= 5]
        return most_common_words or [words_counter.most_common()[0][0]]
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate Spanish words to English.")
    parser.add_argument("--word", type=str, help="Spanish word to translate", required=True)
    args = parser.parse_args()

    scraper = SpanishDictScraper()
    print(f"Direct translations: {scraper.direct_translate(args.word)}")
    example_translations = scraper.example_translate(args.word)
    print(f"Example translations: {example_translations}")
    print(f"Requests made: {scraper.requests_made}")