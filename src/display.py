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
        self._cmc_min: int = hardware_config.getint('cmc_min', fallback=0)
        self._cmc_max: int = hardware_config.getint('cmc_max', fallback=16)
        self._padding_x: int = hardware_config.getint('display_padding_x', fallback=2)
        self._cmc_value_gap: int = hardware_config.getint('display_cmc_value_gap', fallback=6)

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

        self._fit_cmc_font_to_screen()

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

    def _text_size(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def _fit_cmc_font_to_screen(self) -> None:
        """Reduce CMC font size until the widest expected CMC label fits the top region."""
        sample_img = Image.new("1", (1, 1), 0)
        sample_draw = ImageDraw.Draw(sample_img)

        sample_value = str(max(abs(self._cmc_min), abs(self._cmc_max)))
        available_width = max(1, self.width - (2 * self._padding_x))
        sep_y = self._status_y_offset - 4
        available_height = max(1, sep_y - 2)

        for size in range(self._font_size_cmc, 7, -1):
            try:
                test_font = ImageFont.truetype(self._font_cmc_path, size)
            except OSError:
                return

            prefix_w, prefix_h = self._text_size(sample_draw, self._cmc_prefix, test_font)
            value_w, value_h = self._text_size(sample_draw, sample_value, test_font)
            total_w = prefix_w + self._cmc_value_gap + value_w
            total_h = max(prefix_h, value_h)
            if total_w <= available_width and total_h <= available_height:
                self._font_cmc = test_font
                return

    def _truncate_to_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        max_width: int,
    ) -> str:
        if max_width <= 0:
            return ""

        text_w, _ = self._text_size(draw, text, font)
        if text_w <= max_width:
            return text

        ellipsis = "..."
        ellipsis_w, _ = self._text_size(draw, ellipsis, font)
        if ellipsis_w > max_width:
            return ""

        candidate = text
        while candidate:
            candidate = candidate[:-1]
            candidate_w, _ = self._text_size(draw, candidate, font)
            if candidate_w + ellipsis_w <= max_width:
                return candidate + ellipsis

        return ""

    def _render(self) -> None:
        with self._lock:
            cmc = self._cmc
            status = self._status

            img = Image.new("1", (self.width, self.height), 0)
            draw = ImageDraw.Draw(img)

            # --- CMC region (top) ---
            prefix_text = self._cmc_prefix
            value_text = str(cmc)
            sep_y = self._status_y_offset - 4

            prefix_w, prefix_h = self._text_size(draw, prefix_text, self._font_cmc)
            value_w, value_h = self._text_size(draw, value_text, self._font_cmc)
            line_h = max(prefix_h, value_h)
            top_region_height = max(1, sep_y - 1)
            y = max(0, (top_region_height - line_h) // 2)

            total_w = prefix_w + self._cmc_value_gap + value_w
            available_w = self.width - (2 * self._padding_x)
            x_start = self._padding_x + max(0, (available_w - total_w) // 2)

            draw.text((x_start, y), prefix_text, fill=1, font=self._font_cmc)
            draw.text((x_start + prefix_w + self._cmc_value_gap, y), value_text, fill=1, font=self._font_cmc)

            # --- Separator line ---
            draw.line([(0, sep_y), (self.width, sep_y)], fill=1)

            # --- Status region (bottom) ---
            available_status_w = self.width - (2 * self._padding_x)
            status_text = self._truncate_to_width(draw, status, self._font_status, available_status_w)
            draw.text((self._padding_x, self._status_y_offset), status_text, fill=1, font=self._font_status)

            self._device.display(img)
