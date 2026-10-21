#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_SSD1306.h>
#include <Preferences.h>
#include <esp_system.h>

// 2026-10-19 bring-up wiring; the A1 carrier pin assignment is NOT used here.
constexpr int ADC_PIN = 5, SDA_PIN = 11, SCL_PIN = 10;
constexpr int COUNT = 15, MIN_GAP = 25;
const char *const names[COUNT] = {
    "EB", "B8", "B7", "B6", "B5", "B4", "B3", "B2", "B1", "N",
    "P1", "P2", "P3", "P4", "P5"
};
struct Calibration { uint32_t magic; uint16_t centers[COUNT]; };
constexpr uint32_t MAGIC = 0x4a520101;
Calibration saved{}, pending{};
uint16_t captured = 0, rawAdc = 0, filtered = 0;
bool calibrated = false, collecting = false, filterReady = false, oled = false;
int notch = -1;
uint32_t bootId, sequence = 0, sampleAt = 0, reportAt = 0, oledAt = 0;
uint8_t oledAddress = 0;
char command[64]; size_t commandLen = 0;
bool discardLine = false;
Adafruit_SSD1306 screen(128, 64, &Wire, -1, 400000, 100000);
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
    // Only the two normal OLED addresses; an ACK alone does not identify a controller.
    oled = false; oledAddress = 0;
    for (uint8_t addr : {uint8_t(0x3c), uint8_t(0x3d)}) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0 && oledAddress == 0) oledAddress = addr;
    }
    if (oledAddress) oled = screen.begin(SSD1306_SWITCHCAPVCC, oledAddress, false, false);
    Serial.printf("{\"v\":1,\"type\":\"display\",\"address\":%u,\"ready\":%s}\n",
                  oledAddress, oled ? "true" : "false");
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
    } else if (!strcmp(s, "SAVE")) {
        if (!collecting || captured != 0x7fff) { ack("error_capture_all_15"); return; }
        if (!validCalibration(pending)) { ack("error_centers_need_monotonic_spacing25_span500"); return; }
        if (!prefs.begin("jr-v1", false)) { ack("error_nvs_open"); return; }
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
    // Old GPIO4/6 connections never become power outputs in this firmware.
    pinMode(4, INPUT); pinMode(6, INPUT); pinMode(ADC_PIN, INPUT);
    analogReadResolution(12); analogSetPinAttenuation(ADC_PIN, ADC_11db);
    Serial.begin(115200); bootId = esp_random();
    Wire.begin(SDA_PIN, SCL_PIN, 400000); Wire.setTimeOut(15);
    scanDisplay();
    if (prefs.begin("jr-v1", true)) {
        if (prefs.getBytesLength("cal") == sizeof(saved)) prefs.getBytes("cal", &saved, sizeof(saved));
        prefs.end();
    }
    calibrated = validCalibration(saved);
    ack("jr_v1_ready_adc5_sda11_scl10");
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
    if (uint32_t(now-sampleAt) >= 5) { sampleAt = now; sample(); }
    if (uint32_t(now-reportAt) >= 20) {
        reportAt = now;
        const bool ready = calibrated && !collecting && notch >= 0;
        Serial.printf("{\"v\":1,\"type\":\"state\",\"boot\":%lu,\"seq\":%lu,\"ms\":%lu,\"raw\":%u,\"adc\":%u,\"calibrated\":%s,\"notch\":\"%s\"}\n",
            (unsigned long)bootId, (unsigned long)sequence++, (unsigned long)now,
            rawAdc, filtered, ready ? "true":"false", ready ? names[notch]:"--");
    }
    if (oled && uint32_t(now-oledAt) >= 100) {
        oledAt = now;
        Wire.beginTransmission(oledAddress);
        if (Wire.endTransmission() != 0) { oled = false; return; }
        screen.clearDisplay(); screen.setTextColor(SSD1306_WHITE); screen.setTextSize(1); screen.setCursor(0,0);
        screen.printf("ADC5 %4u RAW %4u", filtered, rawAdc);
        screen.setCursor(0,14); screen.setTextSize(3);
        screen.print(collecting ? "CAL" : (notch >= 0 ? names[notch] : "--"));
        screen.setTextSize(1); screen.setCursor(0,43);
        if (collecting) screen.printf("Captured %u/15", __builtin_popcount(captured));
        else screen.print(calibrated ? "Cal OK / local notch" : "Need 15-point cal");
        screen.setCursor(0,55); screen.print(rawAdc >= 4080 ? "TOP SAT: check supply" : "SDA11 SCL10 / SSD1306");
        screen.display();
    }
}
