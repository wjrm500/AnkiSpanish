import argparse
import asyncio
import os
import logging

from anki.storage import Collection as AnkiCollection
from anki.errors import DBError as AnkiDBError
from anki.notes import Note as AnkiNote

from internal_note import InternalNote
from note_creator import NoteCreator
from spanish_dict import SpanishDictScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

"""
The main function. Creates a new Anki note for each card in the deck "A Frequency Dictionary of
Spanish", populating the fields `definition`, `spanish` and `english` with more accurate and
consistent translation data scraped from SpanishDict. The new notes are added to the deck "A
Frequency Dictionary of Spanish (Edited)". If the deck "A Frequency Dictionary of Spanish" does not
exist, the program exits.
"""
async def main(access_limit: int, test_word: str):
    collection_path = "C:\\Users\\wjrm5\\AppData\\Roaming\\Anki2\\User 1\\collection.anki2"
    
    if not os.path.exists(collection_path):
        logger.error(f"Collection not found at {collection_path}")
        return

    logger.info(f"Loading collection from {collection_path}")
    try:
        coll = AnkiCollection(collection_path)
    except AnkiDBError:
        logger.error("Collection is already open in another Anki instance - is Anki running?")
        return
    model = coll.models.by_name("A Frequency Dictionary of Spanish")
    spanish_dict_scraper = SpanishDictScraper()
    note_creator = NoteCreator(coll, model, spanish_dict_scraper, access_limit)

    original_deck_name = "A Frequency Dictionary of Spanish"
    new_deck_name = "A Frequency Dictionary of Spanish (Edited)"

    deck_names = [deck.name for deck in coll.decks.all_names_and_ids()]
    if original_deck_name in deck_names:
        if new_deck_name not in deck_names:
            logger.info(f"Creating new deck '{new_deck_name}'")
            coll.decks.id(new_deck_name)  # This creates a new deck

        original_deck_id = coll.decks.id(original_deck_name)
        new_deck_id = coll.decks.id(new_deck_name)
        
        card_ids = coll.decks.cids(original_deck_id)
        logger.info(f"Processing {len(card_ids)} cards from '{original_deck_name}'")
        tasks = []
        for cid in card_ids:
            original_card = coll.get_card(cid)
            original_note = original_card.note()
            new_internal_note = InternalNote(coll, model, original_note)
            if test_word and new_internal_note.word != test_word:
                continue
            task = note_creator.create_new_note(
                new_internal_note, note_creator.create_new_note_from_dictionary
            )
            tasks.append(task)
        
        # Process tasks as they complete
        notes_created = 0
        for task in asyncio.as_completed(tasks):
            new_note: AnkiNote = await task
            coll.add_note(note=new_note, deck_id=new_deck_id)
            notes_created += 1
            logger.info(
                f"Note #{notes_created} added: {InternalNote(coll, model, new_note).word}"
            )

    else:
        logger.error(f"Deck '{original_deck_name}' not found")
        coll.close()
        return

    coll.close()
    await spanish_dict_scraper.close_session()
    logger.info(f"Processing complete. Total requests made: {spanish_dict_scraper.requests_made}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--access-limit", type=int, default=1)
    parser.add_argument("--test-word", type=str, default=None)
    args = parser.parse_args()

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(args.access_limit, args.test_word))
