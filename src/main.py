"""Momir Basic Printer - Headless hardware-driven appliance for printing Magic: The Gathering cards.

This module provides an event-driven control loop for:
- Selecting a CMC via rotary encoder displayed on an OLED screen
- Printing a random card at the selected CMC via thermal printer on short press
- Cancelling an active operation via long press
- Refreshing card data on startup when needed
"""

import configparser
import enum
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from gpiozero import Button, RotaryEncoder

# Configuration
config = configparser.ConfigParser()
config_file = Path(__file__).resolve().with_name('config.ini')

if not config_file.exists():
    raise FileNotFoundError(f"Configuration file not found: {config_file}")

config.read(config_file)

# Validate required sections exist
required_sections = ['APP', 'FILESYSTEM', 'HARDWARE', 'LOGGING', 'PRINTER', 'SCRYFALL']
missing_sections = [
    section for section in required_sections if section not in config]
if missing_sections:
    raise ValueError(
        f"Missing required configuration sections: {', '.join(missing_sections)}")

app_config = config['APP']
filesystem_config = config['FILESYSTEM']
hardware_config = config['HARDWARE']
logging_config = config['LOGGING']
printer_config = config['PRINTER']
scryfall_config = config['SCRYFALL']

# Logging setup
logger = logging.getLogger('momir.main')
logging.basicConfig(
    level=logging_config.get('log_level').upper(),
    format=logging_config.get('log_format'),
    datefmt=logging_config.get('log_date_format'),
    stream=sys.stdout,
    force=True,
)


class AppState(enum.Enum):
    IDLE = "idle"
    FETCHING = "fetching"
    PRINTING = "printing"


class MomirApp:
    """Main application controller for the headless Momir Basic Printer."""

    def __init__(self) -> None:
        self._state = AppState.IDLE
        self._state_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # CMC bounds from config
        self._cmc_min: int = hardware_config.getint('cmc_min', fallback=0)
        self._cmc_max: int = hardware_config.getint('cmc_max', fallback=16)
        self._cmc: int = self._cmc_min

        # Services (set up in initialize)
        self.printer: Optional[Any] = None
        self.scryfall: Optional[Any] = None
        self.display: Optional[Any] = None

        # Hardware inputs
        hold_time: float = hardware_config.getfloat('hold_time', fallback=1.5)
        enc_clk: int = hardware_config.getint('gpio_encoder_clk')
        enc_dt: int = hardware_config.getint('gpio_encoder_dt')
        enc_sw: int = hardware_config.getint('gpio_encoder_sw')

        self._encoder = RotaryEncoder(enc_clk, enc_dt, wrap=False,
                                       max_steps=self._cmc_max)
        self._encoder.steps = self._cmc_min

        self._button = Button(enc_sw, pull_up=True, hold_time=hold_time)
        self._held_fired = False

        # App UI/runtime text and limits
        self._booting_status: str = app_config.get('booting_status', fallback='Booting...')
        self._ready_status: str = app_config.get('ready_status', fallback='Ready')
        self._refreshing_status: str = app_config.get('refreshing_status', fallback='Refreshing...')
        self._fetching_status: str = app_config.get('fetching_status', fallback='Fetching...')
        self._printing_status: str = app_config.get('printing_status', fallback='Printing...')
        self._cancelled_status: str = app_config.get('cancelled_status', fallback='Cancelled')
        self._error_status: str = app_config.get('error_status', fallback='Error')
        self._reset_status: str = app_config.get('reset_status', fallback='Reset')
        self._services_unavailable_status: str = app_config.get(
            'services_unavailable_status', fallback='Services N/A')
        self._no_cmc_status_template: str = app_config.get(
            'no_cmc_status_template', fallback='No CMC {cmc}')
        self._shutdown_join_timeout_seconds: float = app_config.getfloat(
            'shutdown_join_timeout_seconds', fallback=5)
        self._printed_status_name_max_len: int = app_config.getint(
            'printed_status_name_max_len', fallback=20)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize display, printer, and scryfall services."""
        # Display
        try:
            from display import DisplayManager
            self.display = DisplayManager(hardware_config)
            self.display.update(cmc=self._cmc, status=self._booting_status)
            logger.info("Display service initialized.")
        except Exception as exc:
            self.display = None
            logger.error(f"Display service unavailable: {exc}")

        # Printer
        try:
            from printer import Printer
            self.printer = Printer(printer_config, filesystem_config, hardware_config)
            logger.info("Printer service initialized.")
        except Exception as exc:
            self.printer = None
            logger.error(f"Printer service unavailable: {exc}")

        # Scryfall
        try:
            from scryfall import Scryfall
            self.scryfall = Scryfall(scryfall_config, filesystem_config)
            logger.info("Scryfall service initialized.")
        except Exception as exc:
            self.scryfall = None
            logger.error(f"Scryfall service unavailable: {exc}")

        # Auto-refresh if needed
        if self.scryfall is not None and self.scryfall.needs_refresh():
            self._set_status(self._refreshing_status)
            try:
                self.scryfall.refresh_card_data(force_full_refresh=False)
                logger.info("Card data refresh complete.")
            except Exception as exc:
                logger.error(f"Card data refresh failed: {exc}")

        self._set_status(self._ready_status)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _set_state(self, state: AppState) -> None:
        with self._state_lock:
            self._state = state

    def _get_state(self) -> AppState:
        with self._state_lock:
            return self._state

    def _set_status(self, text: str) -> None:
        logger.debug(f"Status: {text}")
        if self.display is not None:
            self.display.set_status(text)

    # ------------------------------------------------------------------
    # Encoder rotation callback
    # ------------------------------------------------------------------

    def _on_rotate(self) -> None:
        steps = self._encoder.steps
        cmc = max(self._cmc_min, min(self._cmc_max, steps))
        self._encoder.steps = cmc  # clamp
        self._cmc = cmc
        if self.display is not None:
            self.display.set_cmc(cmc)

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    def _on_held(self) -> None:
        """Fires when button is held past hold_time — treat as long press."""
        self._held_fired = True
        self._on_long_press()

    def _on_released(self) -> None:
        """Fires on button release. If hold wasn't triggered, treat as short press."""
        if self._held_fired:
            self._held_fired = False
            return
        self._on_short_press()

    def _on_short_press(self) -> None:
        """Short press: fetch and print a random card at current CMC."""
        if self._get_state() != AppState.IDLE:
            logger.debug("Ignoring short press — operation in progress.")
            return

        if self.scryfall is None or self.printer is None:
            self._set_status(self._services_unavailable_status)
            return

        self._cancel_event.clear()
        self._worker_thread = threading.Thread(
            target=self._fetch_and_print, args=(self._cmc,), daemon=True)
        self._worker_thread.start()

    def _on_long_press(self) -> None:
        """Long press: cancel active operation or reset to idle."""
        if self._get_state() != AppState.IDLE:
            logger.info("Long press — cancelling active operation.")
            self._cancel_event.set()
        else:
            self._cmc = self._cmc_min
            self._encoder.steps = self._cmc_min
            if self.display is not None:
                self.display.update(cmc=self._cmc, status=self._reset_status)

    # ------------------------------------------------------------------
    # Worker (runs in background thread)
    # ------------------------------------------------------------------

    def _fetch_and_print(self, cmc: int) -> None:
        try:
            # --- fetch ---
            self._set_state(AppState.FETCHING)
            self._set_status(self._fetching_status)
            if self._cancel_event.is_set():
                self._set_status(self._cancelled_status)
                return

            card = self.scryfall.get_random_card_by_cmc(cmc)

            if card is None:
                self._set_status(self._no_cmc_status_template.format(cmc=cmc))
                return

            if self._cancel_event.is_set():
                self._set_status(self._cancelled_status)
                return

            # --- print ---
            self._set_state(AppState.PRINTING)
            card_name = card.get("name", "Unknown")
            self._set_status(self._printing_status)
            logger.info(f"Printing: {card_name}")

            self.printer.print_card(card)
            self._set_status(card_name[:self._printed_status_name_max_len])
            logger.info(f"Printed: {card_name}")

        except Exception as exc:
            logger.error(f"Fetch/print error: {exc}")
            self._set_status(self._error_status)
        finally:
            self._set_state(AppState.IDLE)

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Attach callbacks and block until shutdown."""
        logger.info("Momir Basic Printer started.")

        # Encoder rotation
        self._encoder.when_rotated = self._on_rotate

        # Button: when_held fires after hold_time; when_released distinguishes
        # short press (held didn't fire) from long press (held already fired).
        self._button.when_held = self._on_held
        self._button.when_released = self._on_released

        # Wait for shutdown signal
        self._shutdown_event.wait()

    def shutdown(self) -> None:
        """Clean up hardware resources and exit."""
        logger.info("Shutting down...")
        self._cancel_event.set()

        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=self._shutdown_join_timeout_seconds)

        if self.display is not None:
            self.display.clear()
            self.display.cleanup()

        if self.printer is not None:
            self.printer.cleanup()

        self._encoder.close()
        self._button.close()

        self._shutdown_event.set()
        logger.info("Momir Basic Printer stopped.")


def main() -> None:
    app = MomirApp()

    def _signal_handler(signum, frame):
        app.shutdown()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        app.initialize()
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
