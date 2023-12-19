import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dictionary import Dictionary
from app.exception import RateLimitException, RedirectException
from app.language_element import Definition, SentencePair, Translation
from app.note_creator import NoteCreator
from app.retriever import Retriever


@pytest.fixture
def deck_id() -> int:
    return 1_000_000_000


@pytest.fixture
def field_keys() -> list[str]:
    return [
        "deck_id",
        "word_to_translate",
        "word_to_translate_html",
        "part_of_speech",
        "definition_html",
        "source_sentences",
        "target_sentences",
    ]


@pytest.fixture
def field_values(deck_id: int) -> list[str]:
    return [
        str(deck_id),
        "prueba",
        "<a href='https://www.example.com/translate/prueba' style='color:red;'>prueba</a>",
        "feminine noun",
        "<a href='https://www.example.com/translate/test?langFrom=en' style='color:green;'>test</a>",
        "Source sentence",
        "Target sentence",
    ]


@pytest.fixture
def retriever() -> Retriever:
    retriever = MagicMock(spec=Retriever)
    retriever.link.return_value = "https://www.example.com/translate/prueba"
    retriever.reverse_link.return_value = "https://www.example.com/translate/test?langFrom=en"
    return retriever


@pytest.fixture
def note_creator(deck_id: int, retriever: Retriever) -> NoteCreator:
    return NoteCreator(
        deck_id=deck_id,
        dictionary=MagicMock(spec=Dictionary, retriever=retriever),
        concurrency_limit=1,
    )


@pytest.fixture
def translation(retriever: Retriever) -> Translation:
    return Translation(
        word_to_translate="prueba",
        part_of_speech="feminine noun",
        definitions=[
            Definition(
                text="test",
                sentence_pairs=[
                    SentencePair(
                        source_sentence="Source sentence", target_sentence="Target sentence"
                    ),
                ],
            ),
        ],
        retriever=retriever,
    )


def test_combine_sentences_single_sentence(note_creator: NoteCreator) -> None:
    sentences = ["This is a test sentence."]
    combined = note_creator._combine_sentences(sentences)
    assert combined == "This is a test sentence."


def test_combine_sentences_multiple_sentences(note_creator: NoteCreator) -> None:
    sentences = ["First sentence.", "Second sentence."]
    expected_combined = "<span style='color: darkgray'>[1]</span> First sentence.<br><span style='color: darkgray'>[2]</span> Second sentence."
    combined = note_creator._combine_sentences(sentences)
    assert combined == expected_combined


def test_create_note_from_translation(
    field_values: list[str], note_creator: NoteCreator, translation: Translation
) -> None:
    note = note_creator._create_note_from_translation(translation)
    assert note.fields == field_values


@pytest.mark.asyncio
async def test_create_notes(
    field_values: list[str], note_creator: NoteCreator, translation: Translation
) -> None:
    note_creator.dictionary.translate.return_value = [translation]
    notes = await note_creator.create_notes("test")
    assert len(notes) == 1
    assert notes[0].fields == field_values


@pytest.mark.asyncio
async def test_rate_limited_create_notes(
    field_values: list[str], note_creator: NoteCreator, translation: Translation
) -> None:
    note_creator.dictionary.translate.return_value = [translation]
    notes = await note_creator.rate_limited_create_notes("prueba")
    assert len(notes) == 1
    assert notes[0].fields == field_values


@pytest.mark.asyncio
async def test_rate_limited_create_notes_with_rate_limit_exception(
    field_values: list[str], note_creator: NoteCreator, translation: Translation
) -> None:
    asyncio.sleep = AsyncMock()
    note_creator.dictionary.retriever.rate_limited = AsyncMock(return_value=False)
    note_creator.dictionary.translate = AsyncMock(side_effect=[RateLimitException, [translation]])
    notes = await note_creator.rate_limited_create_notes("prueba")
    assert len(notes) == 1
    assert notes[0].fields == field_values
    assert asyncio.sleep.call_count == 1
    assert note_creator.dictionary.retriever.rate_limited.call_count == 1
    assert note_creator.dictionary.translate.call_count == 2


@pytest.mark.asyncio
async def test_rate_limited_create_notes_with_redirect_exception(
    field_values: list[str], note_creator: NoteCreator, translation: Translation
) -> None:
    # Setup
    original_url = "https://www.example.com/translate/prueba"
    redirect_url = "https://www.example.com/redirect"
    exception = RedirectException(
        message=f"URL redirected from {original_url} to {redirect_url}",
        response_url=redirect_url,
    )
    side_effect = [exception] * 6 + [[translation]]
    note_creator.dictionary.translate = AsyncMock(side_effect=side_effect)

    # Increment redirect count to 5, then manually intervene
    for _ in range(5):
        await note_creator.rate_limited_create_notes("prueba")
    assert note_creator.redirect_count == 5
    with patch("builtins.input", return_value="\r") as mock_input:
        await note_creator.rate_limited_create_notes("prueba")
    mock_input.assert_called_once()
    assert note_creator.redirect_count == 0

    # Check that normal processing continues after manual intervention
    notes = await note_creator.rate_limited_create_notes("prueba")
    assert len(notes) == 1
    assert notes[0].fields == field_values


@pytest.mark.asyncio
async def test_rate_limited_create_notes_with_general_exception(
    note_creator: NoteCreator, translation: Translation
) -> None:
    note_creator.dictionary.translate.return_value = [translation]
    note_creator.create_notes = AsyncMock(side_effect=Exception)
    notes = await note_creator.rate_limited_create_notes("prueba")
    assert notes == []
