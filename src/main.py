import argparse
import asyncio
import random
from typing import List

from genanki import Deck as AnkiDeck
from genanki import Model as AnkiModel
from genanki import Note as AnkiNote
from genanki import Package as AnkiPackage

from constant import PrintColour as PC
from log import DEBUG, logger
from note_creator import NoteCreator
from scraper import SpanishDictScraper
from source import AnkiPackageSource, CSVSource, SimpleSource, Source

deck = AnkiDeck(2059400110, "Programmatically generated language learning flashcards")
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
            "qfmt": "<div style='text-align:center;'><span style='color:orange; font-size:20px; font-weight:bold'><a href='https://www.spanishdict.com/translate/{{word}}?langFrom=es' style='color: orange;'>{{word}}</a></span> <span style='color:gray;'>({{part_of_speech}})</span></div><br><div style='font-size:18px; text-align:center;'>{{source_sentences}}</div>",  # noqa: E501
            "afmt": "{{FrontSide}}<hr><div style='font-size:18px; font-weight:bold; text-align:center;'>{{definition}}</div><br><div style='font-size:18px; text-align:center;'>{{target_sentences}}</div>",  # noqa: E501
        }
    ],
)


async def main(
    concurrency_limit: int,
    words_to_translate: List[str],
    note_limit: int,
    output_to: str,
) -> None:
    """
    Creates a new Anki deck containing language learning flashcards with translations and example
    sentences for a given set of words.
    """
    if not words_to_translate:
        logger.warning("No words to translate, exiting")
        return
    scraper = SpanishDictScraper()
    note_creator = NoteCreator(model, scraper, concurrency_limit)
    logger.info(f"Processing {len(words_to_translate)} words")
    tasks: List[asyncio.Task[List[AnkiNote]]] = []
    for word_to_translate in words_to_translate:
        coro = note_creator.rate_limited_create_notes(word_to_translate)
        task = asyncio.create_task(coro)
        tasks.append(task)

    max_word_length = max([len(word) for word in words_to_translate])
    words_processed, notes_to_create = 0, 0
    all_new_notes: List[AnkiNote] = []
    try:
        for completed_task in asyncio.as_completed(tasks):
            new_notes: List[AnkiNote] = await completed_task
            words_processed += 1
            if not new_notes:
                continue
            all_new_notes.extend(new_notes)
            notes_to_create += len(new_notes)
            logger.debug(
                f"{PC.PURPLE}({words_processed:{len(str(len(tasks)))}}/{len(tasks)}){PC.RESET} - Prepared {PC.GREEN}{len(new_notes)}{PC.RESET} notes for word {PC.CYAN}{new_notes[0].fields[0]:{max_word_length}}{PC.RESET} - {PC.PURPLE}total notes to create: {notes_to_create}{PC.RESET}"  # noqa: E501
            )
            if note_limit and notes_to_create >= note_limit:
                logger.info(f"Note limit of {note_limit} reached - stopping processing")
                break
    finally:
        remaining_tasks = [task for task in tasks if not task.done()]
        for task in remaining_tasks:
            task.cancel()
        if remaining_tasks:
            # Set return_exceptions to True so that CancelledError exceptions are not raised
            await asyncio.gather(*remaining_tasks, return_exceptions=True)
        await scraper.close_session()

    logger.info(f"Shuffling {len(all_new_notes)} notes")
    random.shuffle(all_new_notes)
    for new_note in all_new_notes:
        deck.add_note(note=new_note)
        logger.debug(
            f"Created note for translation {PC.CYAN}{new_note.fields[0]} ({new_note.fields[1]}){PC.RESET}"  # noqa: E501
        )
    AnkiPackage(deck).write_to_file(output_to)
    logger.info(
        f"Processing complete. Total web requests made: {scraper.requests_made}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency-limit", type=int, default=1)
    parser.add_argument("--words", nargs="+", default=[])
    parser.add_argument("--anki-package-path", type=str, default="")
    parser.add_argument("--anki-deck-name", type=str, default="")
    parser.add_argument("--anki-field-name", type=str, default="Word")
    parser.add_argument("--csv", type=str, default="")
    parser.add_argument("--note-limit", type=int, default=0)
    parser.add_argument("--output-to", type=str, default="output.apkg")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    source: Source
    if args.words:
        source = SimpleSource(args.words)
    elif args.anki_package_path:
        source = AnkiPackageSource(
            package_path=args.anki_package_path,
            deck_name=args.anki_deck_name,
            field_name=args.anki_field_name,
        )
    elif args.csv:
        source = CSVSource(args.csv)
    else:
        logger.error("Must provide either --words, --anki-package-path or --csv")
        exit(1)
    words = source.get_words_to_translate()

    if args.verbose:
        logger.setLevel(DEBUG)

    asyncio.run(main(args.concurrency_limit, words, args.note_limit, args.output_to))
