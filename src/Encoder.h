#pragma once
#include <Arduino.h>

/**
 * RotaryEncoder
 *
 * Reads an EC11 incremental rotary encoder using a 4-state Gray-code state
 * table for clean, debounce-free step detection.  The integrated push-button
 * is software-debounced with a configurable hold-off window.
 *
 * Pins (all INPUT_PULLUP):
 *   clkPin  – CLK / A phase
 *   dtPin   – DT  / B phase
 *   swPin   – SW  push-button (active LOW)
 *
 * Usage:
 *   Call poll() from loop() as often as possible.
 *   Read getValue() for the current clamped integer value.
 *   Check wasPressed() once per loop() iteration to consume a button event.
 */
class RotaryEncoder
{
public:
    /**
     * @param clkPin      GPIO for CLK phase
     * @param dtPin       GPIO for DT  phase
     * @param swPin       GPIO for push-button (active LOW with INPUT_PULLUP)
     * @param minVal      Minimum clamped value (default 0)
     * @param maxVal      Maximum clamped value (default 16)
     * @param debouncems  Button debounce window in milliseconds (default 50)
     */
    RotaryEncoder(uint8_t clkPin, uint8_t dtPin, uint8_t swPin,
                  int minVal = 0, int maxVal = 16, uint32_t debouncems = 50)
        : _clkPin(clkPin), _dtPin(dtPin), _swPin(swPin),
          _minVal(minVal), _maxVal(maxVal), _debounceMs(debouncems),
          _value(0), _lastEncoderState(0), _btnPressed(false),
          _lastBtnRaw(HIGH), _lastDebounceTime(0)
    {
    }

    void begin()
    {
        pinMode(_clkPin, INPUT_PULLUP);
        pinMode(_dtPin, INPUT_PULLUP);
        pinMode(_swPin, INPUT_PULLUP);

        // Capture initial encoder state so the first poll is clean.
        _lastEncoderState = _readAB();
    }

    /**
     * Poll encoder and button — call from loop() with no delay.
     */
    void poll()
    {
        _pollEncoder();
        _pollButton();
    }

    /** Current clamped CMC value. */
    int getValue() const { return _value; }

    /**
     * Consume a button press event.  Returns true once per physical click,
     * then resets the flag.  Call at most once per loop() iteration.
     */
    bool wasPressed()
    {
        if (_btnPressed)
        {
            _btnPressed = false;
            return true;
        }
        return false;
    }

private:
    // ── Encoder state-table (2-bit Gray code) ─────────────────────────────
    // Each entry encodes the direction (+1 / -1 / 0) for a given
    // (prevAB << 2 | currAB) 4-bit transition.
    static const int8_t _table[16];

    uint8_t _readAB() const
    {
        return (digitalRead(_clkPin) << 1) | digitalRead(_dtPin);
    }

    void _pollEncoder()
    {
        uint8_t currAB = _readAB();
        if (currAB == _lastEncoderState)
            return;

        uint8_t idx = (_lastEncoderState << 2) | currAB;
        int8_t dir = _table[idx & 0x0F];
        _lastEncoderState = currAB;

        if (dir != 0)
        {
            _value = constrain(_value + dir, _minVal, _maxVal);
        }
    }

    // ── Button debouncing ─────────────────────────────────────────────────
    void _pollButton()
    {
        int raw = digitalRead(_swPin);

        if (raw != _lastBtnRaw)
        {
            _lastDebounceTime = millis();
        }
        _lastBtnRaw = raw;

        if ((millis() - _lastDebounceTime) >= _debounceMs)
        {
            // Stable LOW means button pressed (active-low with pull-up).
            if (raw == LOW && _stableBtnState != LOW)
            {
                _stableBtnState = LOW;
                _btnPressed = true; // Rising edge of stable press.
            }
            else if (raw == HIGH)
            {
                _stableBtnState = HIGH;
            }
        }
    }

    // ── Members ───────────────────────────────────────────────────────────
    const uint8_t _clkPin;
    const uint8_t _dtPin;
    const uint8_t _swPin;
    const int _minVal;
    const int _maxVal;
    const uint32_t _debounceMs;

    int _value;
    uint8_t _lastEncoderState;
    volatile bool _btnPressed;

    int _lastBtnRaw;
    int _stableBtnState = HIGH;
    uint32_t _lastDebounceTime;
};

// Gray-code transition table: index = (prev << 2) | curr
// +1 = CW, -1 = CCW, 0 = invalid / no movement
const int8_t RotaryEncoder::_table[16] = {
    //  00   01   10   11   (current AB)
    0, -1, +1, 0, // prev = 00
    +1, 0, 0, -1, // prev = 01
    -1, 0, 0, +1, // prev = 10
    0, +1, -1, 0  // prev = 11
};
