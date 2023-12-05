import asyncio
from typing import List
from unittest.mock import AsyncMock

import pytest
from genanki import Model as AnkiModel
from genanki import Note as AnkiNote

from exception import RateLimitException
from note_creator import NoteCreator
from translation import Definition, SentencePair, Translation


@pytest.fixture
def field_keys() -> List[str]:
    return ["word", "part_of_speech", "definition", "source_sentences", "target_sentences"]


@pytest.fixture
def field_values() -> List[str]:
    return ["test", "noun", "test definition", "Source sentence", "Target sentence"]


@pytest.fixture
def model(field_keys: List[str]) -> AnkiModel:
    return AnkiModel(1, "test", fields=[{"name": field_key} for field_key in field_keys])


@pytest.fixture
def note_creator(model: AnkiModel) -> NoteCreator:
    scraper = AsyncMock()
    return NoteCreator(model, scraper, concurrency_limit=1)


@pytest.fixture
def translation() -> Translation:
    return Translation(
        "test",
        "noun",
        [Definition("test definition", [SentencePair("Source sentence", "Target sentence")])],
    )


@pytest.fixture
def note(model: AnkiModel, field_values: List[str]) -> AnkiNote:
    return AnkiNote(model=model, fields=field_values)


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
    note_creator.model.fields = [
        "word",
        "part_of_speech",
        "definition",
        "source_sentences",
        "target_sentences",
    ]
    note = note_creator._create_note_from_translation(translation)
    assert note.fields == field_values


@pytest.mark.asyncio
async def test_create_notes(
    field_values: List[str], note_creator: NoteCreator, translation: Translation
) -> None:
    note_creator.scraper.translate.return_value = [translation]
    notes = await note_creator.create_notes("test")
    assert len(notes) == 1
    assert notes[0].fields == field_values


@pytest.mark.asyncio
async def test_rate_limited_create_notes(
    note_creator: NoteCreator, translation: Translation
) -> None:
    note_creator.scraper.translate.return_value = [translation]
    notes = await note_creator.rate_limited_create_notes("test")
    assert len(notes) == 1
    assert notes[0].fields == [
        "test",
        "noun",
        "test definition",
        "Source sentence",
        "Target sentence",
    ]


@pytest.mark.asyncio
async def test_rate_limited_create_notes_with_rate_limit_exception(
    note_creator: NoteCreator, translation: Translation
) -> None:
    asyncio.sleep = AsyncMock()
    note_creator.scraper.rate_limited = AsyncMock(return_value=False)
    note_creator.scraper.translate = AsyncMock(side_effect=[RateLimitException, [translation]])
    notes = await note_creator.rate_limited_create_notes("test")
    assert len(notes) == 1
    assert notes[0].fields == [
        "test",
        "noun",
        "test definition",
        "Source sentence",
        "Target sentence",
    ]
    assert asyncio.sleep.call_count == 1
    assert note_creator.scraper.rate_limited.call_count == 1
    assert note_creator.scraper.translate.call_count == 2


@pytest.mark.asyncio
async def test_rate_limited_create_notes_with_general_exception(
    note_creator: NoteCreator, translation: Translation
) -> None:
    note_creator.scraper.translate.return_value = [translation]
    note_creator.create_notes = AsyncMock(side_effect=Exception)
    notes = await note_creator.rate_limited_create_notes("test")
    assert notes == []
