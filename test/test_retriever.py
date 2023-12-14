import pytest
from aioresponses import aioresponses

from language_element import Definition, SentencePair, Translation
from retriever import SpanishDictWebsiteScraper


@pytest.mark.asyncio
async def test_get_soup() -> None:
    mock_url = "https://example.com"
    mock_html = "<html><body>Mocked HTML</body></html>"
    with aioresponses() as m:
        m.get(mock_url, status=200, body=mock_html)
        scraper = SpanishDictWebsiteScraper()
        soup = await scraper._get_soup(mock_url)
        assert soup is not None
        assert soup.find("body").text == "Mocked HTML"


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
    with aioresponses() as m:
        m.get(spanish_dict_url, status=200, body=spanish_dict_html)
        scraper = SpanishDictWebsiteScraper()
        scraper.quickdef_mode = False
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
