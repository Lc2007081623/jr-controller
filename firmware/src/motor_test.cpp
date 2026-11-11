#include <Arduino.h>

#ifdef JR_HIDARI_2
#include "board_pins.h"
constexpr int IN1_PIN = MOTOR_IN1_PIN;
constexpr int IN2_PIN = MOTOR_IN2_PIN;
#else
constexpr int IN1_PIN = 5;
constexpr int IN2_PIN = 6;
#endif
constexpr unsigned long PULSE_MS = 1000;

void setup() {
    pinMode(IN1_PIN, OUTPUT);
    pinMode(IN2_PIN, OUTPUT);
    digitalWrite(IN1_PIN, LOW);
    digitalWrite(IN2_PIN, LOW);
    Serial.begin(115200);
}

void loop() {
    const int command = Serial.read();
    switch (command) {
        case '?':
            Serial.printf("C3 motor test: 1 = GPIO%d high, 2 = GPIO%d high, 1 second per pulse\n",
                          IN1_PIN, IN2_PIN);
            return;
        case '1':
        case '2':
            break;
        default:
            delay(5);
            return;
    }

    const int activePin = command == '1' ? IN1_PIN : IN2_PIN;
    Serial.printf("GPIO%d high for 1 second\n", activePin);
    digitalWrite(activePin, HIGH);
    delay(PULSE_MS);
    digitalWrite(activePin, LOW);
    Serial.printf("GPIO%d=0 GPIO%d=0\n", IN1_PIN, IN2_PIN);
}
