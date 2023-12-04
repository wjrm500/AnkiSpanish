import json
import sqlite3
import zipfile
from typing import Any, Dict, List

from genanki import Deck, Model, Note


def load_decks_from_package(apkg_filepath: str) -> List[Deck]:
    """
    A custom extension to the genanki library that allows for the loading of Anki decks from .apkg
    files. Should look into submitting a pull request to the genanki library to add this
    functionality to the library itself.
    """
    with zipfile.ZipFile(apkg_filepath, "r") as z:
        z.extractall("/tmp")  # Extracts to a temporary directory
        db_path = "/tmp/collection.anki2"  # Path to the SQLite database

    # Connect to the SQLite Database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fetch Decks
    cursor.execute("SELECT decks FROM col")
    decks_json = cursor.fetchone()[0]
    decks_data: Dict[str, Dict[str, Any]] = json.loads(decks_json)

    # Fetch Models
    cursor.execute("SELECT models FROM col")
    models_json = cursor.fetchone()[0]
    models_data: Dict[str, Dict[str, Any]] = json.loads(models_json)

    # Create Deck Objects
    loaded_decks: List[Deck] = []
    for deck_id, deck_info in decks_data.items():
        if deck_id == "1":
            continue
        deck = Deck(deck_id=deck_id, name=deck_info["name"])

        # Fetch Notes for this Deck
        cursor.execute(
            "SELECT id, mid, flds FROM notes WHERE id IN (SELECT nid FROM cards WHERE did=?)",
            (deck_id,),
        )
        notes = cursor.fetchall()

        # Create Note Objects
        for _, model_id, flds in notes:
            model_data = models_data[str(model_id)]
            model = Model(
                model_id=model_id,
                name=model_data["name"],
                fields=[{"name": fn} for fn in model_data["flds"]],
            )
            note = Note(model=model, fields=flds.split("\x1f"))
            deck.add_note(note)

        loaded_decks.append(deck)

    conn.close()
    return loaded_decks


if __name__ == "__main__":
    decks = load_decks_from_package("output.apkg")
    for deck in decks:
        print(f"Deck '{deck.name}' has {len(deck.notes)} notes")
