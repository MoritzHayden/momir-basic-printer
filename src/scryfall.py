from pathlib import Path
from io import BytesIO
from time import sleep
from PIL import Image
import ijson
import json
import gzip
import os
import shutil
import sys
import random
import requests
import logging
logger = logging.getLogger(__name__)


class Scryfall:
    def __init__(self, scryfall_config, filesystem_config):
        self.base_url = scryfall_config.get('base_url')
        self.bulk_data_endpoint = scryfall_config.get('bulk_data_endpoint')
        self.header_accept = scryfall_config.get('header_accept')
        self.header_user_agent = scryfall_config.get('header_user_agent')
        self.header_accept_encoding = scryfall_config.get('header_accept_encoding')
        self.request_delay_seconds = scryfall_config.getfloat('request_delay_seconds')
        self.max_retries = scryfall_config.getint('max_retries')
        self.art_width_px = scryfall_config.getint('art_width_px')
        self.excluded_sets = [set.strip() for set in scryfall_config.get('excluded_sets').replace('\n', '').split(',')]
        self.excluded_layouts = [layout.strip() for layout in scryfall_config.get('excluded_layouts').replace('\n', '').split(',')]
        self.cards_path = Path(sys.argv[0]).resolve().parent.parent / filesystem_config.get('cards_path')
        self.art_path = Path(sys.argv[0]).resolve().parent.parent / filesystem_config.get('art_path')
        self.default_card_art_path = Path(sys.argv[0]).resolve().parent.parent / filesystem_config.get('default_card_art_path')
        self.access_rights = int(filesystem_config.get('access_rights'), 0)

    def get_valid_cmcs(self):
        logger.debug(f"Getting valid CMCs...")
        valid_cmcs = []
        cmc_dirs = [int(d.name) for d in Path(self.cards_path).iterdir() if d.is_dir() and d.name.isdigit()]
        valid_cmcs = sorted(cmc_dirs)
        logger.debug(f"Valid CMCs: {valid_cmcs}")
        return valid_cmcs

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
        card_art_path = Path(os.path.join(self.art_path, f"{card_id}.jpg"))
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

    def is_valid_momir_basic_card(self, card):
        if card.get('layout') in self.excluded_layouts:
            return False

        if card.get('set_type') in self.excluded_sets:
            return False

        if 'paper' not in card.get('games', []):
            return False

        if 'card_faces' in card:
            front_type = card['card_faces'][0].get('type_line', '').lower()
            return 'creature' in front_type
        else:
            type_line = card.get('type_line', '').lower()
            return 'creature' in type_line

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
            'User-Agent': self.header_user_agent,
            'Accept-Encoding': self.header_accept_encoding
        }
        bulk_metadata = self.download_bulk_metadata()
        download_uri = bulk_metadata['download_uri']
        logger.info(f"Streaming bulk data from Scryfall...")
        creature_bulk_data = []
        total_processed = 0
        with requests.get(download_uri, headers=headers, stream=True) as response:
            if response.status_code == 200:
                with gzip.GzipFile(fileobj=response.raw) as unzipped_stream:
                    parser = ijson.items(unzipped_stream, 'item', use_float=True)
                    for card in parser:
                        total_processed += 1
                        if self.is_valid_momir_basic_card(card):
                            creature_bulk_data.append(card)
                        if total_processed % 1000 == 0:
                            logger.info(f"Processed {total_processed} cards. Found {len(creature_bulk_data)} creatures so far.")
                logger.info(f"Finished streaming {total_processed} cards. Found {len(creature_bulk_data)} valid creatures.")
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
            logger.debug(f"Directory {path} does not exist.")
            return

    def create_directory(self, path):
        logger.debug(f"Creating {path} directory...")
        if not os.path.exists(path):
            logger.debug(f"Creating {path} directory...")
            os.makedirs(path, mode=self.access_rights)
            logger.debug(f"Created {path} directory.")
        else:
            logger.debug(f"Directory {path} already exists.")

    def save_card(self, path, card):
        logger.debug(f"Saving {path}...")
        with open(path, 'w') as f:
            json.dump(card, f)
        logger.debug(f"Saved {path}.")

    def save_card_art(self, path, card_art_uri, retry):
        logger.debug(f"Downloading {card_art_uri}...")
        response = requests.get(card_art_uri)
        if response.status_code == 200:
            logger.debug(f"Downloaded {card_art_uri}. Processing...")
            img = Image.open(BytesIO(response.content))
            w_percent = (self.art_width_px / float(img.size[0]))
            h_size = int((float(img.size[1]) * float(w_percent)))
            img = img.resize((self.art_width_px, h_size), Image.Resampling.LANCZOS)
            img = img.convert("1")
            img.save(path)
            logger.debug(f"Processed and saved to {path}. Sleeping for {self.request_delay_seconds} seconds to respect rate limits...")
            sleep(self.request_delay_seconds)
        elif retry < self.max_retries:
            logger.warning(f"Error downloading {card_art_uri}: {response.status_code}. Retrying ({retry + 1}/{self.max_retries})...")
            sleep(self.request_delay_seconds)
            self.save_card_art(path, card_art_uri, retry + 1)
        else:
            logger.warning(f"Error downloading {card_art_uri}: {response.status_code}. Max retries reached. Using default art.")
            shutil.copy(self.default_card_art_path, path)

    def generate_metadata(self, bulk_metadata):
        metadata_path = os.path.join(self.cards_path, "metadata.json")
        metadata = {
            'updated_at': bulk_metadata.get('updated_at'),
            'download_uri': bulk_metadata.get('download_uri'),
            'total_card_count': self.get_total_card_count(),
            'cmc_card_count': {str(cmc): self.get_card_count_by_cmc(cmc) for cmc in self.get_valid_cmcs()}
        }
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
        logger.debug(f"Generated metadata at {metadata_path}.")

    def get_metadata(self):
        metadata_path = os.path.join(self.cards_path, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                logger.debug(f"Loaded metadata from {metadata_path}.")
                return metadata
        else:
            logger.debug(f"Metadata file not found at {metadata_path}. Generating new metadata file...")
            self.generate_metadata()
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                logger.debug(f"Generated and loaded metadata from {metadata_path}.")
                return metadata

    def process_and_save_card(self, card):
        cmc = int(card.get('cmc', 0))
        card_cmc_path = os.path.join(self.cards_path, str(cmc))
        if not os.path.exists(card_cmc_path):
            os.makedirs(card_cmc_path, mode=self.access_rights)
        card_path = os.path.join(card_cmc_path, f"{card['id']}.json")
        self.save_card(card_path, card)
        card_art_uri = (card.get('card_faces', [{}])[0].get('image_uris', {}).get('art_crop') 
                        or card.get('image_uris', {}).get('art_crop'))
        if card_art_uri:
            art_path = os.path.join(self.art_path, f"{card['id']}.jpg")
            self.save_card_art(art_path, card_art_uri, 0)

    def refresh_card_data(self):
        self.delete_directory(self.cards_path)
        self.create_directory(self.cards_path)
        self.delete_directory(self.art_path)
        self.create_directory(self.art_path)
        headers = {'Accept-Encoding': 'gzip', 'User-Agent': self.header_user_agent}
        bulk_metadata = self.download_bulk_metadata()
        total_processed = 0
        total_creatures = 0
        logger.info(f"Streaming bulk data from Scryfall...")
        with requests.get(bulk_metadata['download_uri'], headers=headers, stream=True) as response:
            with gzip.GzipFile(fileobj=response.raw) as unzipped_stream:
                parser = ijson.items(unzipped_stream, 'item', use_float=True)
                for card in parser:
                    total_processed += 1
                    if self.is_valid_momir_basic_card(card):
                        total_creatures += 1
                        self.process_and_save_card(card)
                    if total_processed % 1000 == 0:
                        logger.info(f"Processed {total_processed} cards. Found {total_creatures} valid creatures so far.")
            logger.info(f"Finished processing {total_processed} cards. Found {total_creatures} valid creatures.")
        self.generate_metadata(bulk_metadata)
