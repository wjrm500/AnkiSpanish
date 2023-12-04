import argparse
import asyncio
import os
import logging
from typing import List

from genanki import Deck as AnkiDeck, Model as AnkiModel, Note as AnkiNote, Package as AnkiPackage

from note_creator import NoteCreator
from scraper import SpanishDictScraper

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def get_words_to_translate_from__A_Frequency_Dictionary_of_Spanish__anki_deck() -> List[str]:
    from anki.collection import Collection as AnkiCollection
    from anki.errors import DBError as AnkiDBError

    collection_path = "C:\\Users\\wjrm5\\AppData\\Roaming\\Anki2\\User 1\\collection.anki2"
    original_deck_name = "A Frequency Dictionary of Spanish"
    
    if not os.path.exists(collection_path):
        logger.error(f"Collection not found at {collection_path}")
        return

    logger.info(f"Loading collection from {collection_path}")
    try:
        coll = AnkiCollection(collection_path)
    except AnkiDBError:
        logger.error("Collection is already open in another Anki instance - is Anki running?")
        return

    card_ids = coll.decks.cids(coll.decks.id(original_deck_name))
    logger.info(f"Processing {len(card_ids)} cards from '{original_deck_name}'")
    words_to_translate = []
    for cid in card_ids:
        original_card = coll.get_card(cid)
        word_to_translate = original_card.note().fields[1]
        words_to_translate.append(word_to_translate)
    return list(set(words_to_translate))

async def main(access_limit: int, words_to_translate: List[str], test: bool) -> None:
    if not words_to_translate:
        words_to_translate = get_words_to_translate_from__A_Frequency_Dictionary_of_Spanish__anki_deck()
    scraper = SpanishDictScraper()
    deck = AnkiDeck(
        2059400110,
        "Programmatically generated language learning flashcards"
    )
    model = AnkiModel(
        1098765432,
        "Language learning flashcard model",
        fields=[
            {"name": "word"},
            {"name": "part_of_speech"},
            {"name": "definition"},
            {"name": "source_sentences"},
            {"name": "target_sentences"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": "<div style='text-align:center;'><span style='color:orange; font-size:20px; font-weight:bold'>{{word}}</span> <span style='color:gray;'>({{part_of_speech}})</span></div><br><div style='font-size:18px; text-align:center;'>{{source_sentences}}</div>",
                "afmt": "{{FrontSide}}<hr><div style='font-size:18px; font-weight:bold; text-align:center;'>{{definition}}</div><br><div style='font-size:18px; text-align:center;'>{{target_sentences}}</div>",
            }
        ],
    )
    note_creator = NoteCreator(model, scraper, access_limit)

    logger.info(f"Processing {len(words_to_translate)} words")
    tasks = []
    for word_to_translate in words_to_translate:
        task = note_creator.rate_limited_create_notes(word_to_translate)
        tasks.append(task)
    
    words_processed, notes_added = 0, 0
    for task in asyncio.as_completed(tasks):
        new_notes: List[AnkiNote] = await task
        words_processed += 1
        if not new_notes:
            continue
        if not test:
            for new_note in new_notes:
                deck.add_note(note=new_note)
        notes_added += len(new_notes)
        logger.debug(f"Added {len(new_notes)} notes for word {new_notes[0].fields[0]} ({words_processed}/{len(tasks)})")
    
    AnkiPackage(deck).write_to_file("output.apkg")

    await scraper.close_session()
    logger.info(f"Processing complete. Total requests made: {scraper.requests_made}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--access-limit", type=int, default=1)
    parser.add_argument("--words", nargs="+", default=[])
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(args.access_limit, args.words, args.test))
