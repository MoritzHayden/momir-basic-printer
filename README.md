# Momir Basic Printer (MBP)

Momir Basic Printer (MBP) is a set of Python scripts designed to run headless on a Raspberry Pi connected to a thermal receipt printer for playing the [Momir Basic](https://magic.wizards.com/en/formats/momir-basic) MTG format.

> [!NOTE]
> This project is a work in progress and is not yet fully functional. Please check back for updates as I continue to work on this project!

## TODO

- [ ] Implement button input
- [ ] Implement rotary encoder input
- [ ] Implement OLED display output
- [ ] Implement thermal printer integration
- [ ] Add completed hardware photos to [README.md](README.md)

## Table of Contents

- [About](#about)
- [Examples](#examples)
- [Hardware](#hardware)
  - [Components](#components)
  - [Diagram](#diagram)
- [Installation](#installation)
- [Configuration](#configuration)
- [Service Management](#service-management)
- [Momir Basic Rules](#momir-basic-rules)
- [Disclaimer](#disclaimer)

## About

Downloads card data from the [Scryfall API](https://scryfall.com/docs/api), including card art which is dithered to monochrome on-device, and prints a random card within a set CMC value on demand via thermal printer. All settings are configurable via [config.ini](src/config.ini), and the software can run as a background service on any Linux-based SBC with GPIO. The complete hardware setup is designed to be compact and portable, with all components housed in a waterproof case.

## Examples

| Physical Card                                           | Printed Card                                              |
| ------------------------------------------------------- | --------------------------------------------------------- |
| ![Physical Chrome Courier](img/chrome_courier_card.jpg) | ![Printed Chrome Courier](img/chrome_courier_receipt.jpg) |

## Hardware

### Components

- [Raspberry Pi 3 Model B+](https://www.raspberrypi.com/products/raspberry-pi-3-model-b-plus/)
- [Adafruit T-Cobbler Plus GPIO Breakout](https://a.co/d/0fnKGt3A)
- [Maikrt MC206H Thermal Printer](https://a.co/d/06qIKsng)
- [PAPRMA 57mm x 30mm Thermal Paper](https://a.co/d/04u2Gb2j)
- [MakerFocus 20200330-SD8V OLED Display](https://a.co/d/06Y7V5Uj)
- [KY-040 Rotary Encoder Module](https://a.co/d/0hN4SBto)
- [Nilight 12V 20A SPST Rocker Toggle Switch](https://a.co/d/02VcvtcQ)
- [EG STARTS 24mm Arcade Push Buttons](https://a.co/d/0jlW1BSk)
- [SHNITPWR 60W Universal Power Supply](https://a.co/d/0bKNzwey)
- [LM2596 Buck Converter](https://a.co/d/070NjEDp)
- [KeeYees 4 Channel IIC I2C Logic Level Converter](https://a.co/d/0ecOK7n6)

### Diagram

![Hardware Diagram](img/hardware_diagram.jpg)

## Installation

1. Clone this repository and navigate to the project directory.

```shell
git clone https://github.com/MoritzHayden/momir-basic-printer.git
cd momir-basic-printer
```

2. Open [src/config.ini](src/config.ini) in a text editor and update the configuration variables to add your specific settings (like printer connection details, GPIO pins, and other hardware settings) before proceeding.

```shell
nano src/config.ini
```

3. Make the setup script executable and run it. This will automatically install dependencies and configure the systemd background service.

```shell
chmod +x setup.sh
./setup.sh
```

> [!TIP]
> If you are running a minimal setup and explicitly require the service to run as root, you can bypass the safety check by running: `sudo ./setup.sh --allow-root`

## Configuration

All configuration variables are stored in [src/config.ini](src/config.ini). Update the values in this file to match your specific hardware setup and preferences. After making changes to the configuration, restart the service for the changes to take effect.

| **Section**  | **Variable**                    | **Type**  | **Description**                                                           |
| ------------ | ------------------------------- | --------- | ------------------------------------------------------------------------- |
| `APP`        | `booting_status`                | `string`  | Status string shown while services initialize                             |
| `APP`        | `ready_status`                  | `string`  | Status string shown when the appliance is idle/ready                      |
| `APP`        | `refreshing_status`             | `string`  | Status string shown during initial data refresh                           |
| `APP`        | `fetching_status`               | `string`  | Status string shown while selecting/fetching a card                       |
| `APP`        | `printing_status`               | `string`  | Status string shown while sending output to printer                       |
| `APP`        | `cancelled_status`              | `string`  | Status string shown when active work is cancelled                         |
| `APP`        | `error_status`                  | `string`  | Status string shown when fetch/print fails                                |
| `APP`        | `reset_status`                  | `string`  | Status string shown after long-press reset                                |
| `APP`        | `services_unavailable_status`   | `string`  | Status string shown when printer/Scryfall services are unavailable        |
| `APP`        | `no_cmc_status_template`        | `string`  | Template used when no card exists for selected CMC (supports `{cmc}`)     |
| `APP`        | `shutdown_join_timeout_seconds` | `float`   | Max wait time for worker thread during shutdown                           |
| `APP`        | `printed_status_name_max_len`   | `integer` | Maximum card-name length shown on status line after printing              |
| `FILESYSTEM` | `cards_path`                    | `string`  | Directory path where card JSON files are stored                           |
| `FILESYSTEM` | `art_path`                      | `string`  | Directory path where card artwork images are stored                       |
| `FILESYSTEM` | `default_card_art_path`         | `string`  | File path to default placeholder image for cards without artwork          |
| `FILESYSTEM` | `access_rights`                 | `octal`   | File system permissions for created directories (octal notation)          |
| `HARDWARE`   | `serial_port`                   | `string`  | Serial device path for the thermal printer (e.g., `/dev/serial0`)         |
| `HARDWARE`   | `serial_baud_rate`              | `integer` | Baud rate for the serial printer connection (e.g., `9600` or `19200`)     |
| `HARDWARE`   | `gpio_encoder_clk`              | `integer` | BCM GPIO pin for rotary encoder CLK signal (default: `13`)                |
| `HARDWARE`   | `gpio_encoder_dt`               | `integer` | BCM GPIO pin for rotary encoder DT signal (default: `6`)                  |
| `HARDWARE`   | `gpio_encoder_sw`               | `integer` | BCM GPIO pin for rotary encoder push-button switch (default: `5`)         |
| `HARDWARE`   | `gpio_printer_dtr`              | `integer` | BCM GPIO pin for printer DTR hardware flow control (default: `17`)        |
| `HARDWARE`   | `i2c_address`                   | `hex`     | I2C hex address of the SSD1306 OLED display (default: `0x3C`)             |
| `HARDWARE`   | `i2c_port`                      | `integer` | I2C bus port number (default: `1`)                                        |
| `HARDWARE`   | `oled_width`                    | `integer` | OLED display width in pixels (default: `128`)                             |
| `HARDWARE`   | `oled_height`                   | `integer` | OLED display height in pixels (default: `64`)                             |
| `HARDWARE`   | `display_font_size_cmc`         | `integer` | Font size for the main CMC text on OLED                                   |
| `HARDWARE`   | `display_font_size_status`      | `integer` | Font size for the status text on OLED                                     |
| `HARDWARE`   | `display_status_y_offset`       | `integer` | Vertical Y offset (px) for status text region                             |
| `HARDWARE`   | `display_status_default`        | `string`  | Default status text shown during display initialization                   |
| `HARDWARE`   | `display_font_cmc_path`         | `string`  | Font file path used for CMC text rendering                                |
| `HARDWARE`   | `display_font_status_path`      | `string`  | Font file path used for status text rendering                             |
| `HARDWARE`   | `display_cmc_prefix`            | `string`  | Prefix label used before current CMC value (e.g., `CMC:`)                 |
| `HARDWARE`   | `hold_time`                     | `float`   | Seconds the encoder button must be held for a long-press action           |
| `HARDWARE`   | `cmc_min`                       | `integer` | Minimum selectable CMC value (default: `0`)                               |
| `HARDWARE`   | `cmc_max`                       | `integer` | Maximum selectable CMC value (default: `16`)                              |
| `HARDWARE`   | `dtr_poll_interval`             | `float`   | Seconds between DTR pin polls when printer buffer is full                 |
| `LOGGING`    | `log_level`                     | `string`  | Logging verbosity level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `LOGGING`    | `log_format`                    | `string`  | Format string for log messages                                            |
| `LOGGING`    | `log_date_format`               | `string`  | Format string for timestamps in log messages                              |
| `PRINTER`    | `paper_width_mm`                | `integer` | Physical width of thermal paper in millimeters                            |
| `PRINTER`    | `paper_width_chars`             | `integer` | Maximum number of characters per line for text wrapping                   |
| `PRINTER`    | `card_art_enabled`              | `boolean` | Whether to print card artwork images on receipts                          |
| `PRINTER`    | `qr_code_enabled`               | `boolean` | Whether to print QR codes linking to Scryfall card details                |
| `PRINTER`    | `qr_code_size`                  | `integer` | Size of QR code in printer units (larger = bigger QR code)                |
| `PRINTER`    | `dpi`                           | `integer` | Printer resolution in dots per inch for image rendering                   |
| `PRINTER`    | `vendor_id`                     | `hex`     | USB vendor ID for the thermal printer device                              |
| `PRINTER`    | `product_id`                    | `hex`     | USB product ID for the thermal printer device                             |
| `PRINTER`    | `printer_profile`               | `string`  | ESC/POS printer profile name for compatibility                            |
| `PRINTER`    | `printer_media_width_px`        | `integer` | Media width in pixels for image processing and scaling                    |
| `PRINTER`    | `min_title_spacing`             | `integer` | Minimum spaces between card name and mana cost on title line              |
| `PRINTER`    | `paragraph_spacing`             | `string`  | Escaped spacing appended after wrapped oracle text paragraphs             |
| `PRINTER`    | `text_replacements_json`        | `json`    | Character replacement map for printer-safe text normalization             |
| `SCRYFALL`   | `base_url`                      | `string`  | Base URL for Scryfall API requests                                        |
| `SCRYFALL`   | `bulk_data_endpoint`            | `string`  | API endpoint path for bulk card data download                             |
| `SCRYFALL`   | `header_accept`                 | `string`  | HTTP Accept header value for API content negotiation                      |
| `SCRYFALL`   | `header_user_agent`             | `string`  | HTTP User-Agent header identifying the client application                 |
| `SCRYFALL`   | `header_accept_encoding`        | `string`  | HTTP Accept-Encoding header for compression support                       |
| `SCRYFALL`   | `request_delay_seconds`         | `float`   | Delay between consecutive API requests to respect rate limits             |
| `SCRYFALL`   | `max_retries`                   | `integer` | Maximum number of retry attempts for failed API requests                  |
| `SCRYFALL`   | `art_width_px`                  | `integer` | Target width in pixels for downloaded card artwork                        |
| `SCRYFALL`   | `excluded_sets`                 | `list`    | Comma-separated card sets to exclude (e.g., `funny`, `memorabilia`)       |
| `SCRYFALL`   | `excluded_layouts`              | `list`    | Comma-separated card layouts to exclude (e.g., `token`, `emblem`)         |

## Service Management

View live logs and print statements:

```shell
sudo journalctl -u momir-basic-printer.service -f
```

Check the current status of the service:

```shell
sudo systemctl status momir-basic-printer.service
```

Restart the service (required after making code changes):

```shell
sudo systemctl restart momir-basic-printer.service
```

Stop the service:

```shell
sudo systemctl stop momir-basic-printer.service
```

## Momir Basic Rules

- Number of Players: 2
- Starting Life Total: 24
- Game Duration: 10 minutes
- Deck Size: 60+ basic lands

Each turn players discard a basic land to activate Momir Vig's ability and get a random creature from throughout Magic's history!

![Momir Vig, Simic Visionary](img/momir_vig.jpg)

## Disclaimer

Neither this project nor its contributors are associated with Hasbro, Wizards of the Coast, or _Magic: The Gathering_ in any way whatsoever.

<div align="center">
  <p>Copyright &copy; 2026 Hayden Moritz</p>
</div>
