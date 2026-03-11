"""OLED display manager for the Momir Basic Printer hardware UI."""

import logging
import threading
from typing import Optional

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger('momir.display')


class DisplayManager:
    """Manages a single SSD1306 I2C OLED screen.

    The screen is split into two regions:
    - Top area: large CMC value display
    - Bottom area: status text line
    """

    def __init__(self, hardware_config) -> None:
        self.width: int = hardware_config.getint('oled_width', fallback=128)
        self.height: int = hardware_config.getint('oled_height', fallback=64)
        i2c_address: int = int(hardware_config.get('i2c_address', fallback='0x3C'), 16)
        i2c_port: int = hardware_config.getint('i2c_port', fallback=1)
        self._font_size_cmc: int = hardware_config.getint('display_font_size_cmc', fallback=36)
        self._font_size_status: int = hardware_config.getint('display_font_size_status', fallback=12)
        self._status_y_offset: int = hardware_config.getint('display_status_y_offset', fallback=52)
        self._cmc_prefix: str = hardware_config.get('display_cmc_prefix', fallback='CMC:')
        self._font_cmc_path: str = hardware_config.get(
            'display_font_cmc_path',
            fallback='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        )
        self._font_status_path: str = hardware_config.get(
            'display_font_status_path',
            fallback='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        )

        serial = i2c(port=i2c_port, address=i2c_address)
        self._device = ssd1306(serial, width=self.width, height=self.height)

        self._lock = threading.Lock()
        self._cmc: int = 0
        self._status: str = hardware_config.get('display_status_default', fallback='Ready')

        # Use the default PIL bitmap font (always available, no file dependency).
        try:
            self._font_cmc = ImageFont.truetype(self._font_cmc_path, self._font_size_cmc)
            self._font_status = ImageFont.truetype(self._font_status_path, self._font_size_status)
        except OSError:
            self._font_cmc = ImageFont.load_default()
            self._font_status = ImageFont.load_default()

        self._render()

    def set_cmc(self, cmc: int) -> None:
        with self._lock:
            self._cmc = cmc
        self._render()

    def set_status(self, status: str) -> None:
        with self._lock:
            self._status = status
        self._render()

    def update(self, cmc: Optional[int] = None, status: Optional[str] = None) -> None:
        with self._lock:
            if cmc is not None:
                self._cmc = cmc
            if status is not None:
                self._status = status
        self._render()

    def clear(self) -> None:
        with self._lock:
            self._cmc = 0
            self._status = ""
        self._device.clear()

    def cleanup(self) -> None:
        self._device.cleanup()

    def _render(self) -> None:
        with self._lock:
            cmc = self._cmc
            status = self._status

        img = Image.new("1", (self.width, self.height), 0)
        draw = ImageDraw.Draw(img)

        # --- CMC region (top) ---
        cmc_text = f"{self._cmc_prefix} {cmc}"
        bbox = draw.textbbox((0, 0), cmc_text, font=self._font_cmc)
        text_w = bbox[2] - bbox[0]
        x = (self.width - text_w) // 2
        draw.text((x, 2), cmc_text, fill=1, font=self._font_cmc)

        # --- Separator line ---
        sep_y = self._status_y_offset - 4
        draw.line([(0, sep_y), (self.width, sep_y)], fill=1)

        # --- Status region (bottom) ---
        draw.text((2, self._status_y_offset), status, fill=1, font=self._font_status)

        self._device.display(img)
