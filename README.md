# Momir Basic Printer (MBP)

Momir Basic Printer (MBP) is a self-contained handheld device powered by an **ESP32-S3** that prints a random Magic: The Gathering creature card on a 58mm thermal receipt printer for playing the [Momir Basic](https://magic.wizards.com/en/formats/momir-basic) format.

Rotate a knob to select a CMC, press the button, and a receipt-style card prints instantly - complete with a Scryfall QR code.

If you are looking for the Raspberry Pi-based version, reference the [main](https://github.com/MoritzHayden/momir-basic-printer/tree/main) branch.

![Momir Vig, Simic Visionary](img/momir.jpg)

## Table of Contents

- [Momir Basic Rules](#momir-basic-rules)
- [How It Works](#how-it-works)
- [Examples](#examples)
  - [Gameplay](#gameplay)
  - [Single Card](#single-card)
  - [Multiple Cards](#multiple-cards)
- [Hardware](#hardware)
  - [Components](#components)
  - [Wiring](#wiring)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Build the Card Database](#1-build-the-card-database)
  - [2. Verify the Database](#2-verify-the-database)
  - [3. Flash the Firmware](#3-flash-the-firmware)
  - [4. Upload the Filesystem](#4-upload-the-filesystem)
- [Project Structure](#project-structure)
- [Receipt Layout](#receipt-layout)
- [Firmware Overview](#firmware-overview)
- [Disclaimer](#disclaimer)

---

## Momir Basic Rules

- **Players:** 2
- **Starting Life:** 24
- **Deck:** 60+ basic lands only

Each turn, discard a basic land to activate Momir Vig's ability and get a token copy of a random creature with that mana value from throughout Magic's history!

---

## How It Works

1. **At boot**, the ESP32 mounts a LittleFS filesystem from flash, reads the pre-built `momir.bin` creature database into PSRAM, and shows all segments on while initializing, then `CMC  0` when ready.
2. **Rotate** the KY-040 encoder to select a CMC (0–16). The TM1637 display updates live showing `CMC` on the left and the value on the right.
3. **Press** the encoder button. The display shows `PrnT`, a random creature at that CMC is picked from PSRAM in O(1) time, and the receipt is sent to the thermal printer over UART.
4. **The receipt** prints the card name, mana cost, a centered Scryfall QR code, type line, oracle text (word-wrapped at 32 chars), and power/toughness.
5. The display returns to showing the selected CMC. Ready for the next turn.

---

## Examples

### Gameplay

![Gameplay](img/gameplay.jpg)

### Single Card

![Single Card](img/single_card.jpg)

### Multiple Cards

![Multiple Cards](img/multiple_cards.jpg)

---

## Hardware

### Components

| Component | Purpose |
|---|---|
| [ESP32-S3 (N16R8)](https://a.co/d/0ieCbILF) | Main MCU — 16MB Flash, 8MB Octal PSRAM |
| [Maikrt Micro Thermal Receipt Printer](https://a.co/d/0d352GD9) | Card output |
| [PAPRMA 57mm Thermal Paper](https://a.co/d/04u2Gb2j) | Receipt paper |
| [TM1637 6-Digit 7-Segment Display](https://a.co/d/0eRUYUOv) | CMC / status display |
| [KY-040 Rotary Encoder](https://a.co/d/07Ihmg2c) | CMC selection + print trigger |
| [Mini 360 Buck Converter](https://a.co/d/020VQw1T) | 7.8V → 5V for ESP32-S3 |
| [2S 7.4V 3300mAh Li-ion Battery](https://a.co/d/07E4YvMv) | Power source |
| [SPST Rocker Switch](https://a.co/d/004xDCoW) | Power toggle |
| [Enclosure Body](stl/enclosure_body.stl) | 3D printed main housing ([source](https://www.printables.com/model/1735878-momir-basic-all-in-one-mtg-printer)) |
| [Enclosure Lid](stl/enclosure_lid.stl) | 3D printed lid ([source](https://www.printables.com/model/1735878-momir-basic-all-in-one-mtg-printer)) |

### Wiring

#### Signal Connections (GPIO)

| Signal | ESP32-S3 GPIO | Connected To |
|---|---|---|
| Printer TX (ESP32 → Printer RX) | GPIO 17 | Printer RX |
| Printer TX (Printer → ESP32) | **DO NOT CONNECT** — printer TX idles at 5V and will damage the 3.3V ESP32-S3 | — |
| TM1637 CLK | GPIO 4 | Display CLK |
| TM1637 DIO | GPIO 5 | Display DIO |
| Encoder CLK (A) | GPIO 6 | KY-040 CLK/A |
| Encoder DT (B) | GPIO 7 | KY-040 DT/B |
| Encoder SW (button) | GPIO 8 | KY-040 SW |

#### Power Path

| From | To | Notes |
|---|---|---|
| 2S Li-ion Battery (+) | SPST Rocker Switch (in) | Switched battery positive |
| SPST Rocker Switch (out) | Mini 360 Buck IN+ | Switched 7.4–8.4V input |
| SPST Rocker Switch (out) | Printer VCC | Printer draws heavy current; powered directly from battery rail |
| 2S Li-ion Battery (−) | Common GND | Battery negative |
| Mini 360 Buck OUT+ | ESP32-S3 5V (VIN) | Regulated 5.0V |
| Mini 360 Buck OUT− | Common GND | |
| ESP32-S3 3V3 | TM1637 VCC | **3.3V only** — see caution below |
| ESP32-S3 3V3 | KY-040 `+` (VCC) | **3.3V only** — see caution below |
| ESP32-S3 GND | TM1637 GND | |
| ESP32-S3 GND | KY-040 GND | |
| ESP32-S3 GND | Printer GND | Signal ground only; printer power is from battery rail |

> [!CAUTION]
> Power the TM1637 and KY-040 from the ESP32-S3 **3V3 pin only**, not the 5V (VIN) pin. Both modules connect their signal lines directly to ESP32-S3 GPIOs. If the modules are powered at 5V their outputs will drive 5V logic into the 3.3V GPIO inputs and will damage the chip.

> [!NOTE]
> All KY-040 encoder pins use `INPUT_PULLUP`. CLK and DT also have on-board 10kΩ pull-ups on the KY-040 module — the doubled pull-up is harmless. The printer serial uses `SERIAL_8N1` at 9600 baud.


---

## Getting Started

### Prerequisites

- [PlatformIO](https://platformio.org/) (CLI or VS Code extension)
- Python 3 + `curl` (for building the card database)
- A USB-C cable connected to the **right-side USB-C port** on the ESP32-S3 DevKit (the CH343P UART bridge port, used for flashing and serial monitoring). The left-side native USB port is not used for this project.

### 1. Build the Card Database

Download the latest Scryfall oracle card data and pack all creature cards into the binary format used by the firmware. This step requires an internet connection and takes ~1–2 minutes.

```shell
chmod +x tools/build_momir_bin.sh
tools/build_momir_bin.sh
```

This produces `data/momir.bin` — a compact indexed binary of every paper-legal Magic creature, grouped by CMC (0–16), totalling ~4.5 MB. A pre-built copy is already committed to the repository so this step is only needed when you want to refresh the card data.

> [!TIP]
> The Scryfall bulk data is updated daily. Re-run this script periodically to include newly printed cards.

### 2. Verify the Database

Confirm the binary is well-formed and random lookups work correctly:

```shell
python3 tools/verify_bin.py
```

Expected output shows card counts per CMC and a sample of 3 random card lookups, e.g.:

```
=== 1. Header Validation ===
CMC  0:   35 cards  ...
CMC  1: 1217 cards  ...
...
Total indexed creatures: 18097

=== 2. Random O(1) Lookup Test ===
[CMC 5 | Index 742 | Offset 1849302]
Name:  Thragtusk {4}{G}
Type:  Creature — Beast
P/T:   5/3
...
```

### 3. Flash the Firmware

Build and upload the Arduino firmware to the ESP32-S3:

```shell
pio run --target upload
```

Monitor the serial output (115200 baud) to confirm boot:

```shell
pio device monitor
```

You should see:

```
[MBP] Momir Basic Printer booting...
[MBP] Printer initialized.
Database loaded to PSRAM: 4531234 bytes.
[MBP] Database ready. Entering main loop.
```

### 4. Upload the Filesystem

Flash the `data/` directory as a LittleFS image. This makes `momir.bin` available to the firmware at `/momir.bin`:

```shell
pio run --target uploadfs
```

> [!IMPORTANT]
> Do steps 3 and 4 in any order, but **both must be done** before the device will function. If the database fails to load, the display will show `Err` and the device will halt.

---

## Project Structure

```
momir-basic-printer/
├── data/
│   └── momir.bin          # Pre-built creature database (LittleFS → /momir.bin)
├── img/
│   └── momir.jpg          # Docs image
├── src/
│   ├── main.cpp           # Application entry point (setup/loop)
│   ├── CardDb.h           # LittleFS + PSRAM database loader and random lookup
│   ├── Encoder.h          # KY-040 rotary encoder driver (Gray-code + debounce)
│   └── Printer.h          # Raw ESC/POS thermal printer driver
├── tools/
│   ├── build_momir_bin.sh # Download Scryfall data and build momir.bin
│   └── verify_bin.py      # Verify momir.bin structure and test random lookups
├── partitions_16mb.csv    # Flash partition table (3MB app + 13MB LittleFS)
└── platformio.ini         # PlatformIO build config
```

---

## Receipt Layout

Each printed card follows this layout:

```
Card Name               {X}{Y}{Z}
       [ QR CODE (Scryfall link) ]
        Creature — Subtype
Keyword ability.

Oracle text wrapped cleanly at
32 characters per line.

                            P / T
```

- **Name + mana cost** are space-padded to fill the 32-character line width
- **QR code** links directly to the card's Scryfall page (`https://scryfall.com/card/{uuid}`) and is centered using native ESC/POS `GS ( k` commands
- **Type line** is centered
- **Oracle text** is word-wrapped at 32 characters with blank lines between paragraphs; Unicode (em-dashes, smart quotes, bullets) is normalized to ASCII
- **Power/Toughness** is right-aligned with spaces around the slash (e.g. `5 / 5`)
- **3 blank lines** are fed after each card to clear the manual tear bar

---

## Firmware Overview

### `src/CardDb.h`

Mounts LittleFS, allocates the full `momir.bin` into 8MB Octal PSRAM via `ps_malloc`, and exposes `getRandomCard(uint8_t cmc, CardRecord& out)`. Card lookup is O(1): the binary header stores a per-CMC offset table, so selecting a random card requires exactly two seeks and one `memcpy`.

### `src/Encoder.h`

Reads the KY-040 rotary encoder using a **4-state Gray-code state table** — reliable quadrature decoding with no debounce delays on the AB signal. The push-button uses a separate 50 ms timer-based debouncer. CMC is hard-clamped to `[0, 16]` via `constrain()`. The KY-040 module has on-board 10kΩ pull-ups on CLK and DT; the firmware also applies `INPUT_PULLUP` on all three pins — the doubled pull-up on CLK/DT is harmless. SW has no on-board pull-up on most KY-040 modules, so the firmware's `INPUT_PULLUP` on GPIO 8 is necessary.

### `src/Printer.h`

Sends raw **ESC/POS** byte sequences over `HardwareSerial1`:

| Command | Purpose |
|---|---|
| `ESC @` | Initialize printer |
| `ESC E n` | Bold on/off |
| `ESC a n` | Alignment (left / center / right) |
| `GS ( k` | Native QR code (Model 2, Level M, module size 4) |
| `ESC d n` | Feed n lines |

### `src/main.cpp`

Orchestrates everything: initializes hardware in `setup()`, then in `loop()` polls the encoder, updates the TM1637 display, and on button press fetches a card from `CardDb`, builds the Scryfall URL from the raw UUID bytes, shows `PrnT` on the display, calls `Printer::printCard()`, and returns to showing the CMC.

### `platformio.ini`

Key build flags for the N16R8 variant:

```ini
board_build.arduino.memory_type = qio_opi   ; Required for 8MB Octal PSRAM
build_flags =
    -DBOARD_HAS_PSRAM
    -mfix-esp32-psram-cache-issue
board_build.partitions = partitions_16mb.csv ; 16MB flash layout
board_build.filesystem = littlefs
```

---

## Disclaimer

Neither this project nor its contributors are associated with Hasbro, Wizards of the Coast, or _Magic: The Gathering_ in any way whatsoever.

<div align="center">
  <p>Copyright &copy; 2026 Hayden Moritz</p>
</div>
