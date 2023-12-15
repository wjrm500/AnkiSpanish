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

    def lang_from_url(self, word_to_translate: str) -> str | None:
        """Returns a hyperlink to the dictionary page for the word to translate."""
        return None

    def lang_to_url(self, word_to_translate: str) -> str | None:
        """Returns a hyperlink to the dictionary page for the translation."""
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
            CollinsSpanishWebsiteScraper,
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
    lang_from_mapping = {
        Language.ENGLISH: "en",
        Language.SPANISH: "es",
    }
    lookup_key = "spanishdict"

    def lang_from_url(self, word_to_translate: str) -> str | None:
        lang_from = self.lang_from_mapping[self.language_from]
        return f"{self.base_url}/translate/{self._standardize(word_to_translate)}?langFrom={lang_from}"  # noqa: E501

    def lang_to_url(self, word_to_translate: str) -> str | None:
        lang_to = self.lang_from_mapping[self.language_to]
        return (
            f"{self.base_url}/translate/{self._standardize(word_to_translate)}?langFrom={lang_to}"
        )

    def _get_translation_from_part_of_speech_div(
        self, word_to_translate: str, part_of_speech_div: Tag
    ) -> Translation | None:
        """
        Returns a Translation object from a given part of speech div. If the part of speech div does
        not contains only "No direct translation" definitions, or only definitions with no complete
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
                    "span", {"lang": self.lang_from_mapping[self.language_from]}
                )
                target_sentence_span = marker_tag_grandparent.find(  # type: ignore[union-attr]
                    "span", {"lang": self.lang_from_mapping[self.language_to]}
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
        seen = set()
        unique_definitions = []
        for definition in definitions:
            if definition.text not in seen:
                seen.add(definition.text)
                unique_definitions.append(definition)
        if not unique_definitions:
            return None
        return Translation(self, word_to_translate, part_of_speech, unique_definitions)

    async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
        """
        Retrieves translations for a given word by accessing the dictionary page for the word, and
        then creating a separate Translation object for each part of speech listed in the
        "Dictionary" pane.
        """
        lang_from = self.lang_from_mapping[self.language_from]
        try:
            soup = await self._get_soup(self.lang_from_url(word_to_translate))
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


class CollinsSpanishWebsiteScraper(WebsiteScraper):
    available_language_pairs: list[tuple[Language, Language]] = [
        (Language.ENGLISH, Language.SPANISH),
        (Language.SPANISH, Language.ENGLISH),
    ]
    base_url = "https://www.collinsdictionary.com/dictionary/spanish-english"
    lookup_key = "collinsspanish"

    async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
        # TODO: Implement
        return []


async def main(word_to_translate: str = "hola", retriever_type: str = "spanishdict") -> None:
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
