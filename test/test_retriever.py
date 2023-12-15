import json
import os
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup

from constant import Language, OpenAIModel
from language_element import Definition, SentencePair, Translation
from retriever import (
    CollinsWebsiteScraper,
    OpenAIAPIRetriever,
    Retriever,
    RetrieverFactory,
    SpanishDictWebsiteScraper,
    WebsiteScraper,
)

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_RETRIEVER_DIR = SCRIPT_DIR + "/data/test_retriever/"


@pytest.fixture
def mock_url() -> str:
    return "https://example.com"


@pytest.fixture
def mock_retriever(mock_url: str) -> Retriever:
    class TestRetriever(Retriever):
        available_language_pairs: list[tuple[Language, Language]] = [
            (Language.SPANISH, Language.ENGLISH)
        ]
        base_url: str = mock_url

        async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
            return []

    return TestRetriever(language_from=Language.SPANISH, language_to=Language.ENGLISH)


@pytest.fixture
def mock_website_scraper(mock_url: str) -> WebsiteScraper:
    class TestWebsiteScraper(WebsiteScraper):
        available_language_pairs: list[tuple[Language, Language]] = [
            (Language.SPANISH, Language.ENGLISH)
        ]
        base_url: str = mock_url

        async def retrieve_translations(self, word_to_translate: str) -> list[Translation]:
            return []

    return TestWebsiteScraper(language_from=Language.SPANISH, language_to=Language.ENGLISH)


@pytest.mark.asyncio
async def test_rate_limited(mock_url: str, mock_retriever: Retriever) -> None:
    mock_url = "https://example.com"
    try:
        with aioresponses() as m:
            # Mock rate-limited response
            m.get(mock_url, status=HTTPStatus.TOO_MANY_REQUESTS)
            is_rate_limited = await mock_retriever.rate_limited()
            assert is_rate_limited

            # Mock non rate-limited response
            m.clear()
            m.get(mock_url, status=200)
            is_rate_limited = await mock_retriever.rate_limited()
            assert not is_rate_limited
    finally:
        await mock_retriever.close_session()


def test_standardize(mock_retriever: Retriever) -> None:
    assert mock_retriever._standardize("remove: punctuation!") == "remove punctuation"
    assert mock_retriever._standardize("  remove whitespace  ") == "remove whitespace"
    assert mock_retriever._standardize("Remove Capitalisation") == "remove capitalisation"


def test_retriever_factory():
    openai_retriever = RetrieverFactory.create_retriever(
        "openai", language_from=Language.SPANISH, language_to=Language.ENGLISH
    )
    assert isinstance(openai_retriever, OpenAIAPIRetriever)
    collins_retriever = RetrieverFactory.create_retriever(
        "collins", language_from=Language.SPANISH, language_to=Language.ENGLISH
    )
    assert isinstance(collins_retriever, CollinsWebsiteScraper)
    spanishdict_retriever = RetrieverFactory.create_retriever(
        "spanishdict", language_from=Language.SPANISH, language_to=Language.ENGLISH
    )
    assert isinstance(spanishdict_retriever, SpanishDictWebsiteScraper)
    with pytest.raises(ValueError):
        RetrieverFactory.create_retriever(
            "unknown", language_from=Language.SPANISH, language_to=Language.ENGLISH
        )


@pytest.mark.asyncio
async def test_get_soup(mock_url: str, mock_website_scraper: WebsiteScraper) -> None:
    mock_html = "<html><body>Mocked HTML</body></html>"
    try:
        with aioresponses() as m:
            m.get(mock_url, status=200, body=mock_html)
            soup = await mock_website_scraper._get_soup(mock_url)
            assert soup is not None
            assert soup.find("body").text == "Mocked HTML"
    finally:
        await mock_website_scraper.close_session()


@pytest.fixture
def test_word() -> str:
    return "prueba"


@pytest.fixture
def spanish_dict_url(test_word: str) -> str:
    return f"https://www.spanishdict.com/translate/{test_word}?langFrom=es"


@pytest.fixture
def spanish_dict_html() -> str:
    with open(
        TEST_RETRIEVER_DIR + "spanish_dict_website_scraper_test.html", encoding="utf-8"
    ) as fh:
        return fh.read()


@pytest.mark.asyncio
async def test_spanish_dict_website_scraper_no_concise_mode(
    test_word: str, spanish_dict_url: str, spanish_dict_html: str
) -> None:
    try:
        retriever = SpanishDictWebsiteScraper(
            language_from=Language.SPANISH, language_to=Language.ENGLISH
        )
        retriever.concise_mode = False  # Default is False but setting explicitly for clarity
        with aioresponses() as m:
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            translations = await retriever.retrieve_translations(test_word)
            assert translations == [
                Translation(
                    retriever,
                    "prueba",
                    "feminine noun",
                    [
                        Definition(
                            "test",
                            [
                                SentencePair(
                                    "Hay una prueba de matemáticas el miércoles.",
                                    "There's a math test on Wednesday.",
                                ),
                                SentencePair(
                                    "No pasó la prueba de acceso y tiene que tomar cursos de regularización.",  # noqa: E501
                                    "He didn't pass the entrance examination and has to take remedial courses.",  # noqa: E501
                                ),
                                SentencePair(
                                    "Nos han dado una prueba para hacer en casa.",
                                    "We've been given a quiz to do at home.",
                                ),
                            ],
                        ),
                        Definition(
                            "proof",
                            [
                                SentencePair(
                                    "La carta fue la prueba de que su historia era cierta.",
                                    "The letter was proof that her story was true.",
                                ),
                                SentencePair(
                                    "Te doy este anillo como prueba de mi amor.",
                                    "I give you this ring as a token of my love.",
                                ),
                                SentencePair(
                                    "Su risa fue la prueba de que ya no estaba enojada.",
                                    "Her laugh was a sign that she was no longer mad.",
                                ),
                            ],
                        ),
                        Definition(
                            "piece of evidence",
                            [
                                SentencePair(
                                    "El fiscal no pudo presentar ninguna prueba para condenarlo.",
                                    "The prosecution couldn't present a single piece of evidence to convict him.",  # noqa: E501
                                )
                            ],
                        ),
                    ],
                ),
                Translation(
                    retriever,
                    "prueba",
                    "plural noun",
                    [
                        Definition(
                            "evidence",
                            [
                                SentencePair(
                                    "El juez debe pesar todas las pruebas presentadas antes de dictar sentencia.",  # noqa: E501
                                    "The judge must weigh all of the evidence presented before sentencing.",  # noqa: E501
                                )
                            ],
                        )
                    ],
                ),
            ]
    finally:
        await retriever.close_session()


@pytest.mark.asyncio
async def test_spanish_dict_website_scraper_concise_mode(
    test_word: str, spanish_dict_url: str, spanish_dict_html: str
) -> None:
    retriever = SpanishDictWebsiteScraper(
        language_from=Language.SPANISH, language_to=Language.ENGLISH
    )
    retriever.concise_mode = True
    try:
        with aioresponses() as m:
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            translations = await retriever.retrieve_translations(test_word)
            assert translations == [
                Translation(
                    retriever,
                    "prueba",
                    "feminine noun",
                    [
                        Definition(
                            "test",
                            [
                                SentencePair(
                                    "Hay una prueba de matemáticas el miércoles.",
                                    "There's a math test on Wednesday.",
                                ),
                                SentencePair(
                                    "No pasó la prueba de acceso y tiene que tomar cursos de regularización.",  # noqa: E501
                                    "He didn't pass the entrance examination and has to take remedial courses.",  # noqa: E501
                                ),
                                SentencePair(
                                    "Nos han dado una prueba para hacer en casa.",
                                    "We've been given a quiz to do at home.",
                                ),
                            ],
                        ),
                        Definition(
                            "proof",
                            [
                                SentencePair(
                                    "La carta fue la prueba de que su historia era cierta.",
                                    "The letter was proof that her story was true.",
                                ),
                                SentencePair(
                                    "Te doy este anillo como prueba de mi amor.",
                                    "I give you this ring as a token of my love.",
                                ),
                                SentencePair(
                                    "Su risa fue la prueba de que ya no estaba enojada.",
                                    "Her laugh was a sign that she was no longer mad.",
                                ),
                            ],
                        ),
                    ],
                ),
            ]

            # Test that the translations do not include the second quickdef if it is removed from the HTML  # noqa: E501
            def remove_div_quickdef2_es(html_content: str) -> str:
                soup = BeautifulSoup(html_content, "html.parser")
                div_to_remove = soup.find("div", id="quickdef2-es")
                if div_to_remove:
                    div_to_remove.decompose()
                return str(soup)

            spanish_dict_html = remove_div_quickdef2_es(spanish_dict_html)
            m.clear()
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            retriever._get_soup.cache_clear()
            translations = await retriever.retrieve_translations(test_word)
            assert translations == [
                Translation(
                    retriever,
                    "prueba",
                    "feminine noun",
                    [
                        Definition(
                            "test",
                            [
                                SentencePair(
                                    "Hay una prueba de matemáticas el miércoles.",
                                    "There's a math test on Wednesday.",
                                ),
                                SentencePair(
                                    "No pasó la prueba de acceso y tiene que tomar cursos de regularización.",  # noqa: E501
                                    "He didn't pass the entrance examination and has to take remedial courses.",  # noqa: E501
                                ),
                                SentencePair(
                                    "Nos han dado una prueba para hacer en casa.",
                                    "We've been given a quiz to do at home.",
                                ),
                            ],
                        ),
                    ],
                ),
            ]
    finally:
        await retriever.close_session()


@pytest.mark.asyncio
async def test_openai_api_retriever() -> None:
    mock_openai_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "translations": [
                                {
                                    "word_to_translate": "hola",
                                    "part_of_speech": "interjection",
                                    "definitions": [
                                        {
                                            "text": "hello",
                                            "sentence_pairs": [
                                                {
                                                    "source_sentence": "Hola, ¿cómo estás?",
                                                    "target_sentence": "Hello, how are you?",
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ]
                        }
                    )
                )
            )
        ]
    )

    mock_openai_client = AsyncMock()
    mock_openai_client.chat.completions.create.return_value = mock_openai_response
    retriever = OpenAIAPIRetriever(language_from=Language.SPANISH, language_to=Language.ENGLISH)
    retriever.client = mock_openai_client
    retriever.language = Language.SPANISH
    retriever.model = OpenAIModel.GPT_4_TURBO
    translations = await retriever.retrieve_translations("hola")
    expected_translation = Translation(
        retriever,
        "hola",
        "interjection",
        [
            Definition(
                "hello",
                [
                    SentencePair(
                        "Hola, ¿cómo estás?",
                        "Hello, how are you?",
                    )
                ],
            )
        ],
    )
    assert translations == [expected_translation]


@pytest.fixture
def collins_url(test_word: str) -> str:
    return f"https://www.collinsdictionary.com/dictionary/spanish-english/{test_word}"


@pytest.mark.asyncio
async def test_collins_website_scraper(test_word: str, collins_url: str) -> None:
    with open(TEST_RETRIEVER_DIR + "collins_website_scraper_test.html", encoding="utf-8") as fh:
        mock_html = fh.read()
    retriever = CollinsWebsiteScraper(language_from=Language.SPANISH, language_to=Language.ENGLISH)
    with aioresponses() as m:
        m.get(collins_url, status=200, body=mock_html)
        translations = await retriever.retrieve_translations(test_word)
        assert translations == [
            Translation(
                retriever,
                "prueba",
                "feminine noun",
                [
                    Definition(
                        "proof",
                        [
                            SentencePair(
                                "esta es una prueba palpable de su incompetencia",
                                "this is clear proof of his incompetence",
                            ),
                            SentencePair(
                                "es prueba de que tiene buena salud",
                                "that proves or shows he’s in good health",
                            ),
                            SentencePair(
                                "sin dar la menor prueba de ello",
                                "without giving the faintest sign of it",
                            ),
                        ],
                    ),
                    Definition(
                        "piece of evidence",
                        [
                            SentencePair(
                                "pruebas",
                                "evidence singular",
                            ),
                            SentencePair(
                                "el fiscal presentó nuevas pruebas",
                                "the prosecutor presented new evidence",
                            ),
                            SentencePair(
                                "se encuentran en libertad por falta de pruebas",
                                "they were released for lack of evidence",
                            ),
                        ],
                    ),
                    Definition(
                        "test",
                        [
                            SentencePair(
                                "la maestra nos hizo una prueba de vocabulario",
                                "our teacher gave us a vocabulary test",
                            ),
                            SentencePair(
                                "el médico me hizo más pruebas",
                                "the doctor did some more tests on me",
                            ),
                            SentencePair(
                                "se tendrán que hacer la prueba del SIDA",
                                "they’ll have to be tested for AIDS",
                            ),
                        ],
                    ),
                ],
            ),
        ]
