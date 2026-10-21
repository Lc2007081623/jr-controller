#include <Arduino.h>
#include "matrix_display.h"
#include <Preferences.h>
#include <esp_system.h>

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
struct Calibration { uint32_t magic; uint16_t centers[COUNT]; };
constexpr uint32_t MAGIC = 0x4a520101;
Calibration saved{}, pending{};
uint16_t captured = 0, rawAdc = 0, filtered = 0;
bool calibrated = false, collecting = false, filterReady = false;
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
    return abs(int(c.centers[COUNT-1]) - int(c.centers[0])) >= 500;
}

void ack(const char *message) {
    Serial.printf("{\"v\":1,\"type\":\"ack\",\"message\":\"%s\"}\n", message);
}

void scanDisplay() {
    // MAX7219 has no readback; this reports configuration, not detected hardware.
    Serial.println("{\"v\":1,\"type\":\"display\",\"driver\":\"MAX7219\",\"din\":6,\"cs\":5,\"clk\":4,\"adc_pin\":3,\"readback\":false}");
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
        // Operator holds the detent still; average samples without changing GPIO direction.
        uint32_t sum = 0;
        for (int i = 0; i < 32; ++i) sum += analogRead(ADC_PIN);
        pending.centers[index] = (sum + 16) / 32;
        captured |= uint16_t(1U << index);
        Serial.printf("{\"v\":1,\"type\":\"capture\",\"notch\":\"%s\",\"adc\":%u,\"mask\":%u}\n",
                      names[index], pending.centers[index], captured);
    } else if (!strncmp(s, "SET ", 4)) {
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
    } else if (!strcmp(s, "SAVE")) {
        if (!collecting || captured != 0x7fff) { ack("error_capture_all_15"); return; }
        if (!validCalibration(pending)) { ack("error_centers_need_monotonic_spacing12_span500"); return; }
        if (!prefs.begin("jr-m3", false)) { ack("error_nvs_open"); return; }
        size_t written = prefs.putBytes("cal", &pending, sizeof(pending)); prefs.end();
        if (written != sizeof(pending)) { ack("error_nvs_write"); return; }
        saved = pending; calibrated = true; collecting = false; notch = -1;
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
    uint32_t sum = 0;
    for (int i = 0; i < 8; ++i) sum += analogRead(ADC_PIN);
    rawAdc = (sum+4)/8;
    static float ema = 0;
    if (!filterReady) { ema = rawAdc; filterReady = true; }
    ema += 0.25f * (float(rawAdc) - ema);
    filtered = uint16_t(ema + 0.5f);
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
    pinMode(ADC_PIN, INPUT);
    pinMode(FORWARD_PIN, INPUT_PULLUP);
    forwardRaw = forwardPressed = digitalRead(FORWARD_PIN) == LOW;
    matrixBegin();
    analogReadResolution(12); analogSetPinAttenuation(ADC_PIN, ADC_11db);
    Serial.begin(115200); bootId = esp_random();
    scanDisplay();
    if (prefs.begin("jr-m3", true)) {
        if (prefs.getBytesLength("cal") == sizeof(saved)) prefs.getBytes("cal", &saved, sizeof(saved));
        prefs.end();
    }
    calibrated = validCalibration(saved);
    ack("jr_matrix_ready_adc3_din6_cs5_clk4");
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
        const bool ready = calibrated && !collecting && notch >= 0;
        Serial.printf("{\"v\":1,\"type\":\"state\",\"boot\":%lu,\"seq\":%lu,\"ms\":%lu,\"raw\":%u,\"adc\":%u,\"calibrated\":%s,\"notch\":\"%s\",\"forward_pressed\":%s,\"forward_count\":%lu}\n",
            (unsigned long)bootId, (unsigned long)sequence++, (unsigned long)now,
            rawAdc, filtered, ready ? "true":"false", ready ? names[notch]:"--",
            forwardPressed ? "true":"false", (unsigned long)forwardCount);
    }
    if (uint32_t(now-displayAt) >= 100) {
        displayAt = now;
        matrixShow(collecting ? "C" : (notch >= 0 ? names[notch] : "--"));
    }
}
