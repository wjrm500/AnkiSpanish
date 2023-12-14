from http import HTTPStatus
from typing import List

import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup

from language_element import Definition, SentencePair, Translation
from retriever import Retriever, SpanishDictWebsiteScraper


@pytest.fixture
def mock_url() -> str:
    return "https://example.com"


@pytest.fixture
def mock_retriever(mock_url: str) -> Retriever:
    class TestRetriever(Retriever):
        base_url: str = mock_url

        async def retrieve_translations(self, word_to_translate: str) -> List[Translation]:
            return []
    return TestRetriever()


@pytest.mark.asyncio
async def test_retriever_rate_limited(
    mock_url: str, mock_retriever: Retriever
) -> None:
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


@pytest.mark.asyncio
async def test_get_soup() -> None:
    mock_url = "https://example.com"
    mock_html = "<html><body>Mocked HTML</body></html>"
    scraper = SpanishDictWebsiteScraper()
    try:
        with aioresponses() as m:
            m.get(mock_url, status=200, body=mock_html)
            soup = await scraper._get_soup(mock_url)
            assert soup is not None
            assert soup.find("body").text == "Mocked HTML"
    finally:
        await scraper.close_session()


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
async def test_spanish_dict_website_scraper_no_quickdef(
    spanish_dict_word: str, spanish_dict_url: str, spanish_dict_html: str
) -> None:
    try:
        scraper = SpanishDictWebsiteScraper()
        scraper.quickdef_mode = False
        with aioresponses() as m:
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            translations = await scraper.retrieve_translations(spanish_dict_word)
            assert translations == [
                Translation(
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
        await scraper.close_session()


@pytest.mark.asyncio
async def test_spanish_dict_website_scraper_quickdef(
    spanish_dict_word: str, spanish_dict_url: str, spanish_dict_html: str
) -> None:
    scraper = SpanishDictWebsiteScraper()
    scraper.quickdef_mode = True  # Default is True but setting explicitly for clarity
    try:
        with aioresponses() as m:
            m.get(spanish_dict_url, status=200, body=spanish_dict_html)
            translations = await scraper.retrieve_translations(spanish_dict_word)
            assert translations == [
                Translation(
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
            scraper._get_soup.cache_clear()
            translations = await scraper.retrieve_translations(spanish_dict_word)
            assert translations == [
                Translation(
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
        await scraper.close_session()
