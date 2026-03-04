import configparser
from pathlib import Path
from printer import Printer
from scryfall import Scryfall
import logging
import readline
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
config = configparser.ConfigParser()
config.read(Path(__file__).resolve().with_name('config.ini'))
printer = Printer(config['PRINTER'])
scryfall = Scryfall(config['SCRYFALL'])


def main():
    while True:
        try:
            command = input("Command: ").strip().lower()
            match command:
                case 'r':
                    logger.info("Received refresh command.")
                    logger.info("Refreshing card data...")
                    scryfall.refresh_card_data()
                    logger.info("Refreshed card data.")
                case 'p':
                    logger.info(f"Received print command.")
                    cmc = int(input("CMC: ").strip())
                    logger.info(f"Fetching card with CMC: {cmc}...")
                    card = scryfall.get_random_card_by_cmc(cmc)
                    logger.info(f"Fetched card with CMC: {cmc} - {card['name']}.")
                    logger.info(f"Printing card with CMC: {cmc} - {card['name']}...")
                    printer.print_card(card)
                    logger.info(f"Printed card with CMC: {cmc} - {card['name']}.")
                case 'e':
                    logger.info(f"Received exit command. Exiting...")
                    break
                case _:
                    logger.info("Received unknown command.")
        except (KeyboardInterrupt, EOFError):
            logger.info("Received exit signal. Exiting...")
            break


if __name__ == "__main__":
    main()
