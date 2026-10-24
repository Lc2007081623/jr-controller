#include <Arduino.h>
#include <Wire.h>

#if !CONFIG_IDF_TARGET_ESP32S3
#error "This tested pin assignment is for ESP32-S3; GPIO15 is not a general I2C pin on ESP32-C3."
#endif

constexpr int SDA_PIN = 7, SCL_PIN = 15;
constexpr uint8_t ADDRESS = 0x36;
constexpr bool magnetHealthy(uint8_t status) {
    return (status & 0x20) && !(status & 0x18);
}
static_assert(magnetHealthy(0x20), "Magnet detected, neither weak nor strong");
static_assert(!magnetHealthy(0x00) && !magnetHealthy(0x30) && !magnetHealthy(0x28),
              "Missing, weak and strong magnetic fields must not claim valid angle");

bool readRegister(uint8_t reg, uint8_t *buffer, uint8_t count) {
    Wire.beginTransmission(ADDRESS);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(ADDRESS, count) != count) {
        while (Wire.available()) Wire.read();
        return false;
    }
    for (uint8_t i = 0; i < count; ++i) buffer[i] = Wire.read();
    return true;
}

void setup() {
    Serial.begin(115200);
    Wire.begin(SDA_PIN, SCL_PIN, 100000);
    Wire.setTimeOut(20);
    Serial.println("AS5600 TEST / ESP32-S3 / SDA7 SCL15 / address 0x36 / 115200 baud");
    Serial.printf("{\"type\":\"i2c_scan\",\"sda_level\":%d,\"scl_level\":%d,\"addresses\":[",
                  digitalRead(SDA_PIN), digitalRead(SCL_PIN));
    bool first = true;
    for (uint8_t address = 1; address < 127; ++address) {
        Wire.beginTransmission(address);
        if (Wire.endTransmission() == 0) {
            Serial.printf("%s%u", first ? "" : ",", address);
            first = false;
        }
    }
    Serial.println("]}");
}

void loop() {
    uint8_t status = 0, angle[2] = {};
    bool connected = readRegister(0x0b, &status, 1) && readRegister(0x0c, angle, 2);
    if (!connected) {
        Serial.println("{\"type\":\"as5600\",\"i2c_ok\":false,\"valid\":false,\"error\":\"check_power_sda7_scl15\"}");
    } else {
        uint16_t raw = (uint16_t(angle[0] & 0x0f) << 8) | angle[1];
        Serial.printf("{\"type\":\"as5600\",\"i2c_ok\":true,\"status\":%u,\"magnet_detected\":%s,\"weak\":%s,\"strong\":%s,\"valid\":%s,\"raw\":%u,\"degrees\":%.2f}\n",
            status, status & 0x20 ? "true" : "false", status & 0x10 ? "true" : "false",
            status & 0x08 ? "true" : "false", magnetHealthy(status) ? "true" : "false",
            raw, raw * (360.0f / 4096));
    }
    delay(100);
}
