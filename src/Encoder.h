#pragma once
#include <Arduino.h>

/**
 * RotaryEncoder
 *
 * Reads a KY-040 incremental rotary encoder using a 4-state Gray-code state
 * table for clean, debounce-free step detection.  The integrated push-button
 * is software-debounced with a configurable hold-off window.
 *
 * The value wraps: turning CW past maxVal jumps to minVal, and turning CCW
 * past minVal jumps to maxVal.
 *
 * Pins (all INPUT_PULLUP):
 *   clkPin  – CLK / A phase
 *   dtPin   – DT  / B phase
 *   swPin   – SW  push-button (active LOW)
 *
 * Usage:
 *   Call poll() from loop() as often as possible.
 *   Read getValue() for the current wrapping integer value.
 *   Check wasPressed() once per loop() iteration to consume a button event.
 */
class RotaryEncoder
{
public:
    /**
     * @param clkPin      GPIO for CLK phase
     * @param dtPin       GPIO for DT  phase
     * @param swPin       GPIO for push-button (active LOW with INPUT_PULLUP)
     * @param minVal      Minimum value before wrapping (default 0)
     * @param maxVal      Maximum value before wrapping (default 16)
     * @param debouncems  Button debounce window in milliseconds (default 50)
     */
    RotaryEncoder(uint8_t clkPin, uint8_t dtPin, uint8_t swPin,
                  int minVal = 0, int maxVal = 16, uint32_t debouncems = 50)
        : _clkPin(clkPin), _dtPin(dtPin), _swPin(swPin),
          _minVal(minVal), _maxVal(maxVal), _debounceMs(debouncems),
          _value(minVal), _lastEncoderState(0), _subSteps(0),
          _btnPressed(false),
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

    /** Current wrapping value in [minVal, maxVal]. */
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

    /**
     * Update the navigable range and reset the current value to minVal.
     * Call after the card database has loaded so the range reflects only
     * CMC values that have at least one creature.
     *
     * @param minVal  New minimum (inclusive)
     * @param maxVal  New maximum (inclusive)
     */
    void setRange(int minVal, int maxVal)
    {
        _minVal   = minVal;
        _maxVal   = maxVal;
        _value    = minVal;
        _subSteps = 0;
        // Re-capture encoder state to avoid a phantom step on the next poll.
        _lastEncoderState = _readAB();
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
            // Accumulate sub-steps.  The KY-040 produces 4 Gray-code
            // transitions per mechanical detent, so we count them and only
            // advance the value once we have collected a full step (±4).
            _subSteps += dir;
            if (_subSteps >= 4)
            {
                _subSteps -= 4;
                int next = _value + 1;
                if (next > _maxVal) next = _minVal;
                _value = next;
            }
            else if (_subSteps <= -4)
            {
                _subSteps += 4;
                int next = _value - 1;
                if (next < _minVal) next = _maxVal;
                _value = next;
            }
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
    int _minVal;                  // mutable — updated by setRange()
    int _maxVal;                  // mutable — updated by setRange()
    const uint32_t _debounceMs;

    int _value;
    uint8_t _lastEncoderState;
    int8_t  _subSteps;           // accumulated Gray-code quarter-steps (±4 = one detent)
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
