import copy
import os
import logging
from typing import List

from anki.storage import Collection
from anki.models import NotetypeDict
from anki.notes import Note

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# A class to make field manipulation more readable
class ReadableFields:
    rank: str
    word: str
    part_of_speech: str
    definition: str
    spanish: str
    english: str
    freq: str

    def __init__(self, fields: List) -> None:
        self.rank = fields[0]
        self.word = fields[1]
        self.part_of_speech = fields[2]
        self.definition = fields[3]
        self.spanish = fields[4]
        self.english = fields[5]
        self.freq = fields[6]
    
    def retrieve(self) -> List:
        return [
            self.rank,
            self.word,
            self.part_of_speech,
            self.definition,
            self.spanish,
            self.english,
            self.freq
        ]

# A function to create a new note from an existing note
def create_new_note(col: Collection, model: NotetypeDict, original_note: Note) -> Note:
    new_note = col.new_note(model)
    readable_fields = ReadableFields(original_note.fields)
    # readable_fields.definition = "Test"
    new_note.fields = readable_fields.retrieve()

# The main function
def main():
    collection_path = "C:\\Users\\wjrm5\\AppData\\Roaming\\Anki2\\User 1\\collection.anki2"
    
    if not os.path.exists(collection_path):
        logger.error(f"Collection not found at {collection_path}")
        return

    # Load the collection
    logger.info(f"Loading collection from {collection_path}")
    col = Collection(collection_path)

    # Check for deck existence and create if necessary
    original_deck_name = "A Frequency Dictionary of Spanish"
    new_deck_name = "A Frequency Dictionary of Spanish (Edited)"

    if original_deck_name in col.decks.all_names():
        if new_deck_name not in col.decks.all_names():
            logger.info(f"Creating new deck '{new_deck_name}'")
            col.decks.id(new_deck_name)  # This creates a new deck

        # Process cards in the original deck
        original_deck_id = col.decks.id(original_deck_name)
        new_deck_id = col.decks.id(new_deck_name)
        card_ids = col.decks.cids(original_deck_id)

        logger.info(f"Processing {len(card_ids)} cards from '{original_deck_name}'")
        model = col.models.by_name("A Frequency Dictionary of Spanish")
        for cid in card_ids:
            original_card = col.get_card(cid)
            new_note = create_new_note(col, model, original_card.note())
            col.add_note(note=new_note, deck_id=new_deck_id)

    else:
        logger.error(f"Deck '{original_deck_name}' not found")
        col.close()
        return

    # Save changes and close the collection
    col.save()
    col.close()
    logger.info("Processing complete")

if __name__ == "__main__":
    main()
