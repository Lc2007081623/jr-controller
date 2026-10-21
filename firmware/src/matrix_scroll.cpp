#include <Arduino.h>

// Single MAX7219 8x8 module, connected at its DIN (input) end.
constexpr uint8_t DIN_PIN = 6, CS_PIN = 5, CLK_PIN = 4;
constexpr uint32_t DIGIT_INTERVAL_MS = 1000;
constexpr uint8_t BRIGHTNESS = 2; // 0..15
constexpr uint8_t ROTATION = 0;   // 0..3 clockwise quarter turns
constexpr bool MIRROR_X = false;

// Five columns per digit, bit 0 at the top.
constexpr uint8_t DIGITS[9][5] = {
    {0x00, 0x42, 0x7f, 0x40, 0x00},
    {0x42, 0x61, 0x51, 0x49, 0x46},
    {0x21, 0x41, 0x45, 0x4b, 0x31},
    {0x18, 0x14, 0x12, 0x7f, 0x10},
    {0x27, 0x45, 0x45, 0x45, 0x39},
    {0x3c, 0x4a, 0x49, 0x49, 0x30},
    {0x01, 0x71, 0x09, 0x05, 0x03},
    {0x36, 0x49, 0x49, 0x49, 0x36},
    {0x06, 0x49, 0x49, 0x29, 0x1e}
};
uint8_t digitIndex = 0;
uint32_t lastFrame = 0;

void writeRegister(uint8_t address, uint8_t value) {
    digitalWrite(CS_PIN, LOW);
    shiftOut(DIN_PIN, CLK_PIN, MSBFIRST, address);
    shiftOut(DIN_PIN, CLK_PIN, MSBFIRST, value);
    digitalWrite(CS_PIN, HIGH);
}

void drawFrame() {
    uint8_t rows[8] = {};
    for (int col = 0; col < 5; ++col) {
        const int x = col + 1;
        const uint8_t column = DIGITS[digitIndex][col];
        for (int y = 0; y < 8; ++y) {
            if (!(column & (1U << y))) continue;
            int px = MIRROR_X ? 7 - x : x, py = y;
            for (uint8_t r = 0; r < ROTATION % 4; ++r) {
                const int previousX = px;
                px = 7 - py;
                py = previousX;
            }
            rows[py] |= uint8_t(0x80U >> px);
        }
    }
    for (uint8_t row = 0; row < 8; ++row) writeRegister(row + 1, rows[row]);
}

void setup() {
    digitalWrite(CS_PIN, HIGH);
    digitalWrite(CLK_PIN, LOW);
    digitalWrite(DIN_PIN, LOW);
    pinMode(CS_PIN, OUTPUT);
    pinMode(CLK_PIN, OUTPUT);
    pinMode(DIN_PIN, OUTPUT);
    Serial.begin(115200);
    writeRegister(0x0c, 0);          // Shutdown during initialization.
    writeRegister(0x0f, 0);          // Display test off.
    writeRegister(0x09, 0);          // Raw matrix pixels, no BCD decoding.
    writeRegister(0x0b, 7);          // Scan all eight rows.
    writeRegister(0x0a, BRIGHTNESS);
    drawFrame();
    writeRegister(0x0c, 1);
    Serial.println("MAX7219 ready: DIN=6 CS=5 CLK=4; digits 1-9, interval 1000ms");
    Serial.println("Digit: 1");
    lastFrame = millis();
}

void loop() {
    const uint32_t now = millis();
    if (uint32_t(now - lastFrame) >= DIGIT_INTERVAL_MS) {
        lastFrame = now;
        digitIndex = (digitIndex + 1) % 9;
        drawFrame();
        Serial.printf("Digit: %u\n", unsigned(digitIndex + 1));
    }
    delay(1);
}
