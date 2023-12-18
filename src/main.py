import argparse
import asyncio
import random

from genanki import Deck as AnkiDeck
from genanki import Note as AnkiNote
from genanki import Package as AnkiPackage

from constant import Language
from constant import PrintColour as PC
from dictionary import Dictionary
from log import DEBUG, logger
from note_creator import NoteCreator
from retriever import Retriever, RetrieverFactory
from source import AnkiPackageSource, CSVSource, SimpleSource, Source


async def main(
    words_to_translate: list[str],
    retriever: Retriever,
    concurrency_limit: int = 1,
    note_limit: int = 0,
    output_anki_package_path: str = "output.apkg",
    output_anki_deck_name: str = "Language learning flashcards",
) -> None:
    """
    Creates a new Anki deck containing language learning flashcards with translations and example
    sentences for a given set of words.
    """
    if not words_to_translate:
        logger.warning("No words to translate, exiting")
        return
    deck_id = random.randint(1_000_000_000, 5_000_000_000)
    note_creator = NoteCreator(
        deck_id=deck_id,
        dictionary=Dictionary(retriever=retriever),
        concurrency_limit=concurrency_limit,
    )
    logger.info(f"Processing {len(words_to_translate)} words")
    tasks: list[asyncio.Task[list[AnkiNote]]] = []
    for word_to_translate in words_to_translate:
        coro = note_creator.rate_limited_create_notes(word_to_translate)
        task = asyncio.create_task(coro)
        tasks.append(task)

    max_word_length = max([len(word) for word in words_to_translate])
    words_processed, notes_to_create = 0, 0
    all_new_notes: list[AnkiNote] = []
    try:
        for completed_task in asyncio.as_completed(tasks):
            new_notes: list[AnkiNote] = await completed_task
            words_processed += 1
            if not new_notes:
                continue
            all_new_notes.extend(new_notes)
            notes_to_create += len(new_notes)
            logger.debug(
                f"{PC.PURPLE}({words_processed:{len(str(len(tasks)))}}/{len(tasks)}){PC.RESET} - Prepared {PC.GREEN}{len(new_notes)}{PC.RESET} notes for word {PC.CYAN}{new_notes[0].fields[1]:{max_word_length}}{PC.RESET} - {PC.PURPLE}total notes to create: {notes_to_create}{PC.RESET}"  # noqa: E501
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
        await retriever.close_session()

    if not all_new_notes:
        logger.warning("No notes to create, exiting")
        return

    logger.debug(f"Shuffling {len(all_new_notes)} notes")
    random.shuffle(all_new_notes)

    logger.info(
        f"Creating Anki deck '{output_anki_deck_name}' (ID {deck_id}) with {len(all_new_notes)} notes"  # noqa: E501
    )
    deck = AnkiDeck(deck_id, output_anki_deck_name)
    for new_note in all_new_notes:
        deck.add_note(note=new_note)
        logger.debug(
            f"Created note for translation {PC.CYAN}{new_note.fields[1]} ({new_note.fields[3]}){PC.RESET}"  # noqa: E501
        )
    AnkiPackage(deck).write_to_file(output_anki_package_path)
    logger.info(f"Processing complete. Total web requests made: {retriever.requests_made}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create Anki deck for language learning. Provide either --words, --anki-package-path or --csv as a source of words"  # noqa: E501
    )

    # Source arguments
    parser.add_argument("--words", nargs="+", default=[], help="Words to translate")
    parser.add_argument("--input-anki-package-path", type=str, default="", help="Path to .apkg")
    parser.add_argument(
        "--input-anki-deck-name", type=str, default="", help="Name of deck inside package"
    )
    parser.add_argument(
        "--input-anki-field-name", type=str, default="Word", help="Name of field inside note"
    )
    parser.add_argument("--csv", type=str, default="", help="Path to .csv")

    # Retriever arguments
    parser.add_argument(
        "--language-from",
        type=Language,
        required=True,
        help="Language to translate from",
        choices=list(Language),
    )
    parser.add_argument(
        "--language-to",
        type=Language,
        required=True,
        help="Language to translate to",
        choices=list(Language),
    )
    parser.add_argument(
        "--retriever-type",
        type=str,
        required=True,
        help="Retriever type to use. Options are 'collins', 'openai' and 'spanishdict'",
    )
    parser.add_argument(
        "--concise-mode",
        action="store_true",
        help="Concise mode changes the behaviour of the retriever to find the key definitions and remove any translations or definitions that don't correspond with these, typically leading to a smaller deck with more concise flashcards.",  # noqa: E501
    )

    # Minor arguments
    parser.add_argument(
        "--concurrency-limit",
        type=int,
        default=1,
        help="Number of coroutines to run concurrently",
    )
    parser.add_argument(
        "--note-limit", type=int, default=0, help="Maximum number of notes to create"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    # Output argument
    parser.add_argument(
        "--output-anki-package-path",
        type=str,
        default="output.apkg",
        help="Path to output Anki package (.apkg) file",
    )
    parser.add_argument(
        "--output-anki-deck-name",
        type=str,
        default="Language learning flashcards",
        help="Name of deck inside output Anki package (.apkg) file",
    )

    args = parser.parse_args()

    try:
        source: Source
        if args.words:
            source = SimpleSource(words_to_translate=args.words)
        elif (
            args.input_anki_package_path
            and args.input_anki_deck_name
            and args.input_anki_field_name
        ):
            source = AnkiPackageSource(
                package_path=args.input_anki_package_path,
                deck_name=args.input_anki_deck_name,
                field_name=args.input_anki_field_name,
            )
        elif args.csv:
            source = CSVSource(file_path=args.csv)
        else:
            raise ValueError(
                "Must provide either --words, --anki-package-path, --anki-deck-name and --anki-field-name, or --csv"  # noqa: E501
            )
        words = source.get_words_to_translate()
    except Exception as e:
        logger.error(e)
        exit(1)

    try:
        retriever = RetrieverFactory.create_retriever(
            retriever_type=args.retriever_type,
            language_from=args.language_from,
            language_to=args.language_to,
            concise_mode=args.concise_mode,
        )
    except ValueError as e:
        logger.error(e)
        exit(1)

    if args.verbose:
        logger.setLevel(DEBUG)

    asyncio.run(
        main(
            words,
            retriever,
            args.concurrency_limit,
            args.note_limit,
            args.output_anki_package_path,
            args.output_anki_deck_name,
        )
    )
