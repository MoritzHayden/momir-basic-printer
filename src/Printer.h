#pragma once
#include <Arduino.h>

/**
 * ThermalPrinter
 *
 * Drives a 58mm TTL thermal receipt printer (e.g. Maikrt MC206H or compatible)
 * over HardwareSerial using raw ESC/POS byte sequences.
 *
 * Serial wiring:
 *   ESP32-S3 TX (GPIO 17) → Printer RX
 *   ESP32-S3 RX (GPIO 18) → Printer TX
 *
 * Paper width: 58mm / 384 dots → 32 characters at normal font (12-dot wide).
 *
 * Layout (top → bottom):
 *   ┌────────────────────────────────┐
 *   │  CARD NAME          {MANA}    │  bold, single line or split if too long
 *   │  ────────────────────────────  │  divider
 *   │         [QR CODE]             │  centered, links to Scryfall page
 *   │  ────────────────────────────  │  divider
 *   │  Type Line                     │  normal
 *   │  ────────────────────────────  │  divider
 *   │  Oracle text (word-wrapped)    │  normal, wrapped at 32 chars/line
 *   │  ────────────────────────────  │  divider (only if PT present)
 *   │                     P / T     │  bold, right-aligned (creatures only)
 *   │  [3 blank lines for tear bar] │
 *   └────────────────────────────────┘
 */
class ThermalPrinter
{
public:
    static constexpr uint8_t CHARS_PER_LINE = 32;
    static constexpr uint8_t MIN_TITLE_SPACING = 1;

    /**
     * @param serial   HardwareSerial to use (e.g. Serial1)
     * @param rxPin    ESP32 TX → Printer RX GPIO (default 17)
     * @param txPin    ESP32 RX ← Printer TX GPIO (default 18)
     * @param baud     Baud rate (9600 or 19200, default 9600)
     */
    void begin(HardwareSerial &serial, int rxPin = 17, int txPin = 18,
               uint32_t baud = 9600)
    {
        _serial = &serial;
        _serial->begin(baud, SERIAL_8N1, txPin, rxPin);
        delay(100);
        _init();
    }

    /**
     * Print a full card receipt.
     *
     * @param name        Card name (null-terminated, ASCII)
     * @param mana        Mana cost string (e.g. "{2}{W}{U}")
     * @param typeLine    Type line (e.g. "Legendary Creature — Human Wizard")
     * @param oracle      Oracle rules text (may contain '\n' paragraph breaks)
     * @param pt          Power/Toughness string (e.g. "2/3"), empty if N/A
     * @param scryfallUrl Scryfall URL to encode as a centered QR code.
     *                    Pass nullptr or "" to skip the QR code.
     */
    void printCard(const char *name, const char *mana,
                   const char *typeLine, const char *oracle,
                   const char *pt, const char *scryfallUrl = nullptr)
    {
        // ── NAME + MANA COST ──────────────────────────────────────────────
        // Normal weight — matches physical print (no bold on name line).
        size_t nameLen = strlen(name);
        size_t manaLen = strlen(mana);
        size_t combined = nameLen + MIN_TITLE_SPACING + manaLen;

        if (combined <= CHARS_PER_LINE)
        {
            // Fits on one line: pad between name and mana cost.
            size_t spaces = CHARS_PER_LINE - nameLen - manaLen;
            _serial->print(name);
            for (size_t i = 0; i < spaces; i++)
                _serial->print(' ');
            _serial->println(mana);
        }
        else
        {
            // Too long: print name wrapped, then mana right-aligned.
            _printWrapped(name, CHARS_PER_LINE);
            if (manaLen > 0)
            {
                size_t pad = (manaLen < CHARS_PER_LINE)
                                 ? (CHARS_PER_LINE - manaLen)
                                 : 0;
                for (size_t i = 0; i < pad; i++)
                    _serial->print(' ');
                _serial->println(mana);
            }
        }

        // ── QR CODE (centered, Scryfall link) ─────────────────────────────
        // No divider between name and QR — matches physical print.
        if (scryfallUrl != nullptr && strlen(scryfallUrl) > 0)
        {
            _setAlignment(1); // center
            _printNativeQr(scryfallUrl, /*moduleSize=*/4);
            _setAlignment(0); // left
        }

        // ── TYPE LINE (centered) ──────────────────────────────────────────
        if (strlen(typeLine) > 0)
        {
            _setAlignment(1); // center — matches physical print

            // Normalize em-dash to " - " before printing.
            char typeNorm[128];
            _normalizeText(typeLine, typeNorm, sizeof(typeNorm));

            if (strlen(typeNorm) > CHARS_PER_LINE)
            {
                // Split at " - " if too long to fit on one line.
                const char *dash = strstr(typeNorm, " - ");
                if (dash != nullptr)
                {
                    size_t prefixLen = dash - typeNorm;
                    char prefixBuf[65];
                    size_t toCopy = (prefixLen < sizeof(prefixBuf) - 1)
                                        ? prefixLen
                                        : sizeof(prefixBuf) - 1;
                    memcpy(prefixBuf, typeNorm, toCopy);
                    prefixBuf[toCopy] = '\0';
                    _serial->println(prefixBuf);
                    _printWrapped(dash + 3, CHARS_PER_LINE);
                }
                else
                {
                    _printWrapped(typeNorm, CHARS_PER_LINE);
                }
            }
            else
            {
                _serial->println(typeNorm);
            }
            _setAlignment(0);   // left
            _serial->println(); // blank line after type
        }

        // ── ORACLE TEXT (left-aligned) ────────────────────────────────────
        if (strlen(oracle) > 0)
        {
            char buf[1024];
            _normalizeText(oracle, buf, sizeof(buf));

            char *ctx = nullptr;
            char *para = strtok_r(buf, "\n", &ctx);
            while (para != nullptr)
            {
                if (strlen(para) > 0)
                {
                    _printWrapped(para, CHARS_PER_LINE);
                    _serial->println(); // blank line between paragraphs
                }
                para = strtok_r(nullptr, "\n", &ctx);
            }
        }

        // ── POWER / TOUGHNESS ─────────────────────────────────────────────
        // Right-aligned, normal weight, no divider above — matches physical print.
        // Stored as "P/T"; format as "P / T" with spaces around slash.
        if (strlen(pt) > 0)
        {
            char ptFmt[24];
            const char *slash = strchr(pt, '/');
            if (slash != nullptr)
            {
                size_t pLen = slash - pt;
                snprintf(ptFmt, sizeof(ptFmt), "%.*s / %s",
                         (int)pLen, pt, slash + 1);
            }
            else
            {
                strncpy(ptFmt, pt, sizeof(ptFmt) - 1);
                ptFmt[sizeof(ptFmt) - 1] = '\0';
            }

            size_t ptLen = strlen(ptFmt);
            size_t pad = (ptLen < CHARS_PER_LINE) ? (CHARS_PER_LINE - ptLen) : 0;
            for (size_t i = 0; i < pad; i++)
                _serial->print(' ');
            _serial->println(ptFmt);
        }

        // ── PAPER FEED (3 blank lines for tear bar clearance) ─────────────
        _feedLines(3);
    }

private:
    HardwareSerial *_serial = nullptr;

    // ── ESC/POS helpers ───────────────────────────────────────────────────

    /** Send printer initialisation sequence. */
    void _init()
    {
        // ESC @ — Initialize printer
        _serial->write(0x1B);
        _serial->write('@');
        delay(50);
    }

    /** ESC E n — bold on (n=1) / off (n=0). */
    void _setBold(bool on)
    {
        _serial->write(0x1B);
        _serial->write('E');
        _serial->write(on ? 1 : 0);
    }

    /** ESC a n — text alignment: 0=left, 1=center, 2=right. */
    void _setAlignment(uint8_t align)
    {
        _serial->write(0x1B);
        _serial->write('a');
        _serial->write(align);
    }

    /**
     * Print a QR code using native ESC/POS GS ( k commands (Function 165–181).
     * Supported by virtually all modern 58mm thermal printers.
     *
     * @param url        Null-terminated URL string to encode
     * @param moduleSize Dot size of each QR module (1–16). 4 = ~20mm on 58mm paper.
     */
    void _printNativeQr(const char *url, uint8_t moduleSize = 4)
    {
        size_t dataLen = strlen(url);
        if (dataLen == 0)
            return;

        // ── 1. Select Model 2 (most compatible) ──────────────────────────
        // GS ( k 4 0 49 65 50 0
        _serial->write(0x1D);
        _serial->write('(');
        _serial->write('k');
        _serial->write((uint8_t)4);
        _serial->write((uint8_t)0); // pL, pH
        _serial->write((uint8_t)49);
        _serial->write((uint8_t)65); // cn=49, fn=65
        _serial->write((uint8_t)50);
        _serial->write((uint8_t)0); // Model 2, reserved

        // ── 2. Set module (dot) size ──────────────────────────────────────
        // GS ( k 3 0 49 67 n
        _serial->write(0x1D);
        _serial->write('(');
        _serial->write('k');
        _serial->write((uint8_t)3);
        _serial->write((uint8_t)0);
        _serial->write((uint8_t)49);
        _serial->write((uint8_t)67);
        _serial->write(moduleSize);

        // ── 3. Set error correction level M (recovers ~15%) ───────────────
        // GS ( k 3 0 49 69 49
        // Levels: 48=L, 49=M, 50=Q, 51=H
        _serial->write(0x1D);
        _serial->write('(');
        _serial->write('k');
        _serial->write((uint8_t)3);
        _serial->write((uint8_t)0);
        _serial->write((uint8_t)49);
        _serial->write((uint8_t)69);
        _serial->write((uint8_t)49); // M

        // ── 4. Store QR data in the print buffer ──────────────────────────
        // GS ( k pL pH 49 80 48 <data>
        // pL + pH*256 = dataLen + 3  (3 bytes for cn, fn, m)
        uint16_t storeLen = (uint16_t)(dataLen + 3);
        uint8_t pL = storeLen & 0xFF;
        uint8_t pH = (storeLen >> 8) & 0xFF;
        _serial->write(0x1D);
        _serial->write('(');
        _serial->write('k');
        _serial->write(pL);
        _serial->write(pH);
        _serial->write((uint8_t)49);
        _serial->write((uint8_t)80);
        _serial->write((uint8_t)48);
        _serial->print(url);

        // ── 5. Print the buffered QR code ─────────────────────────────────
        // GS ( k 3 0 49 81 48
        _serial->write(0x1D);
        _serial->write('(');
        _serial->write('k');
        _serial->write((uint8_t)3);
        _serial->write((uint8_t)0);
        _serial->write((uint8_t)49);
        _serial->write((uint8_t)81);
        _serial->write((uint8_t)48);

        _serial->println(); // ensure line feed after QR bitmap
    }

    /** Print a 32-character dashed divider line. */
    void _printDivider()
    {
        for (uint8_t i = 0; i < CHARS_PER_LINE; i++)
            _serial->print('-');
        _serial->println();
    }

    /** ESC d n — feed n lines. */
    void _feedLines(uint8_t n)
    {
        _serial->write(0x1B);
        _serial->write('d');
        _serial->write(n);
    }

    /**
     * Word-wrap a null-terminated string at maxWidth characters per line and
     * print each line followed by '\n'.  Breaks on spaces; forces a hard break
     * if a single word is longer than maxWidth.
     */
    void _printWrapped(const char *text, uint8_t maxWidth)
    {
        size_t len = strlen(text);
        size_t start = 0;

        while (start < len)
        {
            // Skip leading spaces at the start of each wrapped segment.
            while (start < len && text[start] == ' ')
                start++;
            if (start >= len)
                break;

            // Find the furthest break point within [start, start+maxWidth).
            size_t remaining = len - start;
            if (remaining <= maxWidth)
            {
                // Rest fits on one line.
                _serial->write((const uint8_t *)(text + start), remaining);
                _serial->println();
                break;
            }

            // Search backwards from start+maxWidth for a space to break on.
            size_t breakAt = start + maxWidth;
            while (breakAt > start && text[breakAt] != ' ')
                breakAt--;

            if (breakAt == start)
            {
                // No space found — force a hard break at maxWidth.
                breakAt = start + maxWidth;
            }

            size_t lineLen = breakAt - start;
            _serial->write((const uint8_t *)(text + start), lineLen);
            _serial->println();
            start = breakAt;
        }
    }

    /**
     * Replace common Unicode characters with ASCII equivalents suitable for
     * a standard CP437 thermal printer codepage.
     *
     * Operates on raw UTF-8 input; replacements are byte-for-byte substitutions
     * written into dst.  Characters in curly braces like {W}, {2} are kept
     * as-is (they represent mana symbols in oracle text).
     */
    void _normalizeText(const char *src, char *dst, size_t dstSize)
    {
        size_t di = 0;
        size_t si = 0;
        size_t srcLen = strlen(src);

        while (si < srcLen && di < dstSize - 1)
        {
            unsigned char c = (unsigned char)src[si];

            // ── 3-byte UTF-8 sequences ────────────────────────────────────
            if (c == 0xE2 && si + 2 < srcLen)
            {
                unsigned char b1 = (unsigned char)src[si + 1];
                unsigned char b2 = (unsigned char)src[si + 2];

                // U+2014 EM DASH (E2 80 94) → '-'
                if (b1 == 0x80 && b2 == 0x94)
                {
                    dst[di++] = '-';
                    si += 3;
                    continue;
                }
                // U+2013 EN DASH (E2 80 93) → '-'
                if (b1 == 0x80 && b2 == 0x93)
                {
                    dst[di++] = '-';
                    si += 3;
                    continue;
                }
                // U+2019 RIGHT SINGLE QUOTATION MARK (E2 80 99) → '\''
                if (b1 == 0x80 && b2 == 0x99)
                {
                    dst[di++] = '\'';
                    si += 3;
                    continue;
                }
                // U+201C LEFT DOUBLE QUOTATION MARK (E2 80 9C) → '"'
                if (b1 == 0x80 && b2 == 0x9C)
                {
                    dst[di++] = '"';
                    si += 3;
                    continue;
                }
                // U+201D RIGHT DOUBLE QUOTATION MARK (E2 80 9D) → '"'
                if (b1 == 0x80 && b2 == 0x9D)
                {
                    dst[di++] = '"';
                    si += 3;
                    continue;
                }
                // U+2022 BULLET (E2 80 A2) → '*'
                if (b1 == 0x80 && b2 == 0xA2)
                {
                    dst[di++] = '*';
                    si += 3;
                    continue;
                }
                // U+2212 MINUS SIGN (E2 88 92) → '-'
                if (b1 == 0x88 && b2 == 0x92)
                {
                    dst[di++] = '-';
                    si += 3;
                    continue;
                }

                // Unknown 3-byte sequence: skip.
                si += 3;
                continue;
            }

            // ── 2-byte UTF-8 sequences ────────────────────────────────────
            if (c >= 0xC0 && c <= 0xDF && si + 1 < srcLen)
            {
                // Skip unhandled 2-byte sequences.
                si += 2;
                continue;
            }

            // ── 4-byte UTF-8 sequences ────────────────────────────────────
            if (c >= 0xF0 && si + 3 < srcLen)
            {
                si += 4;
                continue;
            }

            // ── Printable ASCII / CR / LF ─────────────────────────────────
            if (c == '\n' || (c >= 0x20 && c < 0x80))
            {
                dst[di++] = (char)c;
            }
            // Silently drop other control characters / high bytes.
            si++;
        }
        dst[di] = '\0';
    }
};
