import argparse
import json
import os
import sqlite3
import zipfile
from typing import Any

from genanki import Deck, Model, Note

from app.constant import PrintColour as PC


class AudioAnkiNote(Note):  # type: ignore
    """
    A custom extension to the genanki library that allows for the creation of notes with audio
    """

    audio_filepaths: list[str]

    def __init__(self, *args, audio_filepaths: list[str] = [], **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)
        self.audio_filepaths = audio_filepaths


def load_decks_from_package(apkg_filepath: str) -> list[Deck]:
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
    decks_data: dict[str, dict[str, Any]] = json.loads(decks_json)

    # Fetch Models
    cursor.execute("SELECT models FROM col")
    models_json = cursor.fetchone()[0]
    models_data: dict[str, dict[str, Any]] = json.loads(models_json)

    # Create Deck Objects
    loaded_decks: list[Deck] = []
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


def main(args: argparse.Namespace) -> None:
    """
    Allows you to quickly see what is inside an .apkg file.
    """
    try:
        if not os.path.exists(args.apkg_filepath):
            raise FileNotFoundError(f"File '{args.apkg_filepath}' does not exist")

        decks = load_decks_from_package(args.apkg_filepath)
        print(
            f"Loaded {len(decks)} deck{'s' if len(decks) > 1 else ''} from '{args.apkg_filepath}'"
        )
        print()
        for deck in decks[: args.max_display_decks]:
            print(f"{PC.GREEN}Deck '{deck.name}' has {len(deck.notes)} notes{PC.RESET}")
            for i, note in enumerate(deck.notes[: args.max_display_notes], 1):
                field_names = [field["name"]["name"] for field in note.model.fields]
                field_values = note.fields
                print(f"   {PC.YELLOW}Note {i}{PC.RESET}:")
                for field_name, field_value in list(zip(field_names, field_values))[
                    : args.max_display_fields
                ]:
                    print(
                        f"      {PC.BLUE}{field_name}{PC.RESET}: {PC.PURPLE}{field_value}{PC.RESET}"
                    )
                print()
    except Exception as e:
        print(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quickly see what is inside an .apkg file")
    parser.add_argument("--apkg-filepath", type=str, help="Path to the .apkg file")
    parser.add_argument(
        "--max-display-decks",
        type=int,
        default=1,
        help="Maximum number of decks to display notes from",
    )
    parser.add_argument(
        "--max-display-notes",
        type=int,
        default=1,
        help="Maximum number of notes to display per deck",
    )
    parser.add_argument(
        "--max-display-fields",
        type=int,
        default=None,
        help="Maximum number of fields to display per note",
    )
    args = parser.parse_args()
    main(args)
