import argparse
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from genanki import Note as AnkiNote

from app.dictionary import Dictionary
from app.genanki_extension import load_decks_from_package
from app.main import create_deck, valid_input_path, valid_output_anki_package_path
from app.note_creator import NoteCreator, model
from app.retriever import SpanishDictWebsiteScraper

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


def test_valid_input_path():
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=True) as temp_file:
        assert valid_input_path(".csv", temp_file.name) == temp_file.name


def test_invalid_input_path_nonexistent_file():
    with pytest.raises(argparse.ArgumentTypeError):
        valid_input_path(".csv", "nonexistent.csv")


def test_invalid_input_path_wrong_extension():
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=True) as temp_file:
        with pytest.raises(argparse.ArgumentTypeError):
            valid_input_path(".csv", temp_file.name)


def test_valid_output_anki_package_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        valid_output_path = f"{temp_dir}/output.apkg"
        assert valid_output_anki_package_path(valid_output_path) == valid_output_path


def test_invalid_output_anki_package_path_nonexistent_dir():
    nonexistent_dir_path = "/nonexistent_dir/output.apkg"
    with pytest.raises(argparse.ArgumentTypeError):
        valid_output_anki_package_path(nonexistent_dir_path)


def test_invalid_output_anki_package_path_wrong_extension():
    with tempfile.TemporaryDirectory() as temp_dir:
        invalid_output_path = f"{temp_dir}/output.txt"
        with pytest.raises(argparse.ArgumentTypeError):
            valid_output_anki_package_path(invalid_output_path)


@pytest.mark.asyncio
async def test_create_deck() -> None:
    anki_package_path = os.path.join(SCRIPT_DIR, "test.apkg")
    try:
        # Delete output.apkg if it exists
        if os.path.exists(anki_package_path):
            os.remove(anki_package_path)

        # Run main with mocks
        deck_id = "123456789"
        mock_notes = {
            "hola": [
                AnkiNote(
                    model=model,
                    fields=[
                        deck_id,
                        "hola",  # word_to_translate
                        "<a href='https://www.spanishdict.com/translate/hola?langFrom=es' style='color:red;'>hola</a>",  # word_to_translate_html
                        "interjection",  # part_of_speech
                        "<a href='https://www.spanishdict.com/translate/hello?langFrom=en' style='color:green;'>hello</a>",  # definition_html
                        "¡Hola! ¿Cómo estás?",  # source_sentences
                        "Hello! How are you?",  # target_sentences
                    ],
                ),
            ],
            "adiós": [
                AnkiNote(
                    model=model,
                    fields=[
                        deck_id,
                        "adiós",  # word_to_translate
                        "<a href='https://www.spanishdict.com/translate/adi%C3%B3s?langFrom=es' style='color:red;'>adiós</a>",  # word_to_translate_html
                        "interjection",  # part_of_speech
                        "<a href='https://www.spanishdict.com/translate/goodbye?langFrom=en' style='color:green;'>goodbye</a>",  # definition_html
                        "¡Adiós! ¡Nos vemos!",  # source_sentences
                        "Goodbye! See you later!",  # target_sentences
                    ],
                ),
            ],
        }
        note_creator = NoteCreator(
            deck_id=deck_id,
            dictionary=MagicMock(spec=Dictionary),
            concurrency_limit=1,
        )
        note_creator.rate_limited_create_notes = AsyncMock(side_effect=list(mock_notes.values()))
        with patch("app.main.NoteCreator", return_value=note_creator):
            await create_deck(
                words_to_translate=["hola", "adiós"],
                retriever=MagicMock(spec=SpanishDictWebsiteScraper),
                concurrency_limit=1,
                note_limit=0,
                output_anki_package_path=anki_package_path,
                output_anki_deck_name="Language learning flashcards",
            )

        # Make assertions
        assert os.path.exists(anki_package_path)
        decks = load_decks_from_package(anki_package_path)
        assert len(decks) == 1
        deck = decks[0]
        assert deck.name == "Language learning flashcards"
        assert len(deck.notes) == 2
        for note in deck.notes:
            assert isinstance(note, AnkiNote)
            word_to_translate = note.fields[1]
            assert (
                note.fields[1:] == mock_notes[word_to_translate][0].fields[1:]
            )  # Ignore deck_id as it is random
    finally:
        # Delete output.apkg if it exists
        if os.path.exists(anki_package_path):
            os.remove(anki_package_path)
