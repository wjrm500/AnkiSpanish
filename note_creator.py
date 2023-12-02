import asyncio
import logging
from typing import Callable, List

from anki.storage import Collection as AnkiCollection
from anki.models import NotetypeDict as AnkiModel
from anki.notes import Note as AnkiNote

from exceptions import RateLimitException
from internal_note import InternalNote
from sentences import EnglishKeyword, SentencePairCollection, SpanishKeyword
from spanish_dict import SpanishDictScraper

logger = logging.getLogger(__name__)

"""
A class that creates Anki notes from InternalNote objects by scraping SpanishDict for more accurate
and consistent translation data. This class also handles rate limiting, allowing only a certain
number of coroutines to access the SpanishDict website at a time.
"""
class NoteCreator:
    def __init__(
        self, coll: AnkiCollection, model: AnkiModel, spanish_dict_scraper: SpanishDictScraper,
        access_limit: int = 1
    ) -> None:
        self.coll = coll
        self.model = model
        self.spanish_dict_scraper = spanish_dict_scraper
        self.rate_limit_event = asyncio.Event()
        self.rate_limit_event.set()  # Setting the event allows all coroutines to proceed
        self.rate_limit_handling_event = asyncio.Event()
        self.semaphore = asyncio.Semaphore(access_limit)
    
    """
    Creates a new Anki note object from a given InternalNote object, representing an existing note,
    a SentencePairCollection object, representing the collection of sentence pairs scraped from
    SpanishDict for the given keyword, and a list of EnglishKeyword objects, representing the
    English keywords found on SpanishDict for the Spanish keyword, which are also used to filter the
    SentencePairCollection to find relevant sentence pairs. The InternalNote object is updated to
    include the translations and example sentences, and a new Anki note is created and returned.
    """
    def _create_new_note(
        self, internal_note: InternalNote, sentence_pair_coll: SentencePairCollection,
        english_keywords: List[EnglishKeyword]
    ) -> AnkiNote:
        if not sentence_pair_coll:
            raise ValueError("No sentence pairs received.")
        if not english_keywords:
            raise ValueError("No English keywords received.")
        spanish_sentences, english_sentences = [], []
        for keyword in english_keywords:
            filtered_sentence_pairs = sentence_pair_coll.filter_by_english_keyword(keyword)
            sentence_pair = filtered_sentence_pairs[0]
            spanish_sentences.append(sentence_pair.spanish_sentence.text)
            english_sentences.append(sentence_pair.english_sentence.text)
        internal_note.definition = "; ".join(
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
        internal_note.spanish = combine_sentences(spanish_sentences)
        internal_note.english = combine_sentences(english_sentences)
        return internal_note.create()

    """
    This note creation method uses the SpanishDict "Examples" pane to find up to twenty example
    sentence pairs for the Spanish keyword, and takes the most common English keywords found among
    the examples, and their corresponding sentence pairs, to create a new Anki note.
    """
    async def create_new_note_from_examples(
        self, internal_note: InternalNote
    ) -> AnkiNote:
        spanish_keyword = SpanishKeyword(
            text=internal_note.word, verb=internal_note.part_of_speech == "v"
        )
        sentence_pairs = await self.spanish_dict_scraper.sentence_pairs_from_examples_pane(
            spanish_keyword
        )
        sentence_pair_coll = SentencePairCollection(sentence_pairs)
        english_keywords = sentence_pair_coll.most_common_english_keywords()
        return self._create_new_note(internal_note, sentence_pair_coll, english_keywords)
    
    """
    This note creation method uses the SpanishDict "Dictionary" pane to find the primary English
    keywords provided for the Spanish keyword, as well as the example sentence pairs also provided
    in this pane, to create a new Anki note.
    """
    async def create_new_note_from_dictionary(
        self, internal_note: InternalNote
    ) -> AnkiNote:
        spanish_keyword = SpanishKeyword(
            text=internal_note.word, verb=internal_note.part_of_speech == "v"
        )
        sentence_pairs = await self.spanish_dict_scraper.sentence_pairs_from_dictionary_pane(
            spanish_keyword
        )
        sentence_pair_coll = SentencePairCollection(sentence_pairs)
        english_keywords = await self.spanish_dict_scraper.translate_from_dictionary(
            spanish_keyword
        )
        return self._create_new_note(internal_note, sentence_pair_coll, english_keywords)
    
    """
    A wrapper and interface for the two note creation methods above. This method provides rate
    limiting functionality, allowing only a certain number of coroutines to access the SpanishDict
    website at a time. If a rate limit is detected, the coroutines will wait until the rate limit
    has been lifted before proceeding. This method also handles general exceptions.
    """
    async def create_new_note(
        self, new_internal_note: InternalNote, note_creation_method: Callable
    ) -> AnkiNote:
        async with self.semaphore:
            try:
                return await note_creation_method(new_internal_note)
            except RateLimitException:
                if not self.rate_limit_handling_event.is_set():  # Check if this coroutine is the first to handle the rate limit
                    self.rate_limit_handling_event.set()  # Indicate that rate limit handling is in progress
                    reset_time = 30
                    logger.error(f"Rate limit activated. Waiting {reset_time} seconds...")
                    self.rate_limit_event.clear()
                    await asyncio.sleep(reset_time)
                    while await self.spanish_dict_scraper.rate_limited():
                        logger.error(f"Rate limit still active. Waiting {reset_time} seconds...")
                        await asyncio.sleep(reset_time)
                    self.rate_limit_event.set()
                    self.rate_limit_handling_event.clear()  # Indicate that rate limit handling is complete
                    logger.info("Rate limit deactivated")
                else:
                    await self.rate_limit_event.wait()  # Wait for the first coroutine to finish handling the rate limit
                return await note_creation_method(new_internal_note)
            except Exception as e:
                logger.error(f"Error processing '{new_internal_note.word}': {e}")
