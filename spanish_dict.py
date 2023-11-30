import argparse
import re
from collections import Counter
from functools import lru_cache
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

class SpanishDictScraper:
    requests_made = 0

    def __init__(self):
        self.base_url = "https://www.spanishdict.com"

    """
    Returns a BeautifulSoup object from a given URL.
    """
    def _get_soup(self, url: str) -> BeautifulSoup:
        response = requests.get(url)
        self.requests_made += 1
        return BeautifulSoup(response.text, "html.parser")

    """
    For a given Spanish word, returns a list of English translations taken from the dictionary.
    """
    def direct_translate(self, spanish_word: str) -> List[str]:
        url = f"{self.base_url}/translate/{spanish_word}"
        soup = self._get_soup(url)
        translation_divs: List[Tag] = soup.find_all("div", id=re.compile(r"quickdef\d+-es"))
        return [div.text for div in translation_divs]
    
    """
    Retrieves a list of HTML table row elements from SpanishDict, each containing an example
    sentence in Spanish and its English translation for the given Spanish word.
    """
    @lru_cache(maxsize=64)
    def _example_rows(self, spanish_word: str) -> List[Tag]:
        url = f"{self.base_url}/examples/{spanish_word}?lang=es"
        soup = self._get_soup(url)
        return soup.find_all("tr", {"data-testid": "example-row"})

    """
    Extracts English translations from the example sentences obtained for a given Spanish word.
    The method focuses on the part of the English sentences that directly corresponds to the
    Spanish word, highlighted in bold in the source.
    """
    def _translations_from_examples(self, spanish_word: str) -> List[str]:
        translations = []
        for example in self._example_rows(spanish_word):
            english_sentence = example.find("div", {"lang": "en"})
            if english_sentence:
                strong_tag = english_sentence.find("strong")
                if strong_tag:
                    translations.append(strong_tag.text)
        return translations
    
    """
    Standardises a given translation by converting it to lowercase and removing any leading or trailing
    punctuation or whitespace.
    """
    def _standardise_translation(self, translation: str) -> str:
        return translation.lower().strip(".,;:!?")

    """
    For a given Spanish word, returns a list of English translations taken from example sentences.
    A maximum of twenty example sentences are used, and only translations that appear at least five
    times are included in the returned list. If no translations appear at least five times, the most
    common translation is returned.
    """
    def example_translate(self, spanish_word: str) -> List[str]:
        translations = self._translations_from_examples(spanish_word)
        if not translations:
            return []
        translations = list(map(self._standardise_translation, translations))
        translations_counter = Counter(translations)
        most_common_translations = [x for x, y in translations_counter.items() if y >= 5]
        return most_common_translations or [translations_counter.most_common()[0][0]]
    
    """
    For a given spanish_word and english_translation, iterates over the Spanish / English sentence
    translation examples given by SpanishDict for spanish_word until one is found where the keyword
    of the English sentence translation equals english_translation, then returns the Spanish and
    English sentences as a tuple of the form ("Spanish sentence", "English sentence").
    """
    def sentence_example(self, spanish_word: str, english_translation: str) -> Tuple[str, str]:
        example_rows = self._example_rows(spanish_word)
        for row in example_rows:
            english_sentence = row.find("div", {"lang": "en"})
            if english_sentence:
                strong_tag = english_sentence.find("strong")
                if strong_tag and strong_tag.text == english_translation:
                    spanish_sentence = row.find("div", {"lang": "es"})
                    if spanish_sentence:
                        return spanish_sentence.text, english_sentence.text
        return "", ""
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate Spanish words to English.")
    parser.add_argument("--word", type=str, help="Spanish word to translate")
    args = parser.parse_args()
    args.word = args.word or "hola"

    print(f"Translating '{args.word}'...")
    scraper = SpanishDictScraper()
    print(f"Direct translations: {scraper.direct_translate(args.word)}")
    example_translations = scraper.example_translate(args.word)
    print(f"Example translations: {example_translations}")
    for example_translation in example_translations:
        spanish_sentence, english_sentence = scraper.sentence_example(args.word, example_translation)
        print(f"Example Spanish sentence for '{args.word}' / '{example_translation}': {spanish_sentence}")
        print(f"Example English sentence for '{args.word}' / '{example_translation}': {english_sentence}")
    print(f"Requests made: {scraper.requests_made}")