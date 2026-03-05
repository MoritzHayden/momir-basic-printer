import json
from pathlib import Path
from io import BytesIO
from PIL import Image
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
        self.excluded_layouts = [layout.strip() for layout in config.get('excluded_layouts').replace('\n', '').split(',')]
        self.art_width_px = config.getint('art_width_px')
        self.cards_path = Path(sys.argv[0]).resolve().parent.parent / config.get('cards_path')
        self.art_path = config.get('art_path')
        self.access_rights = int(config.get('access_rights'), 0)

    def get_total_card_count(self):
        logger.debug(f"Counting all cards...")
        path = Path(self.cards_path)
        all_items = path.rglob('*')
        card_count = len([item for item in all_items if item.is_file()])
        logger.debug(f"Counted {card_count} cards.")
        return card_count

    def get_card_count_by_cmc(self, cmc):
        logger.debug(f"Counting cards with CMC: {cmc}...")
        path = Path(os.path.join(self.cards_path, str(cmc)))
        card_count = len([card for card in path.iterdir() if card.is_file()])
        logger.debug(f"Counted {card_count} cards with CMC: {cmc}.")
        return card_count

    def get_card_art_by_card_id(self, card_id):
        logger.debug(f"Fetching card art for card_id: {card_id}...")
        card_art_path = Path(os.path.join(self.cards_path, self.art_path, f"{card_id}.jpg"))
        card_art = None
        if card_art_path.is_file():
            card_art = Image.open(card_art_path)
            logger.debug(f"Fetched card art for card_id: {card_id}.")
        else:
            logger.warning(f"Failed to fetch card art for card_id: {card_id}.")
        return card_art

    def get_random_card_by_cmc(self, cmc):
        logger.debug(f"Fetching random card with CMC: {cmc}...")
        path = Path(os.path.join(self.cards_path, str(cmc)))
        cards = [card for card in path.iterdir() if card.is_file()]
        if not cards:
            return None
        random_card_path = random.choice(cards)
        with open(random_card_path, 'r') as card_file:
            random_card = json.load(card_file)
            logger.debug(f"Fetched random card with CMC: {cmc} - {random_card['name']}.")
            return random_card

    def download_bulk_metadata(self):
        headers = {
            'Accept': self.header_accept,
            'User-Agent': self.header_user_agent
        }
        logger.debug(f"Fetching bulk metadata...")
        response = requests.get(f"{self.base_url}{self.bulk_data_endpoint}", headers=headers)
        if response.status_code == 200:
            logger.debug(f"Fetched bulk metadata.")
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
        logger.debug(f"Fetching bulk data...")
        response = requests.get(bulk_metadata['download_uri'], headers=headers)
        if response.status_code == 200:
            logger.debug(f"Fetched bulk data. Filtering for creatures...")
            creature_bulk_data = [card for card in response.json() if 'creature' in card['type_line'].lower() and card['layout'] not in self.excluded_layouts]
            logger.debug(f"Filtered bulk data for creatures.")
            return creature_bulk_data
        else:
            logger.error(f"Error fetching bulk data: {response.status_code}")
            raise Exception(f"Error fetching bulk data: {response.status_code}")

    def filter_bulk_data_by_cmc(self, bulk_data, cmc):
        logger.debug(f"Filtering bulk data for CMC: {cmc}...")
        filtered_bulk_data = [card for card in bulk_data if card['cmc'] == cmc]
        logger.debug(f"Filtered bulk data for CMC: {cmc}.")
        return filtered_bulk_data

    def delete_directory(self, path):
        logger.debug(f"Deleting {path} directory...")
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            logger.debug(f"Deleted {path} directory.")
        else:
            logger.warning(f"Directory {path} does not exist.")
            return

    def create_directory(self, path):
        logger.debug(f"Creating {path} directory...")
        if not os.path.exists(path):
            logger.debug(f"Creating {path} directory...")
            os.makedirs(path, mode=self.access_rights)
            logger.debug(f"Created {path} directory.")
        else:
            logger.warning(f"Directory {path} already exists.")

    def save_card(self, path, card):
        logger.debug(f"Saving {path}...")
        with open(path, 'w') as f:
            json.dump(card, f)
        logger.debug(f"Saved {path}.")

    # def save_card_art(self, path, card_art_uri):
    #     logger.debug(f"Downloading {card_art_uri}...")
    #     response = requests.get(card_art_uri)
    #     if response.status_code == 200:
    #         logger.debug(f"Downloaded {card_art_uri}. Saving to {path}...")
    #         with open(path, 'wb') as f:
    #             f.write(response.content)
    #             logger.debug(f"Saved {path}.")
    #         logger.debug(f"Saved {path}.")
    #     else:
    #         logger.error(f"Error downloading {card_art_uri}: {response.status_code}")
    #         raise Exception(f"Error downloading {card_art_uri}: {response.status_code}")

    def save_card_art(self, path, card_art_uri):
        logger.debug(f"Downloading {card_art_uri}...")
        response = requests.get(card_art_uri)
        if response.status_code == 200:
            logger.debug(f"Downloaded {card_art_uri}. Processing...")
            img = Image.open(BytesIO(response.content))
            w_percent = (self.art_width_px / float(img.size[0]))
            h_size = int((float(img.size[1]) * float(w_percent)))
            img = img.resize((self.art_width_px, h_size), Image.Resampling.LANCZOS)
            img = img.convert("1") # "L"=Grayscale, 1=Black&White
            img.save(path)
            logger.debug(f"Processed and saved to {path}.")
        else:
            logger.error(f"Error downloading {card_art_uri}: {response.status_code}")
            raise Exception(f"Error downloading {card_art_uri}: {response.status_code}")

    def generate_metadata(self):
        # TODO: Implement
        pass

    def refresh_card_data(self):
        self.delete_directory(self.cards_path)
        self.create_directory(self.cards_path)
        bulk_creature_data = self.download_bulk_creature_data()
        unique_cmc_values = {int(card['cmc']) for card in bulk_creature_data}
        for cmc in unique_cmc_values:
            filtered_bulk_data = self.filter_bulk_data_by_cmc(bulk_creature_data, cmc)
            card_cmc_path = os.path.join(self.cards_path, str(cmc))
            card_art_cmc_path = os.path.join(card_cmc_path, self.art_path)
            self.create_directory(card_cmc_path)
            self.create_directory(card_art_cmc_path)
            for card in filtered_bulk_data:
                card_path = os.path.join(card_cmc_path, f"{card['id']}.json")
                self.save_card(card_path, card)
                card_art_path = os.path.join(card_art_cmc_path, f"{card['id']}.jpg")
                card_art_uri = None
                if card.get('card_faces') and card['card_faces'][0].get('image_uris'):
                    card_art_uri = card['card_faces'][0]['image_uris'].get('art_crop')
                elif card.get('image_uris'):
                    card_art_uri = card['image_uris'].get('art_crop')
                if not card_art_uri:
                    logger.warning(f"No art URI found for card {card['name']} (ID: {card['id']}). Skipping...")
                    continue
                self.save_card_art(card_art_path, card_art_uri)
