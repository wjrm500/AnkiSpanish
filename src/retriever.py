import abc
import argparse
import asyncio
import json
import os
import re
import urllib.parse
from http import HTTPStatus
from typing import Any

import aiohttp
import async_lru
from bs4 import BeautifulSoup
from bs4.element import Tag
from dotenv import load_dotenv
from openai import AsyncOpenAI

from constant import OPEN_AI_SYSTEM_PROMPT, Language, OpenAIModel
from exception import RateLimitException
from language_element import Definition, SentencePair, Translation


class Retriever(abc.ABC):
    """
    An abstract base class for retrievers. Retriever objects are given a word to translate and
    access the Web in some way to retrieve translation data for that word, then format that data
    into a standardised representation.
    """

    available_language_pairs: list[tuple[Language, Language]] = []
    base_url: str
    concise_mode: bool = False
    language_from: Language
    language_to: Language
    lookup_key: str
    requests_made: int = 0
    session: aiohttp.ClientSession | None = None

    def __init__(self, language_from: Language, language_to: Language) -> None:
        self.language_from = language_from
        self.language_to = language_to
        if (self.language_from, self.language_to) not in self.available_language_pairs:
            raise ValueError(
                f"Language pair {self.language_from.value} -> {self.language_to.value} not supported by the {self.__class__.__name__} retriever"  # noqa: E501
            )

    async def start_session(self) -> None:
        """Starts an asynchronous HTTP session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close_session(self) -> None:
        """Closes the asynchronous HTTP session."""
        if self.session:
            await self.session.close()

    async def rate_limited(self) -> bool:
        """
        Checks if the retriever is rate-limited by the server.

        This method makes a GET request to the base URL to determine if the response status is
        TOO_MANY_REQUESTS (429), indicating rate-limiting.
        """
        if not self.session or self.session.closed:
            await self.start_session()
        assert self.session
        async with self.session.get(self.base_url) as response:
            self.requests_made += 1
            return response.status == HTTPStatus.TOO_MANY_REQUESTS

    def link(self, word_to_translate: str) -> str | None:
        """Returns a hyperlink to a page showing more information for the word to translate."""
        return None

    def reverse_link(self, definition: str) -> str | None:
        """Returns a hyperlink to a page showing more information for the translated definition."""
        return None

    @staticmethod
    def _standardize(text: str) -> str:
        """Standardizes a given string by removing punctuation, whitespace, and capitalization."""
        text = re.sub(r"[.,;:!?-]", "", text)
        return text.strip().lower()

    @abc.abstractmethod
    async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
        """Retrieves translations for a given word."""
        raise NotImplementedError()


class RetrieverFactory:
    @staticmethod
    def create_retriever(
        retriever_type: str, language_from: Language, language_to: Language
    ) -> Retriever:
        retrievers: list[type[Retriever]] = [
            CollinsWebsiteScraper,
            OpenAIAPIRetriever,
            SpanishDictWebsiteScraper,
        ]
        for retriever in retrievers:
            if retriever.lookup_key == retriever_type:
                return retriever(language_from, language_to)
        raise ValueError(f"Unknown retriever type: {retriever_type}")


class WebsiteScraper(Retriever, abc.ABC):
    """
    An abstract class for website scrapers. WebsiteScraper objects are retrievers that specifically
    parse HTML responses.
    """

    @async_lru.alru_cache(maxsize=128)
    async def _get_soup(self, url: str) -> BeautifulSoup:
        """
        Returns a BeautifulSoup object from a given URL. The URL is first encoded to ensure that it
        is valid, and the response is checked for rate-limiting. If the response is rate-limited, a
        RateLimitException is raised.
        """
        url = urllib.parse.quote(url, safe=":/?&=")
        if not self.session or self.session.closed:
            await self.start_session()
        assert self.session
        async with self.session.get(url) as response:
            self.requests_made += 1
            if response.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise RateLimitException()
            if (response_url := str(response.url)) != url:
                raise ValueError(f"URL redirected from {url} to {response_url}")
            return BeautifulSoup(await response.text(), "html.parser")


class APIRetriever(Retriever, abc.ABC):
    api_key: str | None = None


class OpenAIAPIRetriever(APIRetriever):
    available_language_pairs: list[tuple[Language, Language]] = [
        (Language.ENGLISH, Language.SPANISH),
        (Language.SPANISH, Language.ENGLISH),
    ]
    client: AsyncOpenAI
    lookup_key = "openai"
    model: OpenAIModel | None = None

    def __init__(self, language_from: Language, language_to: Language) -> None:
        super().__init__(language_from=language_from, language_to=language_to)
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key)

    def set_language_from(self) -> None:
        """
        Get language from user - done via command line for now to keep things simple
        """
        while True:
            try:
                self.language_from = Language(
                    input(
                        f"Enter the language of the words being translated. Options are: {', '.join(Language.options())}\n"  # noqa: E501
                    )
                )
                break
            except ValueError:
                print("Invalid language, please try again.")

    def set_model(self) -> None:
        """
        Get model from user - done via command line for now to keep things simple
        """
        while True:
            try:
                self.model = OpenAIModel(
                    input(
                        f"Enter the model to use for translation. Options are: {', '.join(OpenAIModel.options())}\n"  # noqa: E501
                    )
                )
                break
            except ValueError:
                print("Invalid model, please try again.")

    async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
        if not self.language_from:
            self.set_language_from()
        if not self.model:
            self.set_model()
        assert self.language_from
        assert self.model
        response = await self.client.chat.completions.create(
            model=self.model.value,
            messages=[
                {"role": "system", "content": OPEN_AI_SYSTEM_PROMPT},
                {"role": "user", "content": f"{self.language_from.value}: {word_to_translate}"},
            ],
        )
        self.requests_made += 1
        if not (content := response.choices[0].message.content):
            return []
        response_json: dict[str, Any] = json.loads(content)
        translation_dicts = response_json["translations"]
        translations = []
        for translation_dict in translation_dicts:
            definitions = []
            for definition_dict in translation_dict["definitions"]:
                sentence_pairs = []
                for sentence_pair_dict in definition_dict["sentence_pairs"]:
                    sentence_pair = SentencePair(
                        sentence_pair_dict["source_sentence"], sentence_pair_dict["target_sentence"]
                    )
                    sentence_pairs.append(sentence_pair)
                definition = Definition(definition_dict["text"], sentence_pairs)
                definitions.append(definition)
            translation = Translation(
                self,
                translation_dict["word_to_translate"],
                translation_dict["part_of_speech"],
                definitions,
            )
            translations.append(translation)
        return translations


class SpanishDictWebsiteScraper(WebsiteScraper):
    """
    A website scraper for SpanishDict.com, which retrieves English translations for a Spanish word
    by searching the online dictionary for the Spanish word.
    """

    available_language_pairs: list[tuple[Language, Language]] = [
        (Language.ENGLISH, Language.SPANISH),
        (Language.SPANISH, Language.ENGLISH),
    ]
    base_url: str = "https://www.spanishdict.com"
    lang_shortener = {
        Language.ENGLISH: "en",
        Language.SPANISH: "es",
    }
    lookup_key = "spanishdict"

    def link(self, word_to_translate: str) -> str | None:
        return f"{self.base_url}/translate/{self._standardize(word_to_translate)}?langFrom={self.lang_shortener[self.language_from]}"  # noqa: E501

    def reverse_link(self, definition: str) -> str | None:
        return f"{self.base_url}/translate/{self._standardize(definition)}?langFrom={self.lang_shortener[self.language_to]}"  # noqa: E501

    def _get_translation_from_part_of_speech_div(
        self, word_to_translate: str, part_of_speech_div: Tag
    ) -> Translation | None:
        """
        Returns a Translation object from a given part of speech div. If the part of speech div
        contains only "No direct translation" definitions, or only definitions with no complete
        sentence pairs, None is returned.
        """
        part_of_speech = (
            part_of_speech_div.find(
                class_=["VlFhSoPR", "L0ywlHB1", "cNX9vGLU", "CDAsok0l", "VEBez1ed"]
            )  # type: ignore
            .find(["a", "span"])  # type: ignore
            .text
        )
        definition_divs: list[Tag] = part_of_speech_div.find_all(class_="tmBfjszm")
        definitions: list[Definition] = []
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
                source_sentence_span = marker_tag_grandparent.find(  # type: ignore[union-attr]
                    "span", {"lang": self.lang_shortener[self.language_from]}
                )
                target_sentence_span = marker_tag_grandparent.find(  # type: ignore[union-attr]
                    "span", {"lang": self.lang_shortener[self.language_to]}
                )
                if not source_sentence_span or not target_sentence_span:
                    continue
                source_sentence = source_sentence_span.text
                target_sentence = target_sentence_span.text
                sentence_pair = SentencePair(source_sentence, target_sentence)
                sentence_pairs.append(sentence_pair)
            if not sentence_pairs:
                continue
            definition = Definition(text, sentence_pairs)
            definitions.append(definition)
        if not definitions:
            return None
        return Translation(self, word_to_translate, part_of_speech, definitions)

    async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
        """
        Retrieves translations for a given word by accessing the dictionary page for the word, and
        then creating a separate Translation object for each part of speech listed in the
        "Dictionary" pane.
        """
        lang_from = self.lang_shortener[self.language_from]
        try:
            soup = await self._get_soup(self.link(word_to_translate))
        except ValueError:
            raise ValueError(
                f"URL redirect occurred for '{word_to_translate}' - are you sure it is a valid {self.language_from.value.title()} word?"  # noqa: E501
            )
        dictionary_neodict_div = soup.find("div", id=f"dictionary-neodict-{lang_from}")
        if not dictionary_neodict_div:
            raise ValueError(
                f"Could not parse translation data for '{word_to_translate}' - are you sure it is a valid {self.language_from.value.title()} word?"  # noqa: E501
            )
        part_of_speech_divs = dictionary_neodict_div.find_all(  # type: ignore[union-attr]
            class_="W4_X2sG1"
        )
        all_translations: list[Translation] = []
        for part_of_speech_div in part_of_speech_divs:
            translation = self._get_translation_from_part_of_speech_div(
                word_to_translate, part_of_speech_div
            )
            if translation:
                all_translations.append(translation)
        if self.concise_mode:
            quickdef_divs: list[Tag] = soup.find_all(
                id=lambda x: x and x.startswith("quickdef") and x.endswith(lang_from)
            )
            quickdefs = [(a.text if (a := d.find("a")) else d.text) for d in quickdef_divs]
            quickdef_translations: set[Translation] = set()
            for quickdef in quickdefs:
                for translation in all_translations:
                    if quickdef in (d.text for d in translation.definitions):
                        quickdef_translations.add(translation)
                        break
            for quickdef_translation in quickdef_translations:
                quickdef_translation.definitions = [
                    d for d in quickdef_translation.definitions if d.text in quickdefs
                ]
            all_translations = list(quickdef_translations)
        return all_translations


class CollinsWebsiteScraper(WebsiteScraper):
    available_language_pairs: list[tuple[Language, Language]] = [
        (Language.ENGLISH, Language.FRENCH),
        (Language.ENGLISH, Language.GERMAN),
        (Language.ENGLISH, Language.ITALIAN),
        (Language.ENGLISH, Language.PORTUGUESE),
        (Language.ENGLISH, Language.SPANISH),
        (Language.FRENCH, Language.ENGLISH),
        (Language.GERMAN, Language.ENGLISH),
        (Language.ITALIAN, Language.ENGLISH),
        (Language.PORTUGUESE, Language.ENGLISH),
        (Language.SPANISH, Language.ENGLISH),
    ]
    base_url = "https://www.collinsdictionary.com/dictionary"
    lookup_key = "collins"

    def link(self, word_to_translate: str) -> str | None:
        return f"{self.base_url}/{self.language_from.value}-{self.language_to.value}/{self._standardize(word_to_translate)}"  # noqa: E501

    def reverse_link(self, definition: str) -> str | None:
        return f"{self.base_url}/{self.language_to.value}-{self.language_from.value}/{self._standardize(definition)}"  # noqa: E501

    def _get_translation_from_part_of_speech_div(
        self, word_to_translate: str, part_of_speech_div: Tag
    ) -> Translation | None:
        part_of_speech = part_of_speech_div.find(class_=["hi", "rend-sc", "pos"]).text  # type: ignore[union-attr]  # noqa: E501
        definition_divs: list[Tag] = part_of_speech_div.find_all("div", class_="sense")
        definitions: list[Definition] = []
        for definition_div in definition_divs:
            text = definition_div.find(class_=["quote", "ref"]).text  # type: ignore[union-attr]
            sentence_pairs = []
            example_divs: list[Tag] = definition_div.find_all(class_=["cit", "type-example"])
            for example_div in example_divs:
                quotes: list[Tag] = example_div.find_all(class_=["quote"])
                if len(quotes) != 2:
                    continue
                source_sentence = quotes[0].text
                target_sentence = quotes[1].text
                sentence_pair = SentencePair(source_sentence, target_sentence)
                sentence_pairs.append(sentence_pair)
            if not sentence_pairs:
                continue
            definition = Definition(text, sentence_pairs)
            definitions.append(definition)
        if not definitions:
            return None
        return Translation(self, word_to_translate, part_of_speech, definitions)

    async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
        soup = await self._get_soup(self.link(word_to_translate))
        if soup.text.find("Enable JavaScript and cookies to continue") != -1:
            raise ValueError(
                "Collins online Spanish dictionary remains scrape-resistant, owing to Cloudflare's anti-bot protection"  # noqa: E501
            )
        part_of_speech_divs = soup.find_all("div", class_="hom")
        all_translations: list[Translation] = []
        for part_of_speech_div in part_of_speech_divs:
            translation = self._get_translation_from_part_of_speech_div(
                word_to_translate, part_of_speech_div
            )
            if translation:
                all_translations.append(translation)
        return all_translations


class WordReferenceWebsiteScraper(WebsiteScraper):
    """
    WORK IN PROGRESS - NOT YET FUNCTIONAL
    """

    available_language_pairs: list[tuple[Language, Language]] = [
        (Language.ENGLISH, Language.FRENCH),
        (Language.ENGLISH, Language.GERMAN),
        (Language.ENGLISH, Language.ITALIAN),
        (Language.ENGLISH, Language.PORTUGUESE),
        (Language.ENGLISH, Language.SPANISH),
        (Language.FRENCH, Language.ENGLISH),
        (Language.FRENCH, Language.SPANISH),
        (Language.GERMAN, Language.ENGLISH),
        (Language.GERMAN, Language.SPANISH),
        (Language.ITALIAN, Language.ENGLISH),
        (Language.ITALIAN, Language.SPANISH),
        (Language.PORTUGUESE, Language.ENGLISH),
        (Language.PORTUGUESE, Language.SPANISH),
        (Language.SPANISH, Language.ENGLISH),
        (Language.SPANISH, Language.FRENCH),
        (Language.SPANISH, Language.GERMAN),
        (Language.SPANISH, Language.ITALIAN),
        (Language.SPANISH, Language.PORTUGUESE),
    ]
    base_url = "https://www.wordreference.com"
    lang_shortener = {
        Language.ENGLISH: "en",
        Language.FRENCH: "fr",
        Language.GERMAN: "de",
        Language.ITALIAN: "it",
        Language.PORTUGUESE: "pt",
        Language.SPANISH: "es",
    }
    lookup_key = "wordreference"

    def link(self, word_to_translate: str) -> str | None:
        if (self.language_from, self.language_to) == (Language.ENGLISH, Language.SPANISH):
            return f"{self.base_url}/es/translation.asp?tranword={self._standardize(word_to_translate)}"  # noqa: E501
        elif (self.language_from, self.language_to) == (Language.SPANISH, Language.ENGLISH):
            return (
                f"{self.base_url}/es/en/translation.asp?spen={self._standardize(word_to_translate)}"
            )
        return f"{self.base_url}/{self.lang_shortener[self.language_from]}{self.lang_shortener[self.language_to]}/{self._standardize(word_to_translate)}"  # noqa: E501

    def reverse_link(self, definition: str) -> str | None:
        if (self.language_from, self.language_to) == (Language.ENGLISH, Language.SPANISH):
            return f"{self.base_url}/es/en/translation.asp?spen={self._standardize(definition)}"
        elif (self.language_from, self.language_to) == (Language.SPANISH, Language.ENGLISH):
            return f"{self.base_url}/es/translation.asp?tranword={self._standardize(definition)}"
        return f"{self.base_url}/{self.lang_shortener[self.language_from]}{self.lang_shortener[self.language_to]}/{self._standardize(definition)}"  # noqa: E501

    async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
        soup = await self._get_soup(self.link(word_to_translate))
        from_word_divs: list[Tag] = soup.find_all("td", class_="FrWrd")[
            1:
        ]  # First instance is header with language name
        word_to_translate = self._standardize(from_word_divs[0].contents[0].contents[0].contents[0])
        to_word_divs: list[Tag] = soup.find_all("td", class_="ToWrd")[
            1:
        ]  # First instance is header with language name
        example_divs: list[Tag] = soup.find_all("td", class_=["ToEx", "FrEx"])
        to_example_divs, from_example_divs = [], []
        current_class = None
        for example_div in example_divs[:]:
            new_class = example_div["class"][0]
            if new_class == current_class:
                continue
            if new_class == "ToEx":
                to_example_divs.append(example_div)
            elif new_class == "FrEx":
                from_example_divs.append(example_div)
            current_class = new_class
        zipped = zip(from_word_divs, to_word_divs, from_example_divs, to_example_divs)
        pos_dict: dict[str, tuple[list[Tag]]] = {}
        for frwrd_div, towrd_div, frex_div, toex_div in zipped:
            if not (found_em := frwrd_div.find("em")):
                break
            part_of_speech = found_em.text.split(",")[0]
            if part_of_speech not in pos_dict:
                pos_dict[part_of_speech] = {
                    "towrd_divs": [],
                    "frex_divs": [],
                    "toex_divs": [],
                }
            pos_dict[part_of_speech]["towrd_divs"].append(towrd_div)
            pos_dict[part_of_speech]["frex_divs"].append(frex_div)
            pos_dict[part_of_speech]["toex_divs"].append(toex_div)
        translations: list[Translation] = []
        for part_of_speech, div_dict in pos_dict.items():
            definition_dict: dict[str, Definition] = {}
            for towrd_div, frex_div, toex_div in zip(
                div_dict["towrd_divs"], div_dict["frex_divs"], div_dict["toex_divs"]
            ):
                definition_text = self._standardize(towrd_div.contents[0].strip().split(",")[0])
                if definition_text not in definition_dict:
                    definition = Definition(
                        definition_text, [SentencePair(frex_div.text, toex_div.text)]
                    )
                    definition_dict[definition_text] = definition
                    if self.concise_mode:
                        break
                else:
                    definition = definition_dict[definition_text]
                    definition.sentence_pairs.append(SentencePair(frex_div.text, toex_div.text))
            translation = Translation(
                self,
                word_to_translate,
                part_of_speech,
                list(definition_dict.values()),
            )
            translations.append(translation)
            if self.concise_mode:
                break
        return translations


async def main(
    word_to_translate: str = "hola", retriever_type: str = SpanishDictWebsiteScraper.lookup_key
) -> None:
    """
    A demonstration of the SpanishDictWebsiteScraper class. The Spanish word "hola" is used by
    default, but another word can be specified using the spanish_word argument.
    """
    print(f"Word to translate: {word_to_translate}\n")
    retriever = RetrieverFactory.create_retriever(
        retriever_type, Language.ENGLISH, Language.SPANISH
    )
    translations = await retriever.retrieve_translations(word_to_translate)
    for translation in translations:
        print(translation.stringify(verbose=True))
        print()
    await retriever.close_session()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate words by scraping online dictionaries.")
    parser.add_argument("--word", type=str, default="hola", help="Word to translate")
    parser.add_argument(
        "--retriever-type", type=str, default="spanishdict", help="Retriever type to use"
    )
    args = parser.parse_args()
    asyncio.run(main(args.word, args.retriever_type))
