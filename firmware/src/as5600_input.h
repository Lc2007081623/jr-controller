#pragma once
#include <Arduino.h>
#include <Wire.h>

#if !CONFIG_IDF_TARGET_ESP32S3
#error "SDA7/SCL15 belongs to the current ESP32-S3 board; remap pins before a C3 migration."
#endif

constexpr int AS5600_SDA = 7, AS5600_SCL = 15;
constexpr uint16_t anglePosition(uint16_t raw, uint16_t origin) {
    return (int(raw) - int(origin) + 4096) & 4095;
}
constexpr int angleDelta(uint16_t from, uint16_t to) {
    return ((int(to) - int(from) + 6144) & 4095) - 2048;
}
static_assert(angleDelta(4090, 3) == 9 && angleDelta(3, 4090) == -9, "Circular delta");
static_assert(anglePosition(3, 4090) == 9, "Circular coordinate");

inline bool readAS5600(uint16_t &raw, uint8_t &status) {
    uint8_t bytes[3];
    Wire.beginTransmission(0x36); Wire.write(0x0b);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(uint8_t(0x36), uint8_t(3)) != 3) {
        while (Wire.available()) Wire.read();
        return false;
    }
    for (int i = 0; i < 3; ++i) bytes[i] = Wire.read();
    status = bytes[0];
    if (!(status & 0x20) || (status & 0x18)) return false;
    raw = (uint16_t(bytes[1] & 15) << 8) | bytes[2];
    return true;
}

// Put the coordinate discontinuity in the largest unused gap, outside the calibrated travel.
inline bool normalizeAngles(const uint16_t (&raw)[15], uint16_t (&positions)[15], uint16_t &origin) {
    uint16_t ordered[15];
    for (int i = 0; i < 15; ++i) {
        if (raw[i] > 4095) return false;
        ordered[i] = raw[i];
    }
    for (int i = 1; i < 15; ++i)
        for (int j = i; j > 0 && ordered[j] < ordered[j-1]; --j) {
            uint16_t t = ordered[j]; ordered[j] = ordered[j-1]; ordered[j-1] = t;
        }
    int largest = -1, gapStart = 0;
    for (int i = 0; i < 15; ++i) {
        int next = i == 14 ? ordered[0] + 4096 : ordered[i+1];
        int gap = next - ordered[i];
        if (gap > largest) { largest = gap; gapStart = ordered[i]; }
    }
    origin = (gapStart + largest/2) & 4095;
    for (int i = 0; i < 15; ++i) positions[i] = anglePosition(raw[i], origin);
    int direction = positions[1] > positions[0] ? 1 : -1;
    for (int i = 1; i < 15; ++i)
        if (direction * (int(positions[i]) - positions[i-1]) < 12) return false;
    return true;
}

inline bool angleSelfTest() {
    uint16_t raw[15], out[15], origin;
    for (int i = 0; i < 15; ++i) raw[i] = (3900 + i*90) & 4095;
    if (!normalizeAngles(raw, out, origin)) return false;
    for (int i = 1; i < 15; ++i) if (out[i] - out[i-1] != 90) return false;
    for (int i = 0; i < 15; ++i) raw[i] = (100 - i*90 + 4096) & 4095;
    if (!normalizeAngles(raw, out, origin)) return false;
    for (int i = 1; i < 15; ++i) if (int(out[i-1]) - out[i] != 90) return false;
    raw[6] = raw[5];
    if (normalizeAngles(raw, out, origin)) return false;
    raw[6] = (100 - 6*90 + 4096) & 4095;
    uint16_t t = raw[5]; raw[5] = raw[6]; raw[6] = t;
    if (normalizeAngles(raw, out, origin)) return false;
    raw[0] = 5000;
    return !normalizeAngles(raw, out, origin);
}
