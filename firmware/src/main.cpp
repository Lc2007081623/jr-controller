#include <Arduino.h>
#include "matrix_display.h"
#include <Preferences.h>
#include <esp_system.h>
#ifdef JR_USE_AS5600
#include "as5600_input.h"
#endif

// 2026-10-21: validated matrix pins 6/5/4; potentiometer wiper GPIO3.
constexpr int ADC_PIN = 3;
constexpr int FORWARD_PIN = 10;
bool forwardRaw = false, forwardPressed = false;
uint32_t forwardChangedAt = 0, forwardCount = 0;
// Real EB/B8 centers are 16 ADC counts apart; keep a 12-count floor.
constexpr int COUNT = 15, MIN_GAP = 12;
const char *const names[COUNT] = {
    "EB", "B8", "B7", "B6", "B5", "B4", "B3", "B2", "B1", "N",
    "P1", "P2", "P3", "P4", "P5"
};
struct Calibration {
    uint32_t magic;
#ifdef JR_USE_AS5600
    uint16_t origin;
#endif
    uint16_t centers[COUNT];
};
#ifdef JR_USE_AS5600
constexpr uint32_t MAGIC = 0x4a520201;
const char *const CAL_NAMESPACE = "jr-as56", *const SOURCE = "AS5600";
#else
constexpr uint32_t MAGIC = 0x4a520101;
const char *const CAL_NAMESPACE = "jr-m3", *const SOURCE = "ADC";
#endif
Calibration saved{}, pending{};
uint16_t captured = 0, rawAdc = 0, filtered = 0;
bool calibrated = false, collecting = false, filterReady = false;
bool positionValid = true, sensorFaultPending = false;
uint8_t sensorStatus = 0;
int notch = -1;
uint32_t bootId, sequence = 0, sampleAt = 0, reportAt = 0, displayAt = 0;
char command[64]; size_t commandLen = 0;
bool discardLine = false;
Preferences prefs;

bool validCalibration(const Calibration &c) {
    if (c.magic != MAGIC) return false;
    int direction = c.centers[1] > c.centers[0] ? 1 : -1;
    for (int i = 0; i < COUNT; ++i) if (c.centers[i] > 4095) return false;
    for (int i = 1; i < COUNT; ++i)
        if (direction * (int(c.centers[i]) - int(c.centers[i-1])) < MIN_GAP) return false;
#ifdef JR_USE_AS5600
    return c.origin <= 4095;
#else
    return abs(int(c.centers[COUNT-1]) - int(c.centers[0])) >= 500;
#endif
}

void ack(const char *message) {
    Serial.printf("{\"v\":1,\"type\":\"ack\",\"message\":\"%s\"}\n", message);
}

void scanDisplay() {
#ifdef JR_USE_AS5600
    Serial.println("{\"v\":1,\"type\":\"display\",\"driver\":\"MAX7219\",\"din\":6,\"cs\":5,\"clk\":4,\"sensor\":\"AS5600\",\"sda\":7,\"scl\":15,\"readback\":false}");
#else
    // MAX7219 has no readback; this reports configuration, not detected hardware.
    Serial.println("{\"v\":1,\"type\":\"display\",\"driver\":\"MAX7219\",\"din\":6,\"cs\":5,\"clk\":4,\"adc_pin\":3,\"readback\":false}");
#endif
}

void runCommand(char *s) {
    if (!strcmp(s, "BEGIN")) {
        collecting = true; captured = 0; pending = {}; pending.magic = MAGIC; notch = -1;
        ack("calibration_started");
    } else if (!strncmp(s, "CAP ", 4)) {
        if (!collecting || !filterReady) { ack("error_begin_first"); return; }
        int index = -1;
        for (int i = 0; i < COUNT; ++i) if (!strcmp(s+4, names[i])) index = i;
        if (index < 0) { ack("error_notch_name"); return; }
#ifdef JR_USE_AS5600
        uint16_t first, next;
        if (!readAS5600(first, sensorStatus)) { sensorFaultPending = true; ack("error_sensor_invalid"); return; }
        int32_t sum = 0;
        for (int i = 0; i < 16; ++i) {
            if (!readAS5600(next, sensorStatus)) { sensorFaultPending = true; ack("error_sensor_invalid"); return; }
            sum += angleDelta(first, next);
        }
        pending.centers[index] = (int(first) + int(lroundf(sum/16.0f)) + 4096) & 4095;
#else
        // Operator holds the detent still; average samples without changing GPIO direction.
        uint32_t sum = 0;
        for (int i = 0; i < 32; ++i) sum += analogRead(ADC_PIN);
        pending.centers[index] = (sum + 16) / 32;
#endif
        captured |= uint16_t(1U << index);
        Serial.printf("{\"v\":1,\"type\":\"capture\",\"notch\":\"%s\",\"adc\":%u,\"mask\":%u}\n",
                      names[index], pending.centers[index], captured);
    } else if (!strncmp(s, "SET ", 4)) {
#ifdef JR_USE_AS5600
        ack("error_as5600_use_physical_capture"); return;
#else
        // Restore a measured backup after flashing; SAVE still validates all 15 points.
        if (!collecting) { ack("error_begin_first"); return; }
        char name[8], extra; unsigned int value;
        if (sscanf(s+4, "%7s %u %c", name, &value, &extra) != 2 || value > 4095) {
            ack("error_restore_value"); return;
        }
        int index = -1;
        for (int i = 0; i < COUNT; ++i) if (!strcmp(name, names[i])) index = i;
        if (index < 0) { ack("error_notch_name"); return; }
        pending.centers[index] = value; captured |= uint16_t(1U << index);
        ack("center_restored");
#endif
    } else if (!strcmp(s, "SAVE")) {
        if (!collecting || captured != 0x7fff) { ack("error_capture_all_15"); return; }
        Calibration candidate = pending;
#ifdef JR_USE_AS5600
        if (!normalizeAngles(pending.centers, candidate.centers, candidate.origin)) {
            ack("error_angles_need_ordered_15_positions_spacing12"); return;
        }
#endif
        if (!validCalibration(candidate)) { ack("error_centers_need_monotonic_spacing12_span500"); return; }
        if (!prefs.begin(CAL_NAMESPACE, false)) { ack("error_nvs_open"); return; }
        size_t written = prefs.putBytes("cal", &candidate, sizeof(candidate)); prefs.end();
        if (written != sizeof(pending)) { ack("error_nvs_write"); return; }
        saved = candidate; calibrated = true; collecting = false; notch = -1;
        ack("calibration_saved");
    } else if (!strcmp(s, "CANCEL")) {
        collecting = false; notch = -1; ack("calibration_cancelled");
    } else if (!strcmp(s, "DUMP")) {
        const Calibration &c = collecting ? pending : saved;
        for (int i = 0; i < COUNT; ++i)
            Serial.printf("{\"v\":1,\"type\":\"center\",\"notch\":\"%s\",\"adc\":%u}\n",names[i],c.centers[i]);
    } else if (!strcmp(s, "SCAN")) {
        scanDisplay();
    } else ack("error_unknown_command");
}

void sample() {
#ifdef JR_USE_AS5600
    positionValid = readAS5600(rawAdc, sensorStatus);
    if (!positionValid) {
        sensorFaultPending = true; filterReady = false; notch = -1; return;
    }
    static float ema = 0;
    if (!filterReady) { ema = rawAdc; filterReady = true; }
    ema += 0.25f * angleDelta(uint16_t(ema + 0.5f) & 4095, rawAdc);
    if (ema < 0) ema += 4096;
    if (ema >= 4096) ema -= 4096;
    uint16_t circular = uint16_t(ema + 0.5f) & 4095;
    filtered = calibrated && !collecting ? anglePosition(circular, saved.origin) : circular;
#else
    uint32_t sum = 0;
    for (int i = 0; i < 8; ++i) sum += analogRead(ADC_PIN);
    rawAdc = (sum+4)/8;
    static float ema = 0;
    if (!filterReady) { ema = rawAdc; filterReady = true; }
    ema += 0.25f * (float(rawAdc) - ema);
    filtered = uint16_t(ema + 0.5f);
#endif
    if (!calibrated || collecting) { notch = -1; return; }
    // Boundaries from adjacent measured centers, with 10% gap hysteresis.
    const int direction = saved.centers[1] > saved.centers[0] ? 1 : -1;
    const int value = direction * int(filtered);
    if (notch < 0) {
        notch = 0;
        for (int i = 1; i < COUNT; ++i)
            if (value > direction * (int(saved.centers[i])+saved.centers[i-1])/2) notch = i;
    }
    while (notch < COUNT-1) {
        int a = direction*int(saved.centers[notch]), b = direction*int(saved.centers[notch+1]);
        if (value <= (a+b)/2 + max(3,(b-a)/10)) break;
        ++notch;
    }
    while (notch > 0) {
        int a = direction*int(saved.centers[notch-1]), b = direction*int(saved.centers[notch]);
        if (value >= (a+b)/2 - max(3,(b-a)/10)) break;
        --notch;
    }
}

void setup() {
#ifndef JR_USE_AS5600
    pinMode(ADC_PIN, INPUT);
#endif
    pinMode(FORWARD_PIN, INPUT_PULLUP);
    forwardRaw = forwardPressed = digitalRead(FORWARD_PIN) == LOW;
    matrixBegin();
    Serial.begin(115200); bootId = esp_random();
#ifdef JR_USE_AS5600
    if (!angleSelfTest()) { ack("error_angle_selftest"); while (true) delay(1000); }
    ack("angle_selftest_passed");
    Wire.begin(AS5600_SDA, AS5600_SCL, 100000); Wire.setTimeOut(10);
    positionValid = false;
#else
    analogReadResolution(12); analogSetPinAttenuation(ADC_PIN, ADC_11db);
#endif
    scanDisplay();
    if (prefs.begin(CAL_NAMESPACE, true)) {
        if (prefs.getBytesLength("cal") == sizeof(saved)) prefs.getBytes("cal", &saved, sizeof(saved));
        prefs.end();
    }
    calibrated = validCalibration(saved);
#ifdef JR_USE_AS5600
    ack("jr_as5600_ready_sda7_scl15_din6_cs5_clk4");
#else
    ack("jr_matrix_ready_adc3_din6_cs5_clk4");
#endif
}

void loop() {
    // Bounded command parser: no blocking readString()/readBytesUntil().
    for (int n = 0; n < 96 && Serial.available(); ++n) {
        char c = char(Serial.read());
        if (c == '\r') continue;
        if (c == '\n') {
            if (!discardLine && commandLen) { command[commandLen] = 0; runCommand(command); }
            commandLen = 0; discardLine = false;
        } else if (!discardLine) {
            if (commandLen < sizeof(command)-1) command[commandLen++] = c;
            else { commandLen = 0; discardLine = true; }
        }
    }
    uint32_t now = millis();
    bool pressed = digitalRead(FORWARD_PIN) == LOW;
    if (pressed != forwardRaw) { forwardRaw = pressed; forwardChangedAt = now; }
    if (forwardRaw != forwardPressed && uint32_t(now-forwardChangedAt) >= 30) {
        forwardPressed = forwardRaw;
        if (forwardPressed) ++forwardCount;
    }
    if (uint32_t(now-sampleAt) >= 5) { sampleAt = now; sample(); }
    if (uint32_t(now-reportAt) >= 20) {
        reportAt = now;
        const bool healthy = positionValid && !sensorFaultPending;
        const bool ready = calibrated && !collecting && notch >= 0 && healthy;
        Serial.printf("{\"v\":1,\"type\":\"state\",\"boot\":%lu,\"seq\":%lu,\"ms\":%lu,\"raw\":%u,\"adc\":%u,\"calibrated\":%s,\"notch\":\"%s\",\"forward_pressed\":%s,\"forward_count\":%lu,\"sensor\":\"%s\",\"sensor_ok\":%s}\n",
            (unsigned long)bootId, (unsigned long)sequence++, (unsigned long)now,
            rawAdc, filtered, ready ? "true":"false", ready ? names[notch]:"--",
            forwardPressed ? "true":"false", (unsigned long)forwardCount, SOURCE, healthy ? "true":"false");
        sensorFaultPending = false;
    }
    if (uint32_t(now-displayAt) >= 100) {
        displayAt = now;
        matrixShow(!positionValid ? "--" : (collecting ? "C" : (notch >= 0 ? names[notch] : "--")));
    }
}
