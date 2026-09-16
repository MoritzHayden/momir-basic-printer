#include <Arduino.h>
#include <TM1637Display.h>

#include "CardDb.h"
#include "Encoder.h"
#include "Printer.h"

// ── Pin Definitions ─────────────────────────────────────────────────────────

// Thermal printer – HardwareSerial1
static constexpr int PRINTER_TX_PIN = 17;  // ESP32 TX → Printer RX
static constexpr int PRINTER_RX_PIN = -1;  // Printer TX: UNCONNECTED — idles at 5V, would damage ESP32
static constexpr uint32_t PRINTER_BAUD = 9600;

// TM1637 4-digit display
static constexpr int DISPLAY_CLK = 4;  // spec: CLK  = GPIO 4
static constexpr int DISPLAY_DIO = 5;  // spec: DIO  = GPIO 5

// KY-040 Rotary Encoder
static constexpr int ENC_CLK = 6;  // spec: Channel A   = GPIO 6, INPUT_PULLUP
static constexpr int ENC_DT  = 7;  // spec: Channel B   = GPIO 7, INPUT_PULLUP
static constexpr int ENC_SW  = 8;  // spec: Push Button = GPIO 8, INPUT_PULLUP (active LOW)

// ── Constants ────────────────────────────────────────────────────────────────

// Compile-time upper bound for validCmcs[] array sizing only.
// The actual navigable range is derived from the binary header at boot via
// db.getCmcSlots() and is not constrained by this value at runtime.
static constexpr uint8_t CMC_SLOTS_CAPACITY = 64;

// Encoder placeholder range before setRange() is called after db loads.
static constexpr int ENC_INIT_MIN = 0;
static constexpr int ENC_INIT_MAX = CMC_SLOTS_CAPACITY - 1;

// ── Global Objects ───────────────────────────────────────────────────────────

TM1637Display display(DISPLAY_CLK, DISPLAY_DIO);
RotaryEncoder encoder(ENC_CLK, ENC_DT, ENC_SW, ENC_INIT_MIN, ENC_INIT_MAX, /*debounceMs=*/50);
ThermalPrinter printer;
CardDb db;

// Valid CMC navigation list — populated from the database at boot.
// The encoder navigates indices 0..(validCmcCount-1); use validCmcs[idx] to
// get the actual CMC value (skipping any CMC with 0 creatures).
static uint8_t validCmcs[CMC_SLOTS_CAPACITY];
static uint8_t validCmcCount = 0;

// Application state
static volatile bool isPrinting = false;


// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Format the raw 16-byte Scryfall UUID stored in a CardRecord into a
 * direct Scryfall card page URL: https://scryfall.com/card/xxxxxxxx-xxxx-...
 *
 * @param uuid    Pointer to 16 raw UUID bytes (big-endian, as stored in momir.bin)
 * @param buf     Output buffer (must be at least 64 bytes)
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

    // Direct card page: https://scryfall.com/card/{uuid}
    snprintf(buf, bufLen, "https://scryfall.com/card/%s", uuidStr);
}


// ── Display Helpers ──────────────────────────────────────────────────────────

/**
 * Show the current CMC value on the 6-digit TM1637 display.
 *
 * Layout:  [ C ][ M ][ C ][   ][ ? ][ ? ]
 *            0    1    2    3    4    5
 *
 * Position 3 is a blank spacer.
 * Single-digit CMC (0–9):  position 4 blank, position 5 = digit.
 * Two-digit CMC  (10–16):  position 4 = tens, position 5 = units.
 *
 * Segment encoding (TM1637Display standard):
 *   bit 0 = a (top)          bit 4 = e (bottom-left)
 *   bit 1 = b (top-right)    bit 5 = f (top-left)
 *   bit 2 = c (bottom-right) bit 6 = g (middle)
 *   bit 3 = d (bottom)
 *
 *   C = a+d+e+f        = 0x39
 *   M = a+b+c+e+f      = 0x37  (outer frame: top + all four verticals)
 */
void showCmc(int cmc)
{
    // Standard 7-segment digit codes 0–9.
    static const uint8_t DIGITS[10] = {
        0x3F, 0x06, 0x5B, 0x4F, 0x66,
        0x6D, 0x7D, 0x07, 0x7F, 0x6F
    };

    uint8_t segs[6];
    segs[0] = 0x39; // C
    segs[1] = 0x37; // M
    segs[2] = 0x39; // C
    segs[3] = 0x00; // blank spacer

    if (cmc < 10)
    {
        segs[4] = 0x00;           // blank
        segs[5] = DIGITS[cmc];    // single digit at far right
    }
    else
    {
        segs[4] = DIGITS[cmc / 10]; // tens
        segs[5] = DIGITS[cmc % 10]; // units
    }

    // Write all 6 positions in one call — no digit is left showing stale data.
    display.setSegments(segs, 6, 0);
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
    // Show "boot" indicator: all 6 segments fully on during init.
    const uint8_t boot[6] = {0x7F, 0x7F, 0x7F, 0x7F, 0x7F, 0x7F};
    display.setSegments(boot, 6, 0);

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
        // Show "Err " across all 6 digits.
        const uint8_t err[6] = {0x79, 0x50, 0x50, 0x00, 0x00, 0x00};
        display.setSegments(err, 6, 0);
        while (true)
            delay(1000);
    }

    // ── Build valid CMC list ───────────────────────────────────────────────
    // Scan all CMC buckets; keep only those with at least one creature.
    // The encoder will navigate indices into this list, so CMC 14 (and any
    // other empty bucket) is simply never reachable from the knob.
    for (uint8_t i = 0; i < db.getCmcSlots(); i++)
    {
        if (db.getCount(i) > 0)
            validCmcs[validCmcCount++] = i;
    }
    if (validCmcCount == 0)
    {
        // Should never happen with a valid momir.bin.
        Serial.println("[MBP] FATAL: No creatures found in database.");
        const uint8_t err[6] = {0x79, 0x50, 0x50, 0x00, 0x00, 0x00};
        display.setSegments(err, 6, 0);
        while (true)
            delay(1000);
    }
    Serial.printf("[MBP] Valid CMC buckets: %d  (range CMC %d – CMC %d)\n",
                  validCmcCount, validCmcs[0], validCmcs[validCmcCount - 1]);

    // Configure encoder to wrap through valid indices only.
    encoder.setRange(0, validCmcCount - 1);

    Serial.println("[MBP] Database ready. Entering main loop.");
    display.clear();
    showCmc(validCmcs[encoder.getValue()]);
}


// ── Main Loop ────────────────────────────────────────────────────────────────

void loop()
{
    encoder.poll();

    if (!isPrinting)
    {
        // encoder.getValue() returns an index into validCmcs[].
        // Convert to the actual CMC for display and database lookup.
        static int lastIdx = -1;
        int idx = encoder.getValue();
        if (idx != lastIdx)
        {
            lastIdx = idx;
            int cmc = validCmcs[idx];
            showCmc(cmc);
            Serial.printf("[MBP] CMC selected: %d\n", cmc);
        }

        // Check for a button press to trigger a print.
        if (encoder.wasPressed())
        {
            int selectedCmc = validCmcs[encoder.getValue()];
            Serial.printf("[MBP] Button pressed — printing CMC %d\n", selectedCmc);

            isPrinting = true;
            _animFrame = 0;
            _animLastMs = 0;

            CardRecord card;
            if (!db.getRandomCard((uint8_t)selectedCmc, card))
            {
                // Safety net — should not be reachable because the encoder only
                // navigates CMC values confirmed to have creatures at boot.
                Serial.printf("[MBP] No cards for CMC %d (unexpected)\n", selectedCmc);
                const uint8_t segs[6] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
                display.setSegments(segs, 6, 0);
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
            // "https://scryfall.com/card/" (26) + uuid (36) + '\0' = 63 bytes; buf is 80.
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
            showCmc(validCmcs[encoder.getValue()]);
        }
    }
    else
    {
        // Guard: if somehow isPrinting is stuck, animate and let loop run.
        animatePrinting();
    }
}

