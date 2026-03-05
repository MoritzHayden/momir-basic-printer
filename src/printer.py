import sys
from pathlib import Path
import os
import sys
import textwrap
from escpos.printer import Network
import logging
logger = logging.getLogger(__name__)


class Printer:
    def __init__(self, config):
        self.paper_width_mm = config.getint('paper_width_mm')
        self.paper_width_chars = config.getint('paper_width_chars')
        self.dpi = config.getint('dpi')
        self.vendor_id = int(config.get('vendor_id'), 0)
        self.product_id = int(config.get('product_id'), 0)
        self.cards_path = Path(sys.argv[0]).resolve().parent.parent / config.get('cards_path')
        self.art_path = config.get('art_path')

    def clean_text(self, text):
        return (text.replace('—', '-')
                    .replace('–', '-')
                    .replace('’', "'")
                    .replace('“', '"')
                    .replace('”', '"'))

    def print_card(self, card):
        card_name = self.clean_text(card["name"])
        card_mana_cost = card["mana_cost"]
        card_art_path = os.path.join(self.cards_path, str(int(card["cmc"])), self.art_path, f"{card['id']}.jpg")
        card_type_line = self.clean_text(card["type_line"])
        card_rarity = card["rarity"].capitalize()
        card_oracle_text = self.clean_text(card["oracle_text"])
        card_power = card["power"]
        card_toughness = card["toughness"]
        card_power_toughness = f"{card_power} / {card_toughness}"
        logger.debug(f"Printing card: {card_name}...")
        printer = Network("127.0.0.1", port=9100, profile="simple")
        printer.set(align='left', bold=True)
        title_line_spaces = self.paper_width_chars - (len(card_name) + len(card_mana_cost))
        title_line_padding = " " * max(1, title_line_spaces)
        printer.text(f"{card_name}{title_line_padding}{card_mana_cost}\n\n")
        printer.set(align='center', bold=False)
        printer.image(card_art_path)
        printer.text(f"\n\n")
        printer.text(f"{card_type_line}\n\n")
        printer.set(align='left', bold=False)
        for paragraph in card_oracle_text.split('\n'):
            if paragraph.strip():
                wrapped = textwrap.fill(paragraph, width=self.paper_width_chars)
                printer.text(wrapped + "\n\n")
            else:
                printer.text("\n")
        printer.set(align='center', bold=False)
        power_line_spaces = self.paper_width_chars - (len(card_rarity) + len(card_power_toughness))
        power_line_padding = " " * max(1, power_line_spaces)
        printer.text(f"{card_rarity}{power_line_padding}{card_power_toughness}\n")
        printer.cut()
        logger.debug(f"Printed card: {card_name}.")
