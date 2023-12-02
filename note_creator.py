import asyncio
import logging
from typing import Callable, List

from anki.storage import Collection as AnkiCollection
from anki.models import NotetypeDict
from anki.notes import Note

from exceptions import RateLimitException
from readable_fields import ReadableFields
from sentences import EnglishKeyword, SentencePairCollection, SpanishKeyword
from spanish_dict import SpanishDictScraper

logger = logging.getLogger(__name__)

class NoteCreator:
    def __init__(
        self, coll: AnkiCollection, model: NotetypeDict, spanish_dict_scraper: SpanishDictScraper,
        access_limit: int = 1
    ) -> None:
        self.coll = coll
        self.model = model
        self.spanish_dict_scraper = spanish_dict_scraper
        self.rate_limit_event = asyncio.Event()
        self.rate_limit_event.set()  # Setting the event allows all coroutines to proceed
        self.rate_limit_handling_event = asyncio.Event()
        self.semaphore = asyncio.Semaphore(access_limit)
    
    def _create_new_note(
        self, readable_fields: ReadableFields, sentence_pair_coll: SentencePairCollection,
        english_keywords: List[EnglishKeyword]
    ) -> Note:
        spanish_sentences, english_sentences = [], []
        for keyword in english_keywords:
            filtered_sentence_pairs = sentence_pair_coll.filter_by_english_keyword(keyword)
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
        new_note = self.coll.new_note(self.model)
        new_note.fields = readable_fields.retrieve()
        return new_note

    async def create_new_note_from_examples(
        self, readable_fields: ReadableFields
    ) -> Note:
        spanish_keyword = SpanishKeyword(
            text=readable_fields.word, verb=readable_fields.part_of_speech == "v"
        )
        sentence_pairs = await self.spanish_dict_scraper.sentence_pairs_from_examples_pane(
            spanish_keyword
        )
        sentence_pair_coll = SentencePairCollection(sentence_pairs)
        english_keywords = sentence_pair_coll.most_common_english_keywords()
        return self._create_new_note(readable_fields, sentence_pair_coll, english_keywords)
    
    async def create_new_note_from_dictionary(
        self, readable_fields: ReadableFields
    ) -> Note:
        spanish_keyword = SpanishKeyword(
            text=readable_fields.word, verb=readable_fields.part_of_speech == "v"
        )
        sentence_pairs = await self.spanish_dict_scraper.sentence_pairs_from_dictionary_pane(
            spanish_keyword
        )
        sentence_pair_coll = SentencePairCollection(sentence_pairs)
        english_keywords = await self.spanish_dict_scraper.translate_from_dictionary(
            spanish_keyword
        )
        return self._create_new_note(readable_fields, sentence_pair_coll, english_keywords)
    
    async def create_new_note(
        self, original_note: Note, note_creation_method: Callable
    ) -> Note:
        readable_fields = ReadableFields(original_note.fields)
        async with self.semaphore:
            try:
                return await note_creation_method(readable_fields)
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
                return await note_creation_method(readable_fields)
            except Exception:
                logger.error(f"Error processing '{readable_fields.word}'")