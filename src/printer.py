import logging
logger = logging.getLogger(__name__)


class Printer:
    def __init__(self, config):
        self.print_speed = config.getint('print_speed')
        self.paper_width_mm = config.getint('paper_width_mm')
        self.dpi = config.getint('dpi')

    def print_card(self, card):
        # TODO: Implement
        card_name = card["name"]
        card_mana_cost = card["mana_cost"]
        card_type_line = card["type_line"]
        card_rarity_long = card["rarity"].capitalize()
        card_rarity_short = card["rarity"][0].upper()
        card_oracle_text = card["oracle_text"]
        card_power = card["power"]
        card_toughness = card["toughness"]
        logger.info(f"Printing card: {card_name}")
        logger.info(f"\n\nCard Name: {card_name}\nMana Cost: {card_mana_cost}\nType Line: {card_type_line}\nRarity: {card_rarity_long} ({card_rarity_short})\nOracle Text: {card_oracle_text}\nPower/Toughness: {card_power}/{card_toughness}\n")
        pass
