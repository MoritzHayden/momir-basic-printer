# Momir Basic Printer (MBP)

Momir Basic Printer (MBP) is a set of Python scripts designed to run headless on a Raspberry Pi connected to a thermal receipt printer for playing the [Momir Basic](https://magic.wizards.com/en/formats/momir-basic) MTG format.

## Table of Contents

- [About](#about)
- [Hardware](#hardware)
- [Installation](#installation)
- [Momir Basic Rules](#momir-basic-rules)
- [Disclaimer](#disclaimer)

## About

Downloads card data from the [Scryfall API](https://scryfall.com/docs/api) and prints a random card on demand when a button is pressed. The card images are converted to monochrome and printed using a thermal receipt printer. The card name is also displayed on an OLED screen.

## Hardware

- [Raspberry Pi 3 Model B+](https://www.raspberrypi.com/products/raspberry-pi-3-model-b-plus/)

## Installation

1. Install Python 3 and pip on your Raspberry Pi.

```shell
sudo apt update
sudo apt install python3 python3-pip
```

2. Clone this repository and navigate to the project directory.

```shell
git clone https://github.com/MoritzHayden/momir-basic-printer.git
cd momir-basic-printer
```

3. Install the required Python packages.

```shell
python3 -m pip install -r requirements.txt
```

4. Configure the settings in [config.ini](config.ini) as needed.
5. Run the main script.

```shell
python3 src/main.py
```

## Momir Basic Rules

- Number of Players: 2
- Starting Life Total: 24
- Game Duration: 10 minutes
- Deck Size: 60+ basic lands

Each turn players discard a basic land to activate Momir Vig's ability and get a random creature from throughout Magic's history!

![Momir Vig, Simic Visionary](img/momir_vig.png)

## Disclaimer

Neither this project nor its contributors are associated with Hasbro, Wizards of the Coast, or _Magic: The Gathering_ in any way whatsoever.

<div align="center">
  <p>Copyright &copy; 2026 Hayden Moritz</p>
</div>
