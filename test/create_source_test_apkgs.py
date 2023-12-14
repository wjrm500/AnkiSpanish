import os
import random

from genanki import Deck as AnkiDeck
from genanki import Model as AnkiModel
from genanki import Note as AnkiNote
from genanki import Package as AnkiPackage

TEST_DIR = os.path.dirname(os.path.realpath(__file__))

model_id = random.randint(1_000_000_000, 5_000_000_000)
model = AnkiModel(
    model_id,
    "Test model",
    fields=[
        {"name": "Word"},
        {"name": "Translation"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "<div>{{word}}</div>",
            "afmt": "{{FrontSide}}<hr><div>{{translation}}</div>",
        }
    ],
)


def create_populated_deck() -> None:
    deck_id = random.randint(1_000_000_000, 5_000_000_000)
    deck = AnkiDeck(deck_id, "Populated deck")
    notes = [
        AnkiNote(model=model, fields=["hola", "hello"]),
        AnkiNote(model=model, fields=["adiós", "goodbye"]),
    ]
    for note in notes:
        deck.add_note(note)
    AnkiPackage(deck).write_to_file(TEST_DIR + "/data/populated_deck.apkg")


def create_empty_deck() -> None:
    deck_id = random.randint(1_000_000_000, 5_000_000_000)
    deck = AnkiDeck(deck_id, "Empty deck")
    AnkiPackage(deck).write_to_file(TEST_DIR + "/data/empty_deck.apkg")


if __name__ == "__main__":
    create_populated_deck()
    create_empty_deck()
