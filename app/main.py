import argparse
import asyncio
import os
import random
import re
from datetime import datetime
from functools import partial

from genanki import Deck as AnkiDeck
from genanki import Note as AnkiNote
from genanki import Package as AnkiPackage
from setuptools_scm import get_version

from app.constant import Language
from app.constant import PrintColour as PC
from app.dictionary import Dictionary
from app.log import DEBUG, logger
from app.note_creator import NoteCreator
from app.retriever import Retriever, RetrieverFactory
from app.source import AnkiPackageSource, CSVSource, SimpleSource, Source


def valid_input_path(file_extension: str, path: str) -> str:
    assert re.match(r"\.\w{1,5}$", file_extension), "Invalid file extension format"

    if not os.path.isfile(path):  # Check if the file exists
        raise argparse.ArgumentTypeError(f"File {path} does not exist.")

    if not path.lower().endswith(file_extension):  # Check if the file has the correct extension
        raise argparse.ArgumentTypeError(f"The file must have a {file_extension} extension")

    return path


def valid_output_anki_package_path(path: str) -> str:
    if not os.path.isdir(os.path.dirname(path)):  # Check if the directory of the file exists
        raise argparse.ArgumentTypeError(f"Directory {os.path.dirname(path)} does not exist.")

    if os.path.isdir(path):  # Check if the path is not a directory
        raise argparse.ArgumentTypeError(f"{path} is a directory.")

    if not path.lower().endswith(".apkg"):  # Check if the file has a .apkg extension
        raise argparse.ArgumentTypeError("The file must have a .apkg extension")

    return path


async def create_deck(
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
                f"{PC.PURPLE}({words_processed:{len(str(len(tasks)))}}/{len(tasks)}){PC.RESET} - Prepared {PC.GREEN}{len(new_notes)}{PC.RESET} notes for word {PC.CYAN}{new_notes[0].fields[1]:{max_word_length}}{PC.RESET} - {PC.PURPLE}total notes to create: {notes_to_create}{PC.RESET}"
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
        f"Creating Anki deck '{output_anki_deck_name}' (ID {deck_id}) with {len(all_new_notes)} notes"
    )
    deck = AnkiDeck(deck_id, output_anki_deck_name)
    for new_note in all_new_notes:
        deck.add_note(note=new_note)
        logger.debug(
            f"Created note for translation {PC.CYAN}{new_note.fields[1]} ({new_note.fields[3]}){PC.RESET}"
        )
    AnkiPackage(deck).write_to_file(output_anki_package_path)
    logger.info(f"Processing complete. Total web requests made: {retriever.requests_made}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Anki deck for language learning. Provide either --words, --input-anki-package-path, --input-anki-deck-name and --input-anki-field-name, or --csv as a source of words"
    )

    # Source arguments
    valid_csv = partial(valid_input_path, ".csv")
    valid_anki_package = partial(valid_input_path, ".apkg")
    source_group = parser.add_argument_group(title="Source arguments")
    source_group.add_argument("--words", nargs="+", default=[], help="Words to translate")
    source_group.add_argument(
        "--input-anki-package-path",
        type=valid_anki_package,
        default=None,
        help="Path to Anki package (.apkg) file containing words to translate",
    )
    source_group.add_argument(
        "--input-anki-deck-name",
        type=str,
        default="",
        help="Name of deck inside Anki package containing words to translate",
    )
    source_group.add_argument(
        "--input-anki-field-name",
        type=str,
        default="Word",
        help="Name of field inside note inside deck inside Anki package containing words to translate",
    )
    source_group.add_argument(
        "--csv",
        type=valid_csv,
        default=None,
        help="Path to CSV (.csv) file containing words to translate",
    )
    source_group.add_argument(
        "--skip-first-row",
        action="store_true",
        help="Skip first row in CSV (.csv) file containing words to transdlate",
    )
    source_group.add_argument(
        "--col-num",
        type=int,
        default=0,
        help="Column number in CSV (.csv) file containing words to translate",
    )

    # Retriever arguments
    retriever_group = parser.add_argument_group(title="Retriever arguments")
    retriever_group.add_argument(
        "-lf",
        "--language-from",
        type=Language,
        required=True,
        help="Language to translate from",
        choices=list(Language),
    )
    retriever_group.add_argument(
        "-lt",
        "--language-to",
        type=Language,
        required=True,
        help="Language to translate to",
        choices=list(Language),
    )
    retriever_group.add_argument(
        "-rt",
        "--retriever-type",
        type=str,
        required=True,
        help="Retriever type to use. Options are 'collins', 'openai', 'spanishdict' and 'wordreference'",
    )
    retriever_group.add_argument(
        "-cm",
        "--concise-mode",
        action="store_true",
        help="Concise mode changes the behaviour of the retriever to prune translations and definitions, typically leading to a smaller deck with more concise flashcards.",
    )

    # Note creator arguments
    note_creator_group = parser.add_argument_group(title="Note creator arguments")
    note_creator_group.add_argument(
        "-cl",
        "--concurrency-limit",
        type=int,
        default=1,
        help="Number of coroutines to run concurrently when fetching data. Minimum of 1, maximum of 5. Defaults to 1",
    )

    # Output arguments
    output_group = parser.add_argument_group(title="Output arguments")
    output_group.add_argument(
        "-op",
        "--output-anki-package-path",
        type=valid_output_anki_package_path,
        default=None,
        help="Path to output Anki package (.apkg) file",
    )
    output_group.add_argument(
        "-od",
        "--output-anki-deck-name",
        type=str,
        default="",
        help="Name of deck inside output Anki package (.apkg) file",
    )

    # Miscellaneous arguments
    misc_group = parser.add_argument_group(title="Miscellaneous arguments")
    misc_group.add_argument(
        "-nl", "--note-limit", type=int, default=0, help="Maximum number of notes to create"
    )
    misc_group.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    misc_group.add_argument(
        "--version",
        action="version",
        version=f"lexideck {get_version()}",
        help="Show version number and exit",
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
            source = CSVSource(
                file_path=args.csv,
                skip_first_row=args.skip_first_row,
                col_num=args.col_num,
            )
        else:
            raise ValueError(
                "Must provide either --words, --anki-package-path, --anki-deck-name and --anki-field-name, or --csv"
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
    except Exception as e:
        logger.error(e)
        exit(1)

    current_date = datetime.now().strftime("%Y-%m-%d")
    if not args.output_anki_package_path:
        args.output_anki_package_path = f"{args.language_from.value}-{args.language_to.value}-{args.retriever_type}-{current_date}.apkg"
    if not args.output_anki_deck_name:
        args.output_anki_deck_name = f"{args.language_from.value.capitalize()} to {args.language_to.value.capitalize()} ({args.retriever_type} - {current_date})"

    if args.verbose:
        logger.setLevel(DEBUG)

    asyncio.run(
        create_deck(
            words,
            retriever,
            args.concurrency_limit,
            args.note_limit,
            args.output_anki_package_path,
            args.output_anki_deck_name,
        )
    )


if __name__ == "__main__":
    main()
