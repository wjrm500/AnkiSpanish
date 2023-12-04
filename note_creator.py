import asyncio
import logging
from typing import List

from genanki import Model as AnkiModel, Note as AnkiNote

from exceptions import RateLimitException
from scraper import Scraper
from translation import Translation

logger = logging.getLogger(__name__)

"""
A class responsible for creating AnkiNote objects from Translation objects. This class coordinates
the process of getting from a word to a list of notes, by first using a Scraper subclass to generate
a list of Translation objects for the word, and then calling an internal method to convert each
Translation object into an AnkiNote object.
"""
class NoteCreator:
    def __init__(self, model: AnkiModel, scraper: Scraper, concurrency_limit: int = 1) -> None:
        self.model = model
        self.scraper = scraper
        self.rate_limit_event = asyncio.Event()
        self.rate_limit_event.set()  # Setting the event allows all coroutines to proceed
        self.rate_limit_handling_event = asyncio.Event()
        self.semaphore = asyncio.Semaphore(concurrency_limit)
    
    """
    Combines a list of sentences into a single string, with each sentence on a new line and prefixed
    with its index.
    """
    def _combine_sentences(self, sentences: List[str]) -> str:
        if len(sentences) == 1:
            return sentences[0]
        else:
            return "<br>".join(
                [
                    f"<span style='color: darkgray'>[{i}]</span> {s}"
                    for i, s in enumerate(sentences, 1)
                ]
            )
    
    """
    Creates an AnkiNote object from a given Translation object. This method is responsible for
    taking the data retrieved from the website and converting it into an AnkiNote object. There is
    a one-to-one relationship between translations and notes.
    """
    def _create_note_from_translation(self, translation: Translation) -> AnkiNote:
        source_sentences, target_sentences = [], []
        for definition in translation.definitions:
            source_sentences.append(definition.sentence_pairs[0].source_sentence)
            target_sentences.append(definition.sentence_pairs[0].target_sentence)
        
        field_dict = {
            "word": translation.word_to_translate,
            "part_of_speech": translation.part_of_speech,
            "definition": ", ".join([d.text for d in translation.definitions]),
            "source_sentences": self._combine_sentences(source_sentences),
            "target_sentences": self._combine_sentences(target_sentences),
        }
        return AnkiNote(
            model=self.model,
            fields=list(field_dict.values()),
        )
    
    """
    Creates a list of AnkiNote objects from a given word. This method coordinates the process of
    getting from a word to a list of notes, by first using a Scraper subclass to generate a list of
    Translation objects for the word, and then calling an internal method to convert each
    Translation object into an AnkiNote object.
    """
    async def create_notes(self, word_to_translate: str) -> List[AnkiNote]:
        translations = await self.scraper.translate(word_to_translate)
        # Filter translations?
        return [self._create_note_from_translation(t) for t in translations]
    
    """
    A wrapper and interface for the note creation method above. This method provides rate limiting
    functionality, allowing only a certain number of coroutines to access the scraper at a time. If
    a rate limit is detected, the coroutines will wait until the rate limit has been lifted before
    proceeding. This method also handles general exceptions.
    """
    async def rate_limited_create_notes(self, word_to_translate: str) -> List[AnkiNote]:
        async with self.semaphore:
            try:
                return await self.create_notes(word_to_translate)
            except RateLimitException:
                if not self.rate_limit_handling_event.is_set():  # Check if this coroutine is the first to handle the rate limit
                    self.rate_limit_handling_event.set()  # Indicate that rate limit handling is in progress
                    reset_time = 30
                    logger.warning(f"Rate limit activated. Waiting {reset_time} seconds...")
                    self.rate_limit_event.clear()
                    await asyncio.sleep(reset_time)
                    while await self.scraper.rate_limited():
                        logger.warning(f"Rate limit still active. Waiting {reset_time} seconds...")
                        await asyncio.sleep(reset_time)
                    self.rate_limit_event.set()
                    self.rate_limit_handling_event.clear()  # Indicate that rate limit handling is complete
                    logger.info("Rate limit deactivated")
                else:
                    await self.rate_limit_event.wait()  # Wait for the first coroutine to finish handling the rate limit
                return await self.create_notes(word_to_translate)
            except Exception as e:
                logger.error(f"Error processing '{word_to_translate}': {e}")
                return []