import os

import pytest

from source import AnkiPackageSource, CSVSource, SimpleSource

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_SOURCE_DIR = SCRIPT_DIR + "/data/test_source/"


def test_simple_source():
    source = SimpleSource(words_to_translate=["hola", "hola", "adiós"])
    assert sorted(source.get_words_to_translate()) == ["adiós", "hola"]


def test_anki_package_source() -> None:
    source = AnkiPackageSource(package_path=TEST_SOURCE_DIR + "populated_deck.apkg")
    assert sorted(source.get_words_to_translate()) == ["adiós", "hola"]


def test_anki_package_source_with_incorrect_deck_name() -> None:
    source = AnkiPackageSource(
        package_path=TEST_SOURCE_DIR + "populated_deck.apkg", deck_name="Incorrect deck name"
    )
    with pytest.raises(ValueError) as e_info:
        source.get_words_to_translate()
    assert str(e_info.value) == "Deck 'Incorrect deck name' not found in package"


def test_anki_package_source_with_empty_deck() -> None:
    source = AnkiPackageSource(package_path=TEST_SOURCE_DIR + "empty_deck.apkg")
    with pytest.raises(ValueError) as e_info:
        source.get_words_to_translate()
    assert str(e_info.value) == "Deck 'Empty deck' has no notes"


def test_anki_package_source_with_incorrect_field_name() -> None:
    source = AnkiPackageSource(
        package_path=TEST_SOURCE_DIR + "populated_deck.apkg", field_name="Incorrect field name"
    )
    with pytest.raises(ValueError) as e_info:
        source.get_words_to_translate()
    assert (
        str(e_info.value)
        == "Field 'Incorrect field name' not found in model. Available fields: ['Word', 'Translation']"  # noqa: E501
    )


def test_csv_source() -> None:
    source = CSVSource(file_path=TEST_SOURCE_DIR + "source_test.csv")
    assert sorted(source.get_words_to_translate()) == ["adiós", "hola"]
