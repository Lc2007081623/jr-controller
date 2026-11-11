#define JR_USE_AS5600 1
#include <Arduino.h>
#include "matrix_display.h"
#include <Preferences.h>
#include <esp_system.h>
#ifdef JR_USE_AS5600
#include "as5600_input.h"
#endif

// 2026-10-21: validated matrix pins 6/5/4; potentiometer wiper GPIO3.
constexpr int ADC_PIN = 3;
bool forwardRaw = false, forwardPressed = false;
uint32_t forwardChangedAt = 0, forwardCount = 0;
#if CONFIG_IDF_TARGET_ESP32C3
#include "reverser_calibration.h"
#include "button_calibration.h"
int inputsRaw = -1;
uint8_t inputsStable = 0;
bool inputsValid = false;
uint8_t reverserMap[3] = {1,0,2}, reverserPending[3] = {};
uint8_t reverserCaptured = 0;
bool reverserCollecting = false;
uint8_t buttonMap[4]={1,2,4,8}, buttonPending[4]={}, buttonCaptured=0;
bool buttonCollecting=false;
uint32_t inputsChangedAt = 0;
#ifdef JR_HIDARI_2
#include "odoriko.h"
Odoriko odoriko;
uint32_t inputsAt = 0;
constexpr uint8_t IN1_CHANNEL = 0, IN2_CHANNEL = 1;

void updateMotorOutput() {
    static uint8_t lastIn1 = 0, lastIn2 = 0;
    const uint8_t in1 = odoriko.direction() == 'F' ? odoriko.duty() : 0;
    const uint8_t in2 = odoriko.direction() == 'R' ? odoriko.duty() : 0;
    if (lastIn1 && !in1) ledcWrite(IN1_CHANNEL, 0);
    if (lastIn2 && !in2) ledcWrite(IN2_CHANNEL, 0);
    if (in1 && in1 != lastIn1) ledcWrite(IN1_CHANNEL, in1);
    if (in2 && in2 != lastIn2) ledcWrite(IN2_CHANNEL, in2);
    lastIn1 = in1;
    lastIn2 = in2;
}

constexpr uint8_t decodeInputs(uint8_t port) {
    // The protocol mask puts forward/reverse below the four buttons.
    return ((uint8_t(~port) & 0x0f) << 2) | ((uint8_t(~port) & 0x30) >> 4);
}
static_assert(decodeInputs(0xff) == 0 && decodeInputs(0xf0) == 0x3c &&
              decodeInputs(0xef) == 1 && decodeInputs(0xdf) == 2 &&
              decodeInputs(0x00) == 0x3f, "Hidari 2 contact mapping");

int readInputs() {
    static bool initialized = false;
    if (!initialized) {
        Wire.beginTransmission(PCF8574_ADDRESS);
        Wire.write(uint8_t{0xff});  // Release all quasi-bidirectional pins for input.
        if (Wire.endTransmission() != 0) return -1;
        initialized = true;
    }
    if (Wire.requestFrom(PCF8574_ADDRESS, uint8_t{1}) == 1) {
        const int port = Wire.read();
        if (port >= 0) return decodeInputs(uint8_t(port));
    }
    initialized = false;
    return -1;
}
#else
int readInputs() {
    uint8_t bits = (digitalRead(FORWARD_PIN) == LOW) | ((digitalRead(REVERSE_PIN) == LOW) << 1);
    for (int i = 0; i < 4; ++i) bits |= (digitalRead(BUTTON_PINS[i]) == LOW) << (i+2);
    return bits;
}
#endif
#endif
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
#ifndef JR_FIRMWARE_VERSION
#ifdef JR_HIDARI_2
#define JR_FIRMWARE_VERSION 1.2.4
#else
#define JR_FIRMWARE_VERSION 1.1.0
#endif
#endif
#define JR_STRINGIFY_IMPL(value) #value
#define JR_STRINGIFY(value) JR_STRINGIFY_IMPL(value)
constexpr const char *FIRMWARE_VERSION = JR_STRINGIFY(JR_FIRMWARE_VERSION);
bool calibrated = false, collecting = false, filterReady = false;
bool positionValid = true, sensorFaultPending = false;
uint8_t sensorStatus = 0;
int notch = -1;
char deviceId[13];
#if defined(JR_HIDARI_2)
constexpr const char *MODEL = "JR-C3-HIDARI-2";
#elif CONFIG_IDF_TARGET_ESP32C3 && defined(JR_USE_AS5600)
constexpr const char *MODEL = "JR-C3-AS5600-R1";
#elif defined(JR_USE_AS5600)
constexpr const char *MODEL = "JR-S3-AS5600";
#else
constexpr const char *MODEL = "JR-S3-ADC";
#endif
uint32_t bootId, sequence = 0, sampleAt = 0, reportAt = 0, displayAt = 0;
char command[256]; size_t commandLen = 0;
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

#ifdef JR_HIDARI_2
void reportOdorikoRates(bool saved) {
    const auto &rates = odoriko.rates;
    Serial.printf("{\"v\":1,\"type\":\"odoriko_config\",\"accel\":%u,\"coast\":%u,\"brake\":%u,\"saved\":%s}\n",
                  rates.accel, rates.coast, rates.brake, saved ? "true" : "false");
}

void saveOdorikoRates(const char *payload) {
    if (!odoriko.pcOutput() && (odoriko.direction() != 'N' || notch != Odoriko::NEUTRAL ||
                               !inputsValid || inputsRaw < 0 || (inputsRaw & 3) ||
                               (inputsStable & 3) || !positionValid)) {
        ack("error_odoriko_neutral");
        return;
    }
    OdorikoRates next;
    for (auto field : {&next.accel, &next.coast, &next.brake}) {
        if (*payload < '0' || *payload > '9') { ack("error_odoriko_rates"); return; }
        char *end = nullptr;
        const unsigned long value = strtoul(payload, &end, 10);
        if (value < 1 || value > 255 || (*end != ' ' && *end != '\0')) {
            ack("error_odoriko_rates"); return;
        }
        *field = uint16_t(value);
        payload = end;
        while (*payload == ' ') ++payload;
    }
    if (*payload) { ack("error_odoriko_rates"); return; }
    if (!prefs.begin("jr-odoriko", false)) { ack("error_odoriko_save"); return; }
    const size_t written = prefs.putBytes("rates", &next, sizeof(next));
    prefs.end();
    if (written != sizeof(next)) { ack("error_odoriko_save"); return; }
    odoriko.rates = next;
    reportOdorikoRates(true);
}
#endif

void scanDisplay() {
#ifdef JR_USE_AS5600
    Serial.printf("{\"v\":1,\"type\":\"display\",\"driver\":\"MAX7219\",\"board\":\"%s\",\"din\":%u,\"cs\":%u,\"clk\":%u,\"sensor\":\"AS5600\",\"sda\":%d,\"scl\":%d,\"readback\":false}\n", BOARD_NAME, DIN_PIN, CS_PIN, CLK_PIN, AS5600_SDA, AS5600_SCL);
#else
    // MAX7219 has no readback; this reports configuration, not detected hardware.
    Serial.println("{\"v\":1,\"type\":\"display\",\"driver\":\"MAX7219\",\"din\":6,\"cs\":5,\"clk\":4,\"adc_pin\":3,\"readback\":false}");
#endif
}

int matrixHex(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

void configureMatrix(const char *payload) {
    // Enable, rotation, brightness, 4 hex mask digits, then 15 eight-byte frames.
    if (strlen(payload) != 247) { ack("error_led_config"); return; }
    MatrixSettings next;
    uint8_t values[247];
    for (int i = 0; i < 247; ++i) {
        int value = matrixHex(payload[i]);
        if (value < 0) { ack("error_led_config"); return; }
        values[i] = value;
    }
    if (values[0] > 1 || values[1] > 3 || values[3] > 7) {
        ack("error_led_config"); return;
    }
    next.enabled = values[0] != 0;
    next.rotation = values[1];
    next.brightness = values[2];
    for (int i = 3; i < 7; ++i) next.customMask = (next.customMask << 4) | values[i];
    for (int i = 0; i < COUNT; ++i)
        for (int y = 0; y < 8; ++y) {
            int offset = 7 + (i * 8 + y) * 2;
            next.patterns[i][y] = (values[offset] << 4) | values[offset + 1];
        }
    matrixSettings = next;
    writeRegister(0x0a, next.brightness);
    writeRegister(0x0c, next.enabled ? 1 : 0);
    ack("led_config_applied");
}

void runCommand(char *s) {
#ifdef JR_HIDARI_2
    if (!strcmp(s, "ODGET")) { reportOdorikoRates(false); return; }
    if (!strncmp(s, "ODSET ", 6)) { saveOdorikoRates(s + 6); return; }
    if (!odoriko.pcOutput() && (!strcmp(s, "BEGIN") || !strcmp(s, "KBEGIN") || !strcmp(s, "RBEGIN"))) {
        ack("error_calibration_requires_pc_mode");
        return;
    }
#endif
    if (!strncmp(s, "LED ", 4)) { configureMatrix(s + 4); return; }
#if CONFIG_IDF_TARGET_ESP32C3
    if (s[0]=='K') {
        if (!strcmp(s,"KBEGIN")) {
            buttonCollecting=true;buttonCaptured=0;collecting=false;reverserCollecting=false;
            ack("button_calibration_started");
        } else if (!strncmp(s,"KCAP ",5)) {
            if (!buttonCollecting) { ack("error_button_begin_first");return; }
            int index=-1;
            for (int i=0;i<4;++i) if (s[5]=="ABXY"[i] && !s[6]) index=i;
            if (index<0) { ack("error_button_name");return; }
            uint8_t raw=inputsStable>>2;
            if (!inputsValid || !raw || (raw&(raw-1)) || readInputs()!=inputsStable || uint32_t(millis()-inputsChangedAt)<60) {
                ack("error_button_hold_one");return;
            }
            for (int i=0;i<4;++i) if (i!=index && (buttonCaptured&(1<<i)) && buttonPending[i]==raw) {
                ack("error_button_duplicate");return;
            }
            buttonPending[index]=raw;buttonCaptured|=1<<index;
            Serial.printf("{\"v\":1,\"type\":\"button_capture\",\"button\":\"%c\",\"contact\":%u}\n","ABXY"[index],raw);
        } else if (!strcmp(s,"KSAVE")) {
            if (!buttonCollecting || buttonCaptured!=15 || !validButtonMap(buttonPending)) {
                ack("error_button_capture_all_four");return;
            }
            if (!prefs.begin("jr-btn",false)) { ack("error_nvs_open");return; }
            size_t written=prefs.putBytes("map",buttonPending,4);prefs.end();
            if (written!=4) { ack("error_nvs_write");return; }
            memcpy(buttonMap,buttonPending,4);buttonCollecting=false;ack("button_calibration_saved");
        } else if (!strcmp(s,"KCANCEL")) {
            buttonCollecting=false;ack("button_calibration_cancelled");
        } else if (strcmp(s,"KDUMP")) { ack("error_unknown_command");return; }
        Serial.printf("{\"v\":1,\"type\":\"button_config\",\"map\":[%u,%u,%u,%u],\"collecting\":%s}\n",buttonMap[0],buttonMap[1],buttonMap[2],buttonMap[3],buttonCollecting?"true":"false");
        return;
    }
    if (s[0] == 'R') {
        if (!strcmp(s,"RBEGIN")) {
            reverserCollecting = true; reverserCaptured = 0;
            buttonCollecting=false;collecting=false;
            ack("reverser_calibration_started");
        } else if (!strncmp(s,"RCAP ",5)) {
            if (!reverserCollecting) { ack("error_reverser_begin_first"); return; }
            const char *names[] = {"F","N","R"};
            int index = -1;
            for (int i = 0; i < 3; ++i) if (!strcmp(s+5,names[i])) index = i;
            if (index < 0) { ack("error_reverser_name"); return; }
            if (!inputsValid || readInputs() != inputsStable || uint32_t(millis()-inputsChangedAt) < 60) {
                ack("error_reverser_hold_still"); return;
            }
            reverserPending[index] = inputsStable & 3;
            reverserCaptured |= 1 << index;
            Serial.printf("{\"v\":1,\"type\":\"reverser_capture\",\"position\":\"%s\",\"contacts\":%u}\n",names[index],reverserPending[index]);
        } else if (!strcmp(s,"RSAVE")) {
            if (!reverserCollecting || reverserCaptured != 7 || !validReverserCalibration(reverserPending)) {
                ack("error_reverser_need_distinct_F_N_R_center_off"); return;
            }
            if (!prefs.begin("jr-rev",false)) { ack("error_nvs_open"); return; }
            size_t written = prefs.putBytes("map",reverserPending,3); prefs.end();
            if (written != 3) { ack("error_nvs_write"); return; }
            memcpy(reverserMap,reverserPending,3); reverserCollecting = false;
            ack("reverser_calibration_saved");
        } else if (!strcmp(s,"RCANCEL")) {
            reverserCollecting = false; ack("reverser_calibration_cancelled");
        } else if (strcmp(s,"RDUMP")) { ack("error_unknown_command"); return; }
        Serial.printf("{\"v\":1,\"type\":\"reverser_config\",\"F\":%u,\"N\":%u,\"R\":%u,\"collecting\":%s}\n",reverserMap[0],reverserMap[1],reverserMap[2],reverserCollecting ? "true":"false");
        return;
    }
#endif
    if (!strcmp(s, "BEGIN")) {
#if CONFIG_IDF_TARGET_ESP32C3
        buttonCollecting=false;reverserCollecting=false;
#endif
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
#ifdef JR_HIDARI_2
    pinMode(MOTOR_IN1_PIN, OUTPUT);
    pinMode(MOTOR_IN2_PIN, OUTPUT);
    digitalWrite(MOTOR_IN1_PIN, LOW);
    digitalWrite(MOTOR_IN2_PIN, LOW);
    ledcSetup(IN1_CHANNEL, 2000, 8);
    ledcSetup(IN2_CHANNEL, 2000, 8);
    ledcAttachPin(MOTOR_IN1_PIN, IN1_CHANNEL);
    ledcAttachPin(MOTOR_IN2_PIN, IN2_CHANNEL);
    Serial.setTxTimeoutMs(5);
    if (prefs.begin("jr-odoriko", true)) {
        OdorikoRates stored;
        if (prefs.getBytesLength("rates") == sizeof(stored) &&
            prefs.getBytes("rates", &stored, sizeof(stored)) == sizeof(stored) &&
            validOdorikoRates(stored)) odoriko.rates = stored;
        prefs.end();
    }
#endif
#ifndef JR_USE_AS5600
    pinMode(ADC_PIN, INPUT);
#endif
#ifndef JR_HIDARI_2
    pinMode(FORWARD_PIN, INPUT_PULLUP);
    forwardRaw = forwardPressed = digitalRead(FORWARD_PIN) == LOW;
#endif
#if CONFIG_IDF_TARGET_ESP32C3
#ifndef JR_HIDARI_2
    pinMode(REVERSE_PIN, INPUT_PULLUP);
    for (int pin : BUTTON_PINS) pinMode(pin, INPUT_PULLUP);
    inputsRaw = inputsStable = readInputs();
    inputsValid = true;
#endif
    if (prefs.begin("jr-btn",true)) {
        uint8_t map[4]={};
        if (prefs.getBytesLength("map")==4 && prefs.getBytes("map",map,4)==4 && validButtonMap(map))
            memcpy(buttonMap,map,4);
        prefs.end();
    }
    if (prefs.begin("jr-rev",true)) {
        uint8_t map[3] = {};
        if (prefs.getBytesLength("map") == 3 && prefs.getBytes("map",map,3) == 3 && validReverserCalibration(map))
            memcpy(reverserMap,map,3);
        prefs.end();
    }
#endif
    uint64_t mac = ESP.getEfuseMac();
    for (int i = 0; i < 6; ++i)
        snprintf(deviceId + i * 2, 3, "%02x", (unsigned)((mac >> (i * 8)) & 0xff));
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
    ack("jr_as5600_ready");
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
#if CONFIG_IDF_TARGET_ESP32C3
#ifdef JR_HIDARI_2
    if (uint32_t(now-inputsAt) >= 5) {
        inputsAt = now;
#else
    {
#endif
        const int inputs = readInputs();
        if (inputs != inputsRaw) { inputsRaw = inputs; inputsChangedAt = now; }
        if (inputs < 0) {
            inputsValid = false;
        } else if (uint32_t(now-inputsChangedAt) >= 30) {
            inputsStable = uint8_t(inputsRaw);
            inputsValid = true;
        }
    }
#else
    bool pressed = digitalRead(FORWARD_PIN) == LOW;
    if (pressed != forwardRaw) { forwardRaw = pressed; forwardChangedAt = now; }
    if (forwardRaw != forwardPressed && uint32_t(now-forwardChangedAt) >= 30) {
        forwardPressed = forwardRaw;
        if (forwardPressed) ++forwardCount;
    }
#endif
    if (uint32_t(now-sampleAt) >= 5) { sampleAt = now; sample(); }
#if CONFIG_IDF_TARGET_ESP32C3
    char reverser = 'X';
    if (inputsValid && !reverserCollecting) {
        for (int i = 0; i < 3; ++i) if ((inputsStable & 3) == reverserMap[i]) reverser = "FNR"[i];
    }
#endif
#ifdef JR_HIDARI_2
    const bool modelInputsValid = positionValid && !sensorFaultPending && calibrated &&
                                 !collecting && !reverserCollecting && !buttonCollecting && inputsValid;
    odoriko.update(now, modelInputsValid ? notch : -1, reverser,
                   inputsRaw >= 0 && (inputsRaw & 3) == (inputsStable & 3),
                   inputsValid ? mappedButtons(inputsStable >> 2, buttonMap) : 0);
    updateMotorOutput();
    forwardPressed = odoriko.pcOutput() && reverser == 'F';
#endif
    if (uint32_t(now-reportAt) >= 20) {
        reportAt = now;
        const bool healthy = positionValid && !sensorFaultPending;
        const bool ready = calibrated && !collecting && notch >= 0 && healthy
#if CONFIG_IDF_TARGET_ESP32C3
            && inputsValid && !buttonCollecting
#endif
#ifdef JR_HIDARI_2
            && odoriko.pcOutput()
#endif
            ;
        Serial.printf("{\"v\":1,\"type\":\"state\",\"boot\":%lu,\"seq\":%lu,\"ms\":%lu,\"raw\":%u,\"adc\":%u,\"calibrated\":%s,\"notch\":\"%s\",\"forward_pressed\":%s,\"forward_count\":%lu,\"sensor\":\"%s\",\"sensor_ok\":%s,\"board\":\"%s\"",
            (unsigned long)bootId, (unsigned long)sequence++, (unsigned long)now,
            rawAdc, filtered, ready ? "true":"false", ready ? names[notch]:"--",
            forwardPressed ? "true":"false", (unsigned long)forwardCount, SOURCE, healthy ? "true":"false", BOARD_NAME);
#if CONFIG_IDF_TARGET_ESP32C3
#ifdef JR_HIDARI_2
        const uint8_t pcButtons = odoriko.takePcButtons();
        Serial.printf(",\"reverser\":\"%c\",\"buttons\":%u", odoriko.pcOutput() ? reverser : 'X',
                      inputsValid && odoriko.pcOutput() ? pcButtons : 0);
#else
        Serial.printf(",\"reverser\":\"%c\",\"buttons\":%u", reverser,
                      inputsValid ? mappedButtons(inputsStable>>2,buttonMap) : 0);
#endif
#ifdef JR_HIDARI_2
        Serial.printf(",\"inputs_ok\":%s,\"mode\":\"%s\"", inputsValid ? "true" : "false", odoriko.mode());
#endif
#endif
        Serial.printf(",\"led_config\":true,\"model\":\"%s\",\"firmware\":\"%s\",\"device_id\":\"%s\"}\n",
                      MODEL, FIRMWARE_VERSION, deviceId);
        sensorFaultPending = false;
    }
    if (uint32_t(now-displayAt) >= 100) {
        displayAt = now;
#ifdef JR_HIDARI_2
        const char *label = odoriko.display(modelInputsValid ? notch : -1, reverser, now);
        const bool displayEnabled = matrixSettings.enabled || !odoriko.pcOutput() || label;
        writeRegister(0x0c, displayEnabled ? 1 : 0);
        if (label) {
            matrixShow(label);
            return;
        }
#endif
        matrixShow(!positionValid ? "--" : (collecting ? "C" : (notch >= 0 ? names[notch] : "--")),
                   positionValid && !collecting ? notch : -1);
    }
}
