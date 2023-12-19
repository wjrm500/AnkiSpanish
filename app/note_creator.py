import asyncio

from genanki import Model as AnkiModel
from genanki import Note as AnkiNote

from app.dictionary import Dictionary
from app.exception import RateLimitException
from app.language_element import Translation
from app.log import logger

model = AnkiModel(
    1098765432,
    "Language learning flashcard model",
    fields=[
        {"name": "deck_id"},
        {"name": "word_to_translate"},
        {"name": "word_to_translate_html"},
        {"name": "part_of_speech"},
        {"name": "definition_html"},
        {"name": "source_sentences"},
        {"name": "target_sentences"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "<div style='text-align:center;'><span style='font-size:20px; font-weight:bold'>{{word_to_translate_html}}</span> <span style='color:gray;'>({{part_of_speech}})</span></div><br><div style='font-size:18px; text-align:center;'>{{source_sentences}}</div>",  # noqa: E501
            "afmt": "{{FrontSide}}<hr><div style='font-size:18px; font-weight:bold; text-align:center;'>{{definition_html}}</div><br><div style='font-size:18px; text-align:center;'>{{target_sentences}}</div>",  # noqa: E501
        }
    ],
)


class NoteCreator:
    """
    A class responsible for coordinating the process of getting from a word to a list of Anki notes.
    It achieves this by first using a Dictionary to retrieve a list of Translation objects for the
    word, and then calling an internal method to convert each Translation object into an AnkiNote
    object.
    """

    deck_id: int
    dictionary: Dictionary
    rate_limit_event: asyncio.Event
    rate_limit_handling_event: asyncio.Event
    semaphore: asyncio.Semaphore

    def __init__(self, deck_id: int, dictionary: Dictionary, concurrency_limit: int = 1) -> None:
        self.deck_id = deck_id
        self.dictionary = dictionary
        self.rate_limit_event = asyncio.Event()
        self.rate_limit_event.set()  # Setting the event allows all coroutines to proceed
        self.rate_limit_handling_event = asyncio.Event()
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    def _combine_sentences(self, sentences: list[str]) -> str:
        """
        Combines a list of sentences into a single piece of HTML, with each sentence on a new line
        and prefixed with its index in dark gray font.
        """
        if len(sentences) == 1:
            return sentences[0]
        else:
            return "<br>".join(
                [
                    f"<span style='color: darkgray'>[{i}]</span> {s}"
                    for i, s in enumerate(sentences, 1)
                ]
            )

    def _create_note_from_translation(self, translation: Translation) -> AnkiNote:
        """Creates an AnkiNote object from a given Translation object."""
        source_sentences, target_sentences = [], []
        for definition in translation.definitions:
            source_sentences.append(definition.sentence_pairs[0].source_sentence)
            target_sentences.append(definition.sentence_pairs[0].target_sentence)

        word_to_translate_html = (
            (
                f"<a href='{lang_from_url}' style='color:red;'>{translation.word_to_translate}</a>"
                if (lang_from_url := translation.retriever.link(translation.word_to_translate))
                else translation.word_to_translate
            )
            if translation.retriever
            else translation.word_to_translate
        )
        definition_html_components = []
        for definition in translation.definitions:
            if definition.translation.retriever:
                link = definition.translation.retriever.reverse_link(definition.text)
                if link:
                    definition_html_components.append(
                        f"<a href='{link}' style='color:green;'>{definition.text}</a>"
                    )
                    continue
            definition_html_components.append(definition.text)
        definition_html = ", ".join(definition_html_components)
        field_dict = {
            "deck_id": str(
                self.deck_id
            ),  # Makes note unique to help Anki avoid updating existing notes on import
            "word_to_translate": translation.word_to_translate,
            "word_to_translate_html": word_to_translate_html,
            "part_of_speech": translation.part_of_speech,
            "definition_html": definition_html,
            "source_sentences": self._combine_sentences(source_sentences),
            "target_sentences": self._combine_sentences(target_sentences),
        }
        return AnkiNote(
            model=model,
            fields=list(field_dict.values()),
        )

    async def create_notes(self, word_to_translate: str) -> list[AnkiNote]:
        """
        Creates a list of AnkiNote objects from a given word. This method coordinates the process of
        getting from a word to a list of Anki notes, by first using a Dictionary to retrieve a list
        of Translation objects for the word, and then calling an internal method to convert each
        Translation object into an AnkiNote object.
        """
        translations = await self.dictionary.translate(word_to_translate)
        if not translations:
            logger.warning(f"No translations found for '{word_to_translate}'")
            return []
        return [self._create_note_from_translation(t) for t in translations]

    async def rate_limited_create_notes(self, word_to_translate: str) -> list[AnkiNote]:
        """
        A wrapper and interface for the note creation method create_notes. This wrapper method
        provides rate limiting functionality, allowing only a certain number of coroutines to access
        the dictionary at a time. If a rate limit is detected, the coroutines will wait until the
        rate limit has been lifted before proceeding. This method also handles general exceptions.
        """
        async with self.semaphore:
            try:
                return await self.create_notes(word_to_translate)
            except RateLimitException:
                # Check if this coroutine is the first to handle the rate limit
                if not self.rate_limit_handling_event.is_set():
                    # Indicate that rate limit handling is in progress
                    self.rate_limit_handling_event.set()
                    reset_time = 30
                    logger.warning(f"Rate limit activated. Waiting {reset_time} seconds...")
                    self.rate_limit_event.clear()
                    await asyncio.sleep(reset_time)
                    assert self.dictionary.retriever is not None
                    while await self.dictionary.retriever.rate_limited():
                        logger.warning(f"Rate limit still active. Waiting {reset_time} seconds...")
                        await asyncio.sleep(reset_time)
                    self.rate_limit_event.set()

                    # Indicate that rate limit handling is complete
                    self.rate_limit_handling_event.clear()
                    logger.info("Rate limit deactivated")
                else:
                    # Wait for the first coroutine to finish handling the rate limit
                    await self.rate_limit_event.wait()
                return await self.create_notes(word_to_translate)
            except Exception as e:
                logger.error(f"Error processing '{word_to_translate}': {e}")
                return []


__all__ = ["model", "NoteCreator"]
