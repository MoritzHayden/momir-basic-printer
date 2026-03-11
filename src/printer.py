"""Thermal printer interface for printing Magic: The Gathering cards."""

import logging
import json
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, Optional

import gpiozero
from escpos.printer import Serial
from PIL import Image

logger = logging.getLogger('momir.printer')


class Printer:
    """Thermal printer interface for printing Magic: The Gathering cards.

    This class handles:
    - Formatting card data for thermal printer output
    - Printing card images, text, and QR codes
    - Text cleaning and wrapping for proper display
    - DTR-based hardware flow control on the serial thermal printer
    """

    def __init__(self, printer_config, filesystem_config, hardware_config=None) -> None:
        """Initialize printer with configuration.

        Args:
            printer_config: Configuration section for printer settings
            filesystem_config: Configuration section for filesystem paths
            hardware_config: Optional configuration section for GPIO/serial settings
        """
        # Printer configuration
        self.paper_width_mm: int = printer_config.getint('paper_width_mm')
        self.paper_width_chars: int = printer_config.getint(
            'paper_width_chars')
        self.card_art_enabled: bool = printer_config.getboolean(
            'card_art_enabled')
        self.qr_code_enabled: bool = printer_config.getboolean(
            'qr_code_enabled')
        self.qr_code_size: int = printer_config.getint('qr_code_size')
        self.dpi: int = printer_config.getint('dpi')
        self.vendor_id: int = int(printer_config.get('vendor_id'), 0)
        self.product_id: int = int(printer_config.get('product_id'), 0)

        # Serial configuration (from [HARDWARE] or fallbacks)
        if hardware_config is not None:
            self.serial_port: str = hardware_config.get(
                'serial_port', fallback='/dev/serial0')
            self.serial_baud_rate: int = hardware_config.getint(
                'serial_baud_rate', fallback=9600)
            self._dtr_pin: int = hardware_config.getint(
                'gpio_printer_dtr', fallback=17)
            self._dtr_poll_interval: float = hardware_config.getfloat(
                'dtr_poll_interval', fallback=0.05)
        else:
            self.serial_port = '/dev/serial0'
            self.serial_baud_rate = 9600
            self._dtr_pin = 17
            self._dtr_poll_interval = 0.05

        self.printer_profile: str = printer_config.get(
            'printer_profile', fallback='simple')
        self.printer_media_width_px: Optional[int] = printer_config.getint(
            'printer_media_width_px', fallback=None)
        self._min_title_spacing: int = printer_config.getint('min_title_spacing', fallback=1)
        self._paragraph_spacing: str = printer_config.get(
            'paragraph_spacing', fallback='\\n\\n').encode('utf-8').decode('unicode_escape')
        text_replacements_json = printer_config.get(
            'text_replacements_json',
            fallback='{"\\u2014":"-","\\u2013":"-","\\u2019":"\'","\\u201c":"\\\"","\\u201d":"\\\""}',
        )
        try:
            self._text_replacements: Dict[str, str] = json.loads(text_replacements_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid text_replacements_json in config: {exc}") from exc

        # DTR monitoring: printer pulls HIGH when its buffer is full.
        self._dtr_device = gpiozero.InputDevice(self._dtr_pin, pull_up=False)

        # Filesystem paths (use __file__ for reliability)
        base_path = Path(__file__).resolve().parent.parent
        self.cards_path: Path = base_path / filesystem_config.get('cards_path')
        self.art_path: Path = base_path / filesystem_config.get('art_path')
        self.default_card_art_path: Path = base_path / \
            filesystem_config.get('default_card_art_path')
        self.access_rights: int = int(
            filesystem_config.get('access_rights'), 0)

        # Ensure runtime directories exist so app can boot on a fresh install.
        self.cards_path.mkdir(parents=True, exist_ok=True, mode=self.access_rights)
        self.art_path.mkdir(parents=True, exist_ok=True, mode=self.access_rights)

        # Validate configuration
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate critical configuration values on initialization.

        Raises:
            ValueError: If critical configuration is missing or invalid
        """
        if self.paper_width_chars <= 0:
            raise ValueError(
                f"paper_width_chars must be positive, got {self.paper_width_chars}")

        if self.qr_code_size <= 0:
            raise ValueError(
                f"qr_code_size must be positive, got {self.qr_code_size}")

        if self.printer_media_width_px is not None and self.printer_media_width_px <= 0:
            raise ValueError(
                "printer_media_width_px must be positive when provided")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (f"Printer(serial='{self.serial_port}', "
                f"baud={self.serial_baud_rate}, "
            f"profile='{self.printer_profile}', "
            f"paper_width_chars={self.paper_width_chars})")

    def clean_text(self, text: str) -> str:
        """Clean text for thermal printer compatibility.

        Replaces special Unicode characters with ASCII equivalents
        that the thermal printer can handle.

        Args:
            text: Input text to clean

        Returns:
            Cleaned text with replaced characters
        """
        cleaned = text
        for old_char, new_char in self._text_replacements.items():
            cleaned = cleaned.replace(old_char, new_char)
        return cleaned

    def _wait_for_dtr(self) -> None:
        """Block until the printer's DTR pin indicates the buffer has space.

        The thermal printer pulls DTR HIGH when its internal buffer is full.
        This method busy-waits (with a sleep interval) until DTR drops LOW.
        """
        while self._dtr_device.is_active:
            time.sleep(self._dtr_poll_interval)

    def _get_printer_connection(self) -> Serial:
        """Create and return a printer serial connection.

        Returns:
            Serial printer connection object

        Raises:
            Exception: If connection to printer fails
        """
        try:
            printer = Serial(
                devfile=self.serial_port,
                baudrate=self.serial_baud_rate,
                profile=self.printer_profile,
            )

            # Optional override for profile media width in pixels.
            if self.printer_media_width_px is not None:
                profile_data = printer.profile.profile_data
                media = profile_data.setdefault("media", {})
                width = media.setdefault("width", {})
                width["pixels"] = str(self.printer_media_width_px)

            return printer
        except Exception as e:
            logger.error(
                f"Failed to connect to printer on {self.serial_port}: {e}")
            raise

    def _get_printer_max_width_px(self, printer: Serial) -> Optional[int]:
        """Read max printable image width (pixels) from the active printer profile.

        Args:
            printer: Connected network printer instance

        Returns:
            Max width in pixels, or None if unavailable
        """
        try:
            pixels_value = printer.profile.profile_data["media"]["width"]["pixels"]
            return int(pixels_value)
        except (KeyError, TypeError, ValueError):
            return None

    def _print_card_art(self, printer: Serial, card_art_path: Path) -> None:
        """Print card art, resizing if needed to fit printer width.

        Args:
            printer: Connected serial printer instance
            card_art_path: Path to card art image
        """
        self._wait_for_dtr()
        max_width_px = self._get_printer_max_width_px(printer)

        if max_width_px is not None:
            with Image.open(card_art_path) as img:
                if img.width > max_width_px:
                    # Scale down to printer width while preserving aspect ratio.
                    scale = max_width_px / float(img.width)
                    target_height = max(1, int(img.height * scale))
                    img = img.resize((max_width_px, target_height), Image.Resampling.LANCZOS)
                    logger.debug(
                        f"Resized card art for printer width: {card_art_path.name} "
                        f"({img.width}x{img.height})"
                    )
                printer.image(img.copy())
            return

        printer.image(str(card_art_path))

    def print_card(self, card: Dict[str, Any]) -> None:
        """Print a Magic: The Gathering card to the thermal printer.

        Prints formatted card information including:
        - Name and mana cost
        - Card artwork (if enabled)
        - Type line
        - Oracle text (wrapped to paper width)
        - Power/toughness (for creatures)
        - QR code linking to Scryfall page (if enabled)

        Args:
            card: Card data dictionary containing card information

        Raises:
            Exception: If printing fails
        """
        # Extract and clean card data
        card_name = self.clean_text(card.get("name") or "Unknown Card")
        card_mana_cost = card.get("mana_cost") or ""
        card_scryfall_uri = card.get("scryfall_uri") or ""
        card_id = card.get("id")
        card_art_path: Optional[Path] = (
            self.art_path / f"{card_id}.jpg") if card_id else None
        card_type_line = self.clean_text(card.get("type_line") or "")
        card_oracle_text = self.clean_text(card.get("oracle_text") or "")
        card_power = card.get("power")
        card_toughness = card.get("toughness")

        logger.debug(f"Printing card: {card_name}...")

        try:
            printer = self._get_printer_connection()

            # NAME AND MANA COST
            self._wait_for_dtr()
            printer.set(align='left', bold=True)
            title_line_spaces = max(
                self._min_title_spacing,
                self.paper_width_chars - (len(card_name) + len(card_mana_cost))
            )
            title_line_padding = " " * title_line_spaces
            printer.text(f"{card_name}{title_line_padding}{card_mana_cost}\n")

            # ART
            printer.set(align='center', bold=False)
            if self.card_art_enabled and card_art_path and card_art_path.exists():
                printer.text("\n")
                self._print_card_art(printer, card_art_path)
                printer.text("\n")

            # TYPE LINE
            if card_type_line:
                printer.text(f"\n{card_type_line}\n\n")

            # ORACLE TEXT
            if card_oracle_text:
                printer.set(align='left', bold=False)
                for paragraph in card_oracle_text.split('\n'):
                    self._wait_for_dtr()
                    if paragraph.strip():
                        wrapped = textwrap.fill(
                            paragraph, width=self.paper_width_chars)
                        printer.text(wrapped + self._paragraph_spacing)
                    else:
                        printer.text("\n")

            # POWER / TOUGHNESS
            if card_power is not None and card_toughness is not None:
                printer.set(align='right', bold=False)
                printer.text(f"{card_power} / {card_toughness}\n")

            # QR CODE
            self._wait_for_dtr()
            printer.set(align='center', bold=False)
            if self.qr_code_enabled and card_scryfall_uri:
                printer.qr(card_scryfall_uri, size=self.qr_code_size)

            printer.cut()
            logger.info(f"Successfully printed: {card_name}")

        except Exception as e:
            logger.error(f"Failed to print card {card_name}: {e}")
            raise

    def cleanup(self) -> None:
        """Release the DTR GPIO resource."""
        self._dtr_device.close()
