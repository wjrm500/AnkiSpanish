import asyncio
import os
import logging

from anki.storage import Collection
from anki.models import NotetypeDict
from anki.notes import Note

from exceptions import RateLimitException
from readable_fields import ReadableFields
from sentences import SentencePairCollection, SpanishKeyword
from spanish_dict import SpanishDictScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

spanish_dict_scraper = SpanishDictScraper()

"""
Creates a new Anki note based on the original note, but with the fields `definition`, `spanish` and
`english` populated with more accurate and consistent translation data scraped from SpanishDict. If
no translation data is found, the original note is returned unmodified.
"""
async def create_new_note(col: Collection, model: NotetypeDict, original_note: Note) -> Note:
    new_note = col.new_note(model)
    readable_fields = ReadableFields(original_note.fields)
    spanish_word = readable_fields.word
    spanish_keyword = SpanishKeyword(text=spanish_word, verb=readable_fields.part_of_speech == "v")
    sentence_pairs = await spanish_dict_scraper.sentence_pairs_from_examples_pane(spanish_keyword)
    sentence_pair_coll = SentencePairCollection(sentence_pairs)
    english_keywords = sentence_pair_coll.most_common_english_keywords()
    if english_keywords:
        spanish_sentences, english_sentences = [], []
        for english_keyword in english_keywords:
            filtered_sentence_pairs = sentence_pair_coll.filter_by_english_keyword(english_keyword)
            if not filtered_sentence_pairs:
                continue
            sentence_pair = filtered_sentence_pairs[0]
            spanish_sentences.append(sentence_pair.spanish_sentence.text)
            english_sentences.append(sentence_pair.english_sentence.text)
        readable_fields.definition = "; ".join(
            [keyword.standardize() for keyword in english_keywords]
        )
        combine_sentences = lambda sentences: (
            sentences[0] if len(sentences) == 1 else "<br>".join(
                [
                    f"<span style='color: darkgray'>[{i}]</span> {s}"
                    for i, s in enumerate(sentences, 1)
                ]
            )
        )
        readable_fields.spanish = combine_sentences(spanish_sentences)
        readable_fields.english = combine_sentences(english_sentences)
    new_note.fields = readable_fields.retrieve()
    return new_note

rate_limit_event = asyncio.Event()
rate_limit_event.set()  # Setting the event allows all coroutines to proceed
rate_limit_handling_event = asyncio.Event()
semaphore = asyncio.Semaphore(5)
"""
This function is a wrapper around `create_new_note` that ensures only three notes can be created
simultaneously, helping to avoid rate limiting by SpanishDict.
"""
async def limited_create_new_note(*args, **kwargs):
    async with semaphore:
        try:
            return await create_new_note(*args, **kwargs)
        except RateLimitException:
            # Check if this coroutine is the first to handle the rate limit
            if not rate_limit_handling_event.is_set():
                rate_limit_handling_event.set()  # Indicate that rate limit handling is in progress
                reset_time = 30
                logger.error(f"Rate limit activated. Waiting {reset_time} seconds...")
                rate_limit_event.clear()
                await asyncio.sleep(reset_time)
                while await spanish_dict_scraper.rate_limited():
                    logger.error(f"Rate limit still active. Waiting {reset_time} seconds...")
                    await asyncio.sleep(reset_time)
                rate_limit_event.set()
                rate_limit_handling_event.clear()  # Indicate that rate limit handling is complete
                logger.info("Rate limit deactivated")
            else:
                # Wait for the first coroutine to finish handling the rate limit
                await rate_limit_event.wait()
            return await create_new_note(*args, **kwargs)

"""
The main function. Creates a new Anki note for each card in the deck "A Frequency Dictionary of
Spanish", populating the fields `definition`, `spanish` and `english` with more accurate and
consistent translation data scraped from SpanishDict. The new notes are added to the deck "A
Frequency Dictionary of Spanish (Edited)". If the deck "A Frequency Dictionary of Spanish" does not
exist, the program exits.
"""
async def main():
    collection_path = "C:\\Users\\wjrm5\\AppData\\Roaming\\Anki2\\User 1\\collection.anki2"
    
    if not os.path.exists(collection_path):
        logger.error(f"Collection not found at {collection_path}")
        return

    logger.info(f"Loading collection from {collection_path}")
    col = Collection(collection_path)
    model = col.models.by_name("A Frequency Dictionary of Spanish")

    original_deck_name = "A Frequency Dictionary of Spanish"
    new_deck_name = "A Frequency Dictionary of Spanish (Edited)"

    deck_names = [deck.name for deck in col.decks.all_names_and_ids()]
    if original_deck_name in deck_names:
        if new_deck_name not in deck_names:
            logger.info(f"Creating new deck '{new_deck_name}'")
            col.decks.id(new_deck_name)  # This creates a new deck

        original_deck_id = col.decks.id(original_deck_name)
        new_deck_id = col.decks.id(new_deck_name)
        
        card_ids = col.decks.cids(original_deck_id)
        logger.info(f"Processing {len(card_ids)} cards from '{original_deck_name}'")
        tasks = []
        for cid in card_ids:
            original_card = col.get_card(cid)
            original_note = original_card.note()
            task = limited_create_new_note(col, model, original_note)
            tasks.append(task)
        
        # Process tasks as they complete
        notes_created = 0
        for task in asyncio.as_completed(tasks):
            new_note: Note = await task
            col.add_note(note=new_note, deck_id=new_deck_id)
            notes_created += 1
            logger.info(f"Note #{notes_created} added: {ReadableFields(new_note.fields).word}")

    else:
        logger.error(f"Deck '{original_deck_name}' not found")
        col.close()
        return

    col.close()
    await spanish_dict_scraper.close_session()
    logger.info(f"Processing complete. Total requests made: {spanish_dict_scraper.requests_made}")

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
