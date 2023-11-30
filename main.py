import os
import logging

from anki.storage import Collection
from anki.models import NotetypeDict
from anki.notes import Note

from readable_fields import ReadableFields
from spanish_dict import SpanishDictScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

spanish_dict_scraper = SpanishDictScraper()

def create_new_note(col: Collection, model: NotetypeDict, original_note: Note) -> Note:
    new_note = col.new_note(model)
    readable_fields = ReadableFields(original_note.fields)
    spanish_word = readable_fields.word
    english_translations = spanish_dict_scraper.example_translate(spanish_word)
    if english_translations:
        spanish_sentences, english_sentences = [], []
        for english_translation in english_translations:
            new_spanish_sentence, new_english_sentence = spanish_dict_scraper.sentence_example(
                spanish_word, english_translation
            )
            spanish_sentences.append(new_spanish_sentence)
            english_sentences.append(new_english_sentence)
        readable_fields.definition = "; ".join(english_translations)
        combine_sentences = lambda sentences: (
            sentences[0] if len(sentences) == 1 else "<br>".join(
                [f"<span style='color: darkgray'>[{i}]</span> {s}" for i, s in enumerate(sentences, 1)]
            )
        )
        readable_fields.spanish = combine_sentences(spanish_sentences)
        readable_fields.english = combine_sentences(english_sentences)
    new_note.fields = readable_fields.retrieve()
    return new_note

def main():
    collection_path = "C:\\Users\\wjrm5\\AppData\\Roaming\\Anki2\\User 1\\collection.anki2"
    
    if not os.path.exists(collection_path):
        logger.error(f"Collection not found at {collection_path}")
        return

    logger.info(f"Loading collection from {collection_path}")
    col = Collection(collection_path)

    original_deck_name = "A Frequency Dictionary of Spanish"
    new_deck_name = "A Frequency Dictionary of Spanish (Edited)"

    if original_deck_name in col.decks.all_names():
        if new_deck_name not in col.decks.all_names():
            logger.info(f"Creating new deck '{new_deck_name}'")
            col.decks.id(new_deck_name)  # This creates a new deck

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

    col.close()
    logger.info("Processing complete")

if __name__ == "__main__":
    main()
