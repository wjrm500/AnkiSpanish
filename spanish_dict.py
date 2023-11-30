import argparse
from collections import Counter
from typing import List

from bs4 import BeautifulSoup
from bs4.element import Tag
import requests

class SpanishDictScraper:
    def __init__(self):
        self.base_url = "https://www.spanishdict.com"

    def direct_translate(self, spanish_word: str) -> List[str]:
        url = f"{self.base_url}/translate/{spanish_word}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        translation_div = soup.find("div", id="quickdef1-es")
        if translation_div:
            return translation_div.text.split(",")
        return []

    def _translations_from_examples(self, spanish_word: str) -> List[str]:
        url = f"{self.base_url}/examples/{spanish_word}?lang=es"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        examples: List[Tag] = soup.find_all("tr", {"data-testid": "example-row"})
        translations = []
        for example in examples:
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
    print("Direct translate: ", scraper.direct_translate(args.word))
    print("Example translate: ", scraper.example_translate(args.word))