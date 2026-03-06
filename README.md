# Momir Basic Printer (MBP)

Momir Basic Printer (MBP) is a set of Python scripts designed to run headless on a Raspberry Pi connected to a thermal receipt printer for playing the [Momir Basic](https://magic.wizards.com/en/formats/momir-basic) MTG format.

## Table of Contents

- [About](#about)
- [Hardware](#hardware)
  - [Components](#components)
  - [Pinout](#pinout)
- [Installation](#installation)
- [Service Management](#service-management)
- [Momir Basic Rules](#momir-basic-rules)
- [Disclaimer](#disclaimer)

## About

Downloads card data from the [Scryfall API](https://scryfall.com/docs/api) and prints a random card on demand when a button is pressed. The card images are converted to monochrome and printed using a thermal receipt printer. The card name is also displayed on an OLED screen.

## Hardware

### Components

- [Raspberry Pi 3 Model B+](https://www.raspberrypi.com/products/raspberry-pi-3-model-b-plus/)
- [Raspberry Pi 3 Case](https://a.co/d/0bsgVSjd)
- [Maikrt MC206H Thermal Receipt Printer](https://a.co/d/06qIKsng)
- [BuyRegisterRolls 57mm x 30mm Thermal Receipt Paper](https://a.co/d/00LGsMJn)
- [MakerFocus 20200330-SD8V OLED Display](https://a.co/d/06Y7V5Uj)
- [Assorted Jumper Wires](https://a.co/d/0evrCTOw)
- [CASEMATIX Graded Card Case](https://a.co/d/0cv4oRv7)
- [KY-040 Rotary Encoder Module](https://a.co/d/0hN4SBto)
- [Twidec SPST KCD3-101 Rocker Switch](https://a.co/d/00npt3Dj)
- [SHNITPWR 60W Universal Power Supply](https://a.co/d/0bKNzwey)
- [DaierTek DC Barrel Jack](https://a.co/d/093TzIyP)
- [Gebildet 12mm Momemtary Push Button](https://a.co/d/0gaiNBBG)
- TODO: Momentary Push Button Switches (OBSF-30 or similar)
- TODO: Voltage Step-Down	(LM2596 DC-DC Adjustable Buck Converter Module)
- TODO: Logic Level Shifter	4-Channel Bidirectional Logic Level Converter (Adafruit BSS138 or TXB0108)
- TODO: Mounting Hardware	(M2.5 Brass Standoffs, Screws, and Nuts Assortment)

### Pinout

...

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

_(Note: If you are running a minimal setup and explicitly require the service to run as root, you can bypass the safety check by running `sudo ./setup.sh --allow-root`)_

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
