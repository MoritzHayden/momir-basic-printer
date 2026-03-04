import json
from pathlib import Path
import os
import shutil
import sys
import random
import requests
import logging
logger = logging.getLogger(__name__)


class Scryfall:
    def __init__(self, config):
        self.base_url = config.get('base_url')
        self.bulk_data_endpoint = config.get('bulk_data_endpoint')
        self.header_accept = config.get('header_accept')
        self.header_user_agent = config.get('header_user_agent')
        self.download_path = Path(sys.argv[0]).resolve().parent.parent / config.get('download_path')
        self.access_rights = config.get('access_rights')

    def get_total_card_count(self):
        logger.info(f"Counting all cards...")
        path = Path(self.download_path)
        all_items = path.rglob('*')
        card_count = len([item for item in all_items if item.is_file()])
        logger.info(f"Counted {card_count} cards.")
        return card_count

    def get_card_count_by_cmc(self, cmc):
        logger.info(f"Counting cards with CMC: {cmc}...")
        path = Path(os.path.join(self.download_path, str(cmc)))
        card_count = len([card for card in path.iterdir() if card.is_file()])
        logger.info(f"Counted {card_count} cards with CMC: {cmc}.")
        return card_count

    def get_random_card_by_cmc(self, cmc):
        logger.info(f"Fetching random card with CMC: {cmc}...")
        path = Path(os.path.join(self.download_path, str(cmc)))
        cards = [card for card in path.iterdir() if card.is_file()]
        if not cards:
            return None
        random_card_path = random.choice(cards)
        with open(random_card_path, 'r') as card_file:
            random_card = json.load(card_file)
            logger.info(f"Fetched random card with CMC: {cmc} - {random_card['name']}.")
            return random_card

    def download_bulk_metadata(self):
        headers = {
            'Accept': self.header_accept,
            'User-Agent': self.header_user_agent
        }
        logger.info(f"Fetching bulk metadata...")
        response = requests.get(f"{self.base_url}{self.bulk_data_endpoint}", headers=headers)
        if response.status_code == 200:
            logger.info(f"Fetched bulk metadata.")
            return response.json()
        else:
            logger.error(f"Error fetching bulk data: {response.status_code}")
            raise Exception(f"Error fetching bulk data: {response.status_code}")

    def download_bulk_creature_data(self):
        headers = {
            'Accept': self.header_accept,
            'User-Agent': self.header_user_agent
        }
        bulk_metadata = self.download_bulk_metadata()
        logger.info(f"Fetching bulk data...")
        response = requests.get(bulk_metadata['download_uri'], headers=headers)
        if response.status_code == 200:
            logger.info(f"Fetched bulk data. Filtering for creatures...")
            creature_bulk_data = [card for card in response.json() if 'creature' in card['type_line'].lower()]
            logger.info(f"Filtered bulk data for creatures.")
            return creature_bulk_data
        else:
            logger.error(f"Error fetching bulk data: {response.status_code}")
            raise Exception(f"Error fetching bulk data: {response.status_code}")

    def filter_bulk_data_by_cmc(self, bulk_data, cmc):
        logger.info(f"Filtering bulk data for CMC: {cmc}...")
        filtered_bulk_data = [card for card in bulk_data if card['cmc'] == cmc]
        logger.info(f"Filtered bulk data for CMC: {cmc}.")
        return filtered_bulk_data

    def delete_directory(self, path):
        logger.info(f"Deleting {path} directory...")
        if os.path.exists(path):
            shutil.rmtree(path)
            logger.info(f"Deleted {path} directory.")
        else:
            logger.warning(f"Directory {path} does not exist.")
            return

    def create_directory(self, path):
        logger.info(f"Creating {path} directory...")
        if not os.path.exists(path):
            logger.info(f"Creating {path} directory...")
            os.makedirs(path, mode=int(self.access_rights, 8))
            logger.info(f"Created {path} directory.")
        else:
            logger.warning(f"Directory {path} already exists.")

    def refresh_card_data(self):
        self.delete_directory(self.download_path)
        self.create_directory(self.download_path)
        bulk_creature_data = self.download_bulk_creature_data()
        unique_cmc_values = {int(card['cmc']) for card in bulk_creature_data}
        for cmc in unique_cmc_values:
            cmc_path = os.path.join(self.download_path, str(cmc))
            self.create_directory(cmc_path)
            filtered_bulk_data = self.filter_bulk_data_by_cmc(bulk_creature_data, cmc)
            for card in filtered_bulk_data:
                card_path = os.path.join(cmc_path, f"{card['id']}.json")
                logger.info(f"Saving {card_path}...")
                with open(card_path, 'w') as f:
                    json.dump(card, f)
                    logger.info(f"Saved {card_path}.")
