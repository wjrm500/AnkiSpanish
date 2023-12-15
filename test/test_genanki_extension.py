import os

import pytest

from genanki_extension import load_decks_from_package

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_GENANKI_EXTENSION_DIR = SCRIPT_DIR + "/data/test_genanki_extension/"


@pytest.fixture
def apkg_file_path() -> str:
    return TEST_GENANKI_EXTENSION_DIR + "freq_dict.apkg"


def test_load_decks_from_package_success(apkg_file_path: str) -> None:
    # Load decks from the .apkg file
    decks = load_decks_from_package(apkg_file_path)

    # Assert that there is exactly one deck and its name is correct
    assert len(decks) == 1
    assert decks[0].name == "A Frequency Dictionary of Spanish"

    # Assert that the deck contains exactly 5,000 notes
    assert len(decks[0].notes) == 5000

    # Assert that the deck contains a note with the expected fields
    expected_fields = {
        "Rank": "1",
        "Word": "el, la",
        "Part-of-Speech": "art",
        "Definition": "the (+m, f)",
        "Spanish": "el diccionario tenía también frases útiles",
        "English": "the dictionary also had useful phrases",
        "Freq": "2055835 | 201481381",
    }
    note_found = False
    for note in decks[0].notes:
        note_fields = {
            field_name: note.fields[idx] for idx, field_name in enumerate(expected_fields)
        }
        if note_fields == expected_fields:
            note_found = True
            break
    assert note_found, "Note with the specified fields was not found."
