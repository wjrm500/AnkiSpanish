import logging

from anki.storage import Collection

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Path to Anki collection
collection_path = "C:\\Users\\wjrm5\\AppData\\Roaming\\Anki2\\User 1\\collection.anki2"

# Function to modify cards (empty for now)
def modify_card(card):
    pass

try:
    # Open the collection
    collection = Collection(collection_path, log=True)
    logger.info("Opened the collection.")

    # Check for the existence of the decks
    original_deck_name = "A Frequency Dictionary of Spanish"
    edited_deck_name = "A Frequency Dictionary of Spanish (Edited)"

    original_deck_id = collection.decks.id(original_deck_name, create=False)
    edited_deck_id = collection.decks.id(edited_deck_name, create=False)

    if edited_deck_id:
        logger.info(f"Deck '{edited_deck_name}' already exists.")
    else:
        if original_deck_id:
            logger.info(f"Deck '{original_deck_name}' found. Creating a copy named '{edited_deck_name}'.")
            # Copy the deck
            collection.decks.copy(original_deck_id, edited_deck_name)
            edited_deck_id = collection.decks.id(edited_deck_name)
            # Copy cards from the original deck to the new deck
            card_ids = collection.find_cards(f"'deck:{original_deck_id}'")
            for card_id in card_ids:
                card = collection.get_card(card_id)
                card.did = edited_deck_id
                card.flush()
        else:
            logger.error(f"Deck '{original_deck_name}' not found. Exiting script.")
            raise Exception(f"Deck '{original_deck_name}' not found.")

    # Iterate over the cards in the copied deck
    for cid in collection.find_cards(f"'deck:{edited_deck_name}'"):
        card = collection.get_card(cid)
        modify_card(card)  # Call the modify_card function on each card

    # Save the changes and close the collection
    collection.save()
    collection.close()
    logger.info("Changes saved and collection closed.")

except Exception as e:
    logger.error(f"An error occurred: {e}")

finally:
    if "collection" in locals():
        collection.close()
        logger.info("Collection closed.")
