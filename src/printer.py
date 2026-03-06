import sys
from pathlib import Path
import os
import sys
import textwrap
from escpos.printer import Network
import logging
logger = logging.getLogger(__name__)


class Printer:
    def __init__(self, printer_config, filesystem_config):
        self.paper_width_mm = printer_config.getint('paper_width_mm')
        self.paper_width_chars = printer_config.getint('paper_width_chars')
        self.card_art_enabled = printer_config.getboolean('card_art_enabled')
        self.qr_code_enabled = printer_config.getboolean('qr_code_enabled')
        self.qr_code_size = printer_config.getint('qr_code_size')
        self.dpi = printer_config.getint('dpi')
        self.vendor_id = int(printer_config.get('vendor_id'), 0)
        self.product_id = int(printer_config.get('product_id'), 0)
        self.cards_path = Path(sys.argv[0]).resolve().parent.parent / filesystem_config.get('cards_path')
        self.art_path = Path(sys.argv[0]).resolve().parent.parent / filesystem_config.get('art_path')
        self.default_card_art_path = Path(sys.argv[0]).resolve().parent.parent / filesystem_config.get('default_card_art_path')
        self.access_rights = int(filesystem_config.get('access_rights'), 0)

    def clean_text(self, text):
        return (text.replace('—', '-')
                    .replace('–', '-')
                    .replace('’', "'")
                    .replace('“', '"')
                    .replace('”', '"'))

    def print_card(self, card):
        card_name = self.clean_text(card.get("name") or "Unknown Card")
        card_mana_cost = card.get("mana_cost") or ""
        card_scryfall_uri = card.get("scryfall_uri") or ""
        card_id = card.get("id")
        card_art_path = os.path.join(self.art_path, f"{card_id}.jpg") if card_id else None
        card_type_line = self.clean_text(card.get("type_line") or "")
        card_oracle_text = self.clean_text(card.get("oracle_text") or "")
        card_power = card.get("power")
        card_toughness = card.get("toughness")

        logger.debug(f"Printing card: {card_name}...")
        printer = Network("127.0.0.1", port=9100, profile="simple")

        # NAME AND MANA COST
        printer.set(align='left', bold=True)
        title_line_spaces = max(1, self.paper_width_chars - (len(card_name) + len(card_mana_cost)))
        title_line_padding = " " * title_line_spaces
        printer.text(f"{card_name}{title_line_padding}{card_mana_cost}\n")

        # ART
        printer.set(align='center', bold=False)
        if self.card_art_enabled and card_art_path and os.path.exists(card_art_path):
            printer.text("\n")
            printer.image(card_art_path)
            printer.text("\n")

        # TYPE LINE
        if card_type_line:
            printer.text(f"\n{card_type_line}\n\n")

        # ORACLE TEXT
        if card_oracle_text:
            printer.set(align='left', bold=False)
            for paragraph in card_oracle_text.split('\n'):
                if paragraph.strip():
                    wrapped = textwrap.fill(paragraph, width=self.paper_width_chars)
                    printer.text(wrapped + "\n\n")
                else:
                    printer.text("\n")

        # POWER / TOUGHNESS
        if card_power is not None and card_toughness is not None:
            printer.set(align='right', bold=False)
            printer.text(f"{card_power} / {card_toughness}\n")

        # QR CODE
        printer.set(align='center', bold=False)
        if self.qr_code_enabled and card_scryfall_uri:
            printer.qr(card_scryfall_uri, size=self.qr_code_size)

        printer.cut()
        logger.debug(f"Printed card: {card_name}.")
