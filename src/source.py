import abc
import csv
import os

from genanki import Model as AnkiModel
from genanki import Note as AnkiNote

from genanki_extension import load_decks_from_package


class Source(abc.ABC):
    """An abstract base class that represents a source of words to be translated."""

    def _deduplicate(self, words_to_translate: list[str]) -> list[str]:
        """Removes duplicates from a list of words."""
        seen = set()
        unique_words: list[str] = []
        for word in words_to_translate:
            if word not in seen:
                seen.add(word)
                unique_words.append(word)
        return unique_words

    @abc.abstractmethod
    def get_words_to_translate(self) -> list[str]:
        """Abstract method to get a list of words from the source."""
        raise NotImplementedError


class SimpleSource(Source):
    """Source class for getting words from a simple list"""

    words_to_translate: list[str]

    def __init__(self, words_to_translate: list[str]) -> None:
        self.words_to_translate = words_to_translate

    def get_words_to_translate(self) -> list[str]:
        """Simply returns a de-duplicated list of the words provided to the constructor."""
        return self._deduplicate(self.words_to_translate)


class AnkiPackageSource(Source):
    """Source class for getting words from an Anki package."""

    package_path: str
    deck_name: str | None
    field_name: str

    def __init__(
        self, package_path: str, deck_name: str | None = None, field_name: str = "Word"
    ) -> None:
        if not os.path.exists(package_path):
            raise FileNotFoundError(f"Package not found at {package_path}")
        self.package_path = package_path
        self.deck_name = deck_name
        self.field_name = field_name

    def get_words_to_translate(self) -> list[str]:
        """
        Gets words from an Anki package. The words are extracted from the specified deck, and the
        field name is used to determine which field to get the words from for each note.
        """
        decks = load_decks_from_package(self.package_path)
        deck = next(
            (d for d in decks if not self.deck_name or d.name == self.deck_name), None
        )  # If no deck name is specified, use the first deck
        if not deck:
            raise ValueError(f"Deck '{self.deck_name}' not found in package")
        if len(deck.notes) == 0:
            raise ValueError(f"Deck '{deck.name}' has no notes")
        signal_note: AnkiNote = deck.notes[0]
        model: AnkiModel = signal_note.model
        desired_field = next(
            (f for f in model.fields if f["name"]["name"] == self.field_name), None
        )
        if not desired_field:
            raise ValueError(f"Field '{self.field_name}' not found in model")
        field_index = model.fields.index(desired_field)
        words_to_translate = []
        for note in deck.notes:
            assert isinstance(note, AnkiNote)
            words_to_translate.append(note.fields[field_index])
        return self._deduplicate(words_to_translate)


class CSVSource(Source):
    """Source class for getting words from a CSV file."""

    file_path: str
    col_num: int

    def __init__(self, file_path: str, col_num: int = 0) -> None:
        self.file_path = file_path
        self.col_num = col_num

    def get_words_to_translate(self) -> list[str]:
        """
        Gets a list of words from a CSV file. The CSV file should have one word per row, with the
        word in the first column.
        """
        words_to_translate = []
        with open(self.file_path, mode="r", encoding="utf-8") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                words_to_translate.append(row[self.col_num])
        return self._deduplicate(words_to_translate)
