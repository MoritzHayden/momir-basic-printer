import configparser
from pathlib import Path
import readline
import logging
config = configparser.ConfigParser()
config.read(Path(__file__).resolve().with_name('config.ini'))
filesystem_config = config['FILESYSTEM']
logging_config = config['LOGGING']
printer_config = config['PRINTER']
scryfall_config = config['SCRYFALL']
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging_config.get('log_level').upper(),
    format=logging_config.get('log_format')
)
from printer import Printer
from scryfall import Scryfall
printer = Printer(printer_config, filesystem_config)
scryfall = Scryfall(scryfall_config, filesystem_config)


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
                case 'i' | 'info':
                    logger.debug(f"Received info command.")
                    metadata = scryfall.get_metadata()
                    logger.info(f"Last updated at: {metadata.get('updated_at')}")
                    logger.info(f"Total card count: {metadata.get('total_card_count')} cards")
                    logger.info(f"CMC card counts:")
                    for cmc, count in metadata.get('cmc_card_count', {}).items():
                        logger.info(f"\tCMC {cmc}: {count} cards")
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
