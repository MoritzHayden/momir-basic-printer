import configparser
from pathlib import Path
from printer import Printer
from scryfall import Scryfall
import logging
import readline
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
config = configparser.ConfigParser()
config.read(Path(__file__).resolve().with_name('config.ini'))
printer = Printer(config['PRINTER'])
scryfall = Scryfall(config['SCRYFALL'])


def settings_loop():
    # TODO: Implement
    pass

def print_loop():
    while True:
        try:
            logger.debug(f"Starting print loop...")
            cmc = int(input("~/MBP/PRINT: ").strip())
            logger.debug(f"Fetching card with CMC: {cmc}...")
            card = scryfall.get_random_card_by_cmc(cmc)
            logger.debug(f"Fetched card with CMC: {cmc} - {card['name']}. Printing...")
            printer.print_card(card)
            logger.debug(f"Printed card with CMC: {cmc} - {card['name']}.")
            # TODO: Get valid CMC range
            match cmc:
                case 'b' | 'back':
                    logger.debug(f"Received back command. Returning to main menu...")
                    break
                case _:
                    logger.debug(f"Received unknown command. Continuing print loop...")
        except (KeyboardInterrupt, EOFError):
            logger.debug("Received exit signal. Exiting...")
            break

def main():
    while True:
        try:
            logger.debug("Entered main menu. Awaiting command...")
            command = input("~/MBP/MAIN: ").strip().lower()
            match command:
                case 's' | 'settings':
                    logger.debug("Received settings command.")
                    settings_loop()
                case 'r' | 'refresh':
                    logger.debug("Received refresh command. Refreshing card data...")
                    scryfall.refresh_card_data()
                    logger.debug("Refreshed card data.")
                case 'p' | 'print':
                    logger.debug(f"Received print command.")
                    print_loop()
                case 'q' | 'quit':
                    logger.debug(f"Received exit command. Exiting...")
                    break
                case _:
                    logger.warning("Unknown command.")
        except (KeyboardInterrupt, EOFError):
            logger.debug("Received exit signal. Exiting...")
            break


if __name__ == "__main__":
    main()
