import asyncio
from typing import List
from unittest.mock import AsyncMock

import pytest

from exception import RateLimitException
from language_element import Definition, SentencePair, Translation
from note_creator import NoteCreator


@pytest.fixture
def deck_id() -> int:
    return 1_000_000_000


@pytest.fixture
def field_keys() -> List[str]:
    return [
        "deck_id",
        "word",
        "part_of_speech",
        "definition",
        "source_sentences",
        "target_sentences",
    ]


@pytest.fixture
def field_values(deck_id: int) -> List[str]:
    return [str(deck_id), "test", "noun", "test definition", "Source sentence", "Target sentence"]


@pytest.fixture
def note_creator(deck_id: int) -> NoteCreator:
    dictionary = AsyncMock()
    return NoteCreator(deck_id, dictionary, concurrency_limit=1)


@pytest.fixture
def translation() -> Translation:
    return Translation(
        "test",
        "noun",
        [Definition("test definition", [SentencePair("Source sentence", "Target sentence")])],
    )


def test_combine_sentences_single_sentence(note_creator: NoteCreator) -> None:
    sentences = ["This is a test sentence."]
    combined = note_creator._combine_sentences(sentences)
    assert combined == "This is a test sentence."


def test_combine_sentences_multiple_sentences(note_creator: NoteCreator) -> None:
    sentences = ["First sentence.", "Second sentence."]
    expected_combined = "<span style='color: darkgray'>[1]</span> First sentence.<br><span style='color: darkgray'>[2]</span> Second sentence."  # noqa: E501
    combined = note_creator._combine_sentences(sentences)
    assert combined == expected_combined


def test_create_note_from_translation(
    field_values: List[str], note_creator: NoteCreator, translation: Translation
) -> None:
    note = note_creator._create_note_from_translation(translation)
    assert note.fields == field_values


@pytest.mark.asyncio
async def test_create_notes(
    field_values: List[str], note_creator: NoteCreator, translation: Translation
) -> None:
    note_creator.dictionary.translate.return_value = [translation]
    notes = await note_creator.create_notes("test")
    assert len(notes) == 1
    assert notes[0].fields == field_values


@pytest.mark.asyncio
async def test_rate_limited_create_notes(
    field_values: List[str], note_creator: NoteCreator, translation: Translation
) -> None:
    note_creator.dictionary.translate.return_value = [translation]
    notes = await note_creator.rate_limited_create_notes("test")
    assert len(notes) == 1
    assert notes[0].fields == field_values


@pytest.mark.asyncio
async def test_rate_limited_create_notes_with_rate_limit_exception(
    field_values: List[str], note_creator: NoteCreator, translation: Translation
) -> None:
    asyncio.sleep = AsyncMock()
    note_creator.dictionary.retriever.rate_limited = AsyncMock(return_value=False)
    note_creator.dictionary.translate = AsyncMock(side_effect=[RateLimitException, [translation]])
    notes = await note_creator.rate_limited_create_notes("test")
    assert len(notes) == 1
    assert notes[0].fields == field_values
    assert asyncio.sleep.call_count == 1
    assert note_creator.dictionary.retriever.rate_limited.call_count == 1
    assert note_creator.dictionary.translate.call_count == 2


@pytest.mark.asyncio
async def test_rate_limited_create_notes_with_general_exception(
    note_creator: NoteCreator, translation: Translation
) -> None:
    note_creator.dictionary.translate.return_value = [translation]
    note_creator.create_notes = AsyncMock(side_effect=Exception)
    notes = await note_creator.rate_limited_create_notes("test")
    assert notes == []
