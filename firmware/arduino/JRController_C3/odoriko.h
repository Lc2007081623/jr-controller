#pragma once
#include <stdint.h>

struct OdorikoRates {
    uint16_t accel = 30, coast = 40, brake = 50, minimumCv = 0, ebFlags = 0;
};

constexpr uint16_t ODORIKO_FULL_SCALE_CV = 1200;
constexpr uint16_t EB_MINIMUM_VOLTAGE = 1, EB_RELEASE_WITHOUT_NEUTRAL = 2;

inline bool validOdorikoRates(const OdorikoRates &rates) {
    return rates.accel >= 1 && rates.accel <= 255 &&
           rates.coast >= 1 && rates.coast <= 255 &&
           rates.brake >= 1 && rates.brake <= 255 &&
           rates.minimumCv <= ODORIKO_FULL_SCALE_CV &&
           rates.ebFlags <= (EB_MINIMUM_VOLTAGE | EB_RELEASE_WITHOUT_NEUTRAL);
}

class Odoriko {
public:
    static constexpr uint8_t PREVIOUS = 1, NEXT = 2, CONFIRM = 4, BACK = 8;
    static constexpr int NEUTRAL = 9;

    bool pcOutput() const { return !model && !menu; }
    const char *mode() const { return menu ? "menu" : model ? "odoriko" : "pc"; }
    uint8_t takePcButtons() {
        const uint8_t result = buttons | taps;
        taps = 0;
        return result;
    }
    OdorikoRates rates;
    uint8_t duty() const {
        if (driveDirection == 'N') return 0;
        const int step = speed / 1000;
        const int floor = (rates.minimumCv * 255 + ODORIKO_FULL_SCALE_CV - 1) / ODORIKO_FULL_SCALE_CV;
        if (emergencyBrake) return rates.ebFlags & EB_MINIMUM_VOLTAGE ? floor : 0;
        if (!step) return floor;
        const int first = floor > 1 ? floor : 1;
        return first + ((255 - first) * (step - 1) + 127) / 254;
    }
    char direction() const { return driveDirection; }

    const char *display(int notch, char reverser, uint32_t now = 0) const {
        if (chordHeld && !chordNeutral && notch >= 0 && reverser != 'X')
            return (now / 250) % 2 == 0 ? "N" : "";
        if (menu) {
            if (notch < 0 || reverser == 'X') return "--";
            if (notch != NEUTRAL) return "Hn";
            if (reverser != 'N') return "rn";
            return modelSelected ? "Od" : "PC";
        }
        if (!model) return nullptr;
        if (notch == 0) return "EB";
        if (stopped || notch < 0) return "--";
        if (emergencyBrake && notch != NEUTRAL) return "Hn";
        return nullptr;
    }

    void update(uint32_t now, int notch, char reverser, bool directionUnchanged, uint8_t pressed) {
        const bool valid = notch >= 0 && reverser != 'X';
        const bool neutral = valid && notch == NEUTRAL && reverser == 'N' && directionUnchanged;
        const uint8_t edges = pressed & ~lastButtons;
        lastButtons = pressed;
        buttons = pressed;

        if (menu) {
            if (pressed == 0) menuKeysReady = true;
            if (!menuKeysReady) return;
            if (edges == PREVIOUS || edges == NEXT) modelSelected = !modelSelected;
            if (edges == BACK || (edges == CONFIRM && neutral)) {
                if (edges == CONFIRM) {
                    model = modelSelected;
                    stopped = false;
                }
                menu = false;
                waitRelease = true;
                buttons = 0;
            }
            return;
        }

        if (waitRelease) {
            buttons = 0;
            if (pressed == 0) waitRelease = false;
        } else {
            handleMenuKeys(now, neutral, pressed);
        }
        if (menu || !model) return;

        if (!valid || (buttons & BACK)) {
            stop();
            stopped = true;
            return;
        }
        if (stopped) {
            if (directionUnchanged && edges == CONFIRM && !waitRelease) stopped = false;
            return;
        }
        if (notch == 0) {
            speed = 0;
            emergencyBrake = true;
        } else if (notch == NEUTRAL || (rates.ebFlags & EB_RELEASE_WITHOUT_NEUTRAL)) {
            emergencyBrake = false;
        }
        if (!directionUnchanged || reverser == 'N' || waitRelease) {
            driveDirection = 'N';
            speed = 0;
            return;
        }
        if (driveDirection != reverser) {
            driveDirection = reverser;
            speed = 0;
            rampAt = now;
        }
        if (emergencyBrake) return;
        const uint32_t elapsed = now - rampAt;
        rampAt = now;
        const int dt = elapsed < 100 ? int(elapsed) : 100;
        const int rate = notch > NEUTRAL ? rates.accel * (notch - NEUTRAL)
                       : notch < NEUTRAL ? -rates.brake * (NEUTRAL - notch) : -rates.coast;
        speed += rate * dt;
        if (speed < 0) speed = 0;
        if (speed > 255000) speed = 255000;
    }

private:
    static constexpr uint8_t CHORD = PREVIOUS | BACK;
    bool model = false, menu = false, modelSelected = false, menuKeysReady = false;
    bool waitRelease = false, stopped = false, emergencyBrake = false;
    bool chordHeld = false, chordNeutral = false, chordBlocked = false, singlePending = false;
    uint8_t buttons = 0, lastButtons = 0, singleKey = 0, taps = 0;
    uint32_t chordAt = 0, singleAt = 0, rampAt = 0;
    char driveDirection = 'N';
    int speed = 0;

    void stop() {
        driveDirection = 'N';
        speed = 0;
        emergencyBrake = false;
    }

    void handleMenuKeys(uint32_t now, bool neutral, uint8_t pressed) {
        const uint8_t keys = pressed & CHORD;
        if (keys == 0) {
            if (singlePending && !chordBlocked) {
                if (model) buttons |= singleKey;
                else taps |= singleKey;
            }
            chordBlocked = false;
        }
        if (chordHeld) {
            buttons &= ~CHORD;
            if (pressed != CHORD) {
                chordHeld = false;
                waitRelease = pressed != 0;
            } else if (!neutral) {
                chordNeutral = false;
            } else if (!chordNeutral) {
                chordNeutral = true;
                chordAt = now;
            } else if (uint32_t(now - chordAt) >= 1000) {
                stop();
                menu = true;
                modelSelected = model;
                menuKeysReady = false;
                chordHeld = false;
                taps = 0;
            }
            return;
        }
        if (pressed == CHORD && !chordBlocked) {
            singlePending = false;
            chordHeld = true;
            chordNeutral = neutral;
            chordAt = now;
            buttons = 0;
            return;
        }
        if (keys == 0 || pressed != keys) {
            singlePending = false;
            if (keys) chordBlocked = true;
        } else if (!chordBlocked) {
            if (!singlePending) {
                singleAt = now;
                singlePending = true;
                singleKey = keys;
            }
            if (uint32_t(now - singleAt) < 100) buttons &= ~CHORD;
            else chordBlocked = true;
        }
    }
};
