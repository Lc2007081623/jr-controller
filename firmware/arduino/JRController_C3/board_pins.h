#pragma once
#include <Arduino.h>

#if CONFIG_IDF_TARGET_ESP32C3
#ifdef JR_HIDARI_2
constexpr uint8_t DIN_PIN = 0, CS_PIN = 10, CLK_PIN = 7;
constexpr uint8_t PCF8574_ADDRESS = 0x20;
constexpr int MOTOR_IN1_PIN = 4, MOTOR_IN2_PIN = 3; // U9 MODULE_B, MODULE_A
#else
constexpr uint8_t DIN_PIN = 4, CS_PIN = 3, CLK_PIN = 2;
constexpr int FORWARD_PIN = 7, REVERSE_PIN = 1;
constexpr int BUTTON_PINS[] = {0, 10, 20, 21};
#endif
constexpr int AS5600_SDA = 6, AS5600_SCL = 5;
constexpr const char *BOARD_NAME = "C3";
// Both contacts closed is invalid; a centre-off switch closes neither.
constexpr char reverserPosition(uint8_t contacts) {
    return contacts == 1 ? 'F' : contacts == 2 ? 'R' : contacts == 0 ? 'N' : 'X';
}
static_assert(reverserPosition(0) == 'N' && reverserPosition(1) == 'F' &&
              reverserPosition(2) == 'R' && reverserPosition(3) == 'X', "Reverser contacts");
#elif CONFIG_IDF_TARGET_ESP32S3
constexpr uint8_t DIN_PIN = 6, CS_PIN = 5, CLK_PIN = 4;
constexpr int AS5600_SDA = 7, AS5600_SCL = 15;
constexpr int FORWARD_PIN = 10;
constexpr const char *BOARD_NAME = "S3";
#else
#error "Unsupported controller board"
#endif
