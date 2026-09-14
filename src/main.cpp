#include <Arduino.h>
#include <TM1637Display.h>

#include "CardDb.h"
#include "Encoder.h"
#include "Printer.h"

// ── Pin Definitions ─────────────────────────────────────────────────────────

// Thermal printer – HardwareSerial1
static constexpr int PRINTER_TX_PIN = 17; // ESP32 TX → Printer RX
static constexpr int PRINTER_RX_PIN = 18; // ESP32 RX ← Printer TX
static constexpr uint32_t PRINTER_BAUD = 9600;

// TM1637 4-digit display
static constexpr int DISPLAY_CLK = 7;
static constexpr int DISPLAY_DIO = 8;

// EC11 Rotary Encoder
static constexpr int ENC_CLK = 4;
static constexpr int ENC_DT = 5;
static constexpr int ENC_SW = 6;

// ── Constants ────────────────────────────────────────────────────────────────

static constexpr int CMC_MIN = 0;
static constexpr int CMC_MAX = 16;

// ── Global Objects ───────────────────────────────────────────────────────────

TM1637Display display(DISPLAY_CLK, DISPLAY_DIO);
RotaryEncoder encoder(ENC_CLK, ENC_DT, ENC_SW, CMC_MIN, CMC_MAX, /*debounceMs=*/50);
ThermalPrinter printer;
CardDb db;

// Application state
static volatile bool isPrinting = false;

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Format the raw 16-byte Scryfall UUID stored in a CardRecord into a
 * Scryfall search URL: https://scryfall.com/search?q=id%3Axxxxxxxx-xxxx-...
 *
 * @param uuid    Pointer to 16 raw UUID bytes (big-endian, as stored in momir.bin)
 * @param buf     Output buffer (must be at least 83 bytes)
 * @param bufLen  Size of buf
 */
static void formatScryfallUrl(const uint8_t *uuid, char *buf, size_t bufLen)
{
    // UUID string: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  (36 chars)
    char uuidStr[37];
    snprintf(uuidStr, sizeof(uuidStr),
             "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
             uuid[0], uuid[1], uuid[2], uuid[3],
             uuid[4], uuid[5],
             uuid[6], uuid[7],
             uuid[8], uuid[9],
             uuid[10], uuid[11], uuid[12], uuid[13], uuid[14], uuid[15]);

    // Scryfall search by exact ID: https://scryfall.com/search?q=id%3A{uuid}
    snprintf(buf, bufLen, "https://scryfall.com/search?q=id%%3A%s", uuidStr);
}

// ── Display Helpers ──────────────────────────────────────────────────────────

/**
 * Show the current CMC value on the TM1637 display.
 * Values 0–9 are right-aligned in the two rightmost digits.
 * Values 10–16 use both rightmost digits (e.g. " 10", " 16").
 */
void showCmc(int cmc)
{
    // Clear the left two digits first so they're dark before the number appears.
    display.setSegments((const uint8_t[]){0x00, 0x00}, 2, 0);
    // showNumberDec: no leading zeros, 2 digits wide, starting at position 2 (right pair).
    display.showNumberDec(cmc, /*leading_zero=*/false, /*length=*/2, /*pos=*/2);
}

/**
 * Animate "----" on the display while printing.
 * Call repeatedly; the pattern toggles every ~300 ms.
 */
static uint8_t _animFrame = 0;
static uint32_t _animLastMs = 0;

void animatePrinting()
{
    uint32_t now = millis();
    if (now - _animLastMs < 300)
        return;
    _animLastMs = now;

    // Alternate between "----" and "    " (blank) for a blink effect.
    if (_animFrame & 1)
    {
        // All four digits showing a middle dash segment (0x40).
        const uint8_t dashes[4] = {0x40, 0x40, 0x40, 0x40};
        display.setSegments(dashes);
    }
    else
    {
        display.clear();
    }
    _animFrame++;
}

// ── Setup ────────────────────────────────────────────────────────────────────

void setup()
{
    Serial.begin(115200);
    delay(500);
    Serial.println("[MBP] Momir Basic Printer booting...");

    // ── TM1637 Display ────────────────────────────────────────────────────
    display.setBrightness(7); // Maximum brightness (0–7)
    display.clear();
    // Show "boot" indicator: all segments on during init.
    const uint8_t boot[4] = {0x7F, 0x7F, 0x7F, 0x7F};
    display.setSegments(boot);

    // ── Rotary Encoder ────────────────────────────────────────────────────
    encoder.begin();

    // ── Thermal Printer ───────────────────────────────────────────────────
    printer.begin(Serial1, PRINTER_TX_PIN, PRINTER_RX_PIN, PRINTER_BAUD);
    Serial.println("[MBP] Printer initialized.");

    // ── Card Database (LittleFS + PSRAM) ─────────────────────────────────
    if (!db.begin())
    {
        Serial.println("[MBP] FATAL: Database load failed.");
        display.clear();
        // Show "Err " on the display.
        const uint8_t err[4] = {
            0x79, // E
            0x50, // r
            0x50, // r
            0x00  // blank
        };
        display.setSegments(err);
        while (true)
            delay(1000);
    }

    Serial.println("[MBP] Database ready. Entering main loop.");
    display.clear();
    showCmc(encoder.getValue());
}

// ── Main Loop ────────────────────────────────────────────────────────────────

void loop()
{
    encoder.poll();

    if (!isPrinting)
    {
        // Update display whenever the knob position might have changed.
        static int lastCmc = -1;
        int cmc = encoder.getValue();
        if (cmc != lastCmc)
        {
            lastCmc = cmc;
            showCmc(cmc);
            Serial.printf("[MBP] CMC selected: %d\n", cmc);
        }

        // Check for a button press to trigger a print.
        if (encoder.wasPressed())
        {
            int selectedCmc = encoder.getValue();
            Serial.printf("[MBP] Button pressed — printing CMC %d\n", selectedCmc);

            isPrinting = true;
            _animFrame = 0;
            _animLastMs = 0;

            CardRecord card;
            if (!db.getRandomCard((uint8_t)selectedCmc, card))
            {
                Serial.printf("[MBP] No cards for CMC %d\n", selectedCmc);
                // Flash display briefly to signal "no card".
                display.clear();
                delay(300);
                showCmc(selectedCmc);
                isPrinting = false;
                return;
            }

            // Print the card — display animates during the blocking send.
            // We drive the animation manually by calling animatePrinting()
            // inside a brief delay loop.  The actual serial write in printCard()
            // is blocking but fast (a few hundred ms at 9600 baud for most cards).
            // We show the animation before/after; for long oracle texts the
            // blocking nature of Serial.write means animation only runs between
            // lines, which is acceptable.

            Serial.printf("[MBP] Printing: %s\n", card.name);

            // Build Scryfall URL from the card UUID for the QR code.
            // Buffer: "https://scryfall.com/search?q=id%3A" (35) + uuid (36) + '\0' = 72
            char scryfallUrl[80];
            formatScryfallUrl(card.uuid, scryfallUrl, sizeof(scryfallUrl));
            Serial.printf("[MBP] QR URL: %s\n", scryfallUrl);

            // Show "PRNT" on the display while printing.
            // P=0x73, r=0x50, n=0x54, t=0x78
            const uint8_t prntSeg[4] = {0x73, 0x50, 0x54, 0x78};
            display.setSegments(prntSeg);

            printer.printCard(
                card.name,
                card.mana,
                card.type_line,
                card.oracle,
                card.pt,
                scryfallUrl);

            Serial.printf("[MBP] Print complete: %s\n", card.name);

            isPrinting = false;
            showCmc(encoder.getValue());
        }
    }
    else
    {
        // Guard: if somehow isPrinting is stuck, animate and let loop run.
        animatePrinting();
    }
}
