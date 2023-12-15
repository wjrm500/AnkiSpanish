import json
from http import HTTPStatus
from types import SimpleNamespace
from typing import List, Tuple
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup

from constant import Language, OpenAIModel
from language_element import Definition, SentencePair, Translation
from retriever import (
    CollinsSpanishWebsiteScraper,
    OpenAIAPIRetriever,
    Retriever,
    RetrieverFactory,
    SpanishDictWebsiteScraper,
    WebsiteScraper,
)


@pytest.fixture
def mock_url() -> str:
    return "https://example.com"


@pytest.fixture
def mock_retriever(mock_url: str) -> Retriever:
    class TestRetriever(Retriever):
        available_language_pairs: List[Tuple[Language, Language]] = [
            (Language.SPANISH, Language.ENGLISH)
        ]
        base_url: str = mock_url

        async def retrieve_translations(self, word_to_translate: str) -> List[Translation]:
            return []

    return TestRetriever(language_from=Language.SPANISH, language_to=Language.ENGLISH)


@pytest.fixture
def mock_website_scraper(mock_url: str) -> WebsiteScraper:
    class TestWebsiteScraper(WebsiteScraper):
        available_language_pairs: List[Tuple[Language, Language]] = [
            (Language.SPANISH, Language.ENGLISH)
        ]
        base_url: str = mock_url

        async def retrieve_translations(self, word_to_translate: str) -> List[Translation]:
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
        "collinsspanish", language_from=Language.SPANISH, language_to=Language.ENGLISH
    )
    assert isinstance(collins_retriever, CollinsSpanishWebsiteScraper)
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
def spanish_dict_word() -> str:
    return "prueba"


@pytest.fixture
def spanish_dict_url(spanish_dict_word: str) -> str:
    return f"https://www.spanishdict.com/translate/{spanish_dict_word}?langFrom=es"


@pytest.fixture
def spanish_dict_html() -> str:
    return """
    <html>
        <body>
            <div id="quickdef1-es">
                <a>test</a>
            </div>
            <div id="quickdef2-es">
                <a>proof</a>
            </div>
            <div id="dictionary-neodict-es">
                <div class="W4_X2sG1">
                    <div class="VlFhSoPR L0ywlHB1 cNX9vGLU CDAsok0l VEBez1ed">
                        <a>feminine noun</a>
                    </div>
                    <div class="tmBfjszm">
                        <span>
                            <a>test</a>
                        </span>
                        <div>
                            <span lang="es">Hay una prueba de matemáticas el miércoles.</span>
                            <span lang="en">There's a math test on Wednesday.</span>
                        </div>
                    </div>
                    <div class="tmBfjszm">
                        <span>
                            <a>proof</a>
                        </span>
                        <div>
                            <span lang="es">La carta fue la prueba de que su historia era cierta.</span>  # noqa: E501
                            <span lang="en">The letter was proof that her story was true.</span>
                        </div>
                    </div>
                </div>
                <div class="W4_X2sG1">
                    <div class="VlFhSoPR L0ywlHB1 cNX9vGLU CDAsok0l VEBez1ed">
                        <a>plural noun</a>
                    </div>
                    <div class="tmBfjszm">
                        <span>
                            <a>evidence</a>
                        </span>
                        <div>
                            <span lang="es">El juez debe pesar todas las pruebas presentadas antes de dictar sentencia.</span>  # noqa: E501
                            <span lang="en">The judge must weigh all of the evidence presented before sentencing.</span>  # noqa: E501
                        </div>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """


@pytest.mark.asyncio
async def test_spanish_dict_website_scraper_no_concise_mode(
    spanish_dict_word: str, spanish_dict_url: str, spanish_dict_html: str
) -> None:
    try:
        retriever = SpanishDictWebsiteScraper(
            language_from=Language.SPANISH, language_to=Language.ENGLISH
        )
        retriever.concise_mode = False  # Default is False but setting explicitly for clarity
        with aioresponses() as m:
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            translations = await retriever.retrieve_translations(spanish_dict_word)
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
                                )
                            ],
                        ),
                        Definition(
                            "proof",
                            [
                                SentencePair(
                                    "La carta fue la prueba de que su historia era cierta.",
                                    "The letter was proof that her story was true.",
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
    spanish_dict_word: str, spanish_dict_url: str, spanish_dict_html: str
) -> None:
    retriever = SpanishDictWebsiteScraper(
        language_from=Language.SPANISH, language_to=Language.ENGLISH
    )
    retriever.concise_mode = True
    try:
        with aioresponses() as m:
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            translations = await retriever.retrieve_translations(spanish_dict_word)
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
                                )
                            ],
                        ),
                        Definition(
                            "proof",
                            [
                                SentencePair(
                                    "La carta fue la prueba de que su historia era cierta.",
                                    "The letter was proof that her story was true.",
                                )
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
            translations = await retriever.retrieve_translations(spanish_dict_word)
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
                                )
                            ],
                        )
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
