"""Export the same C3 firmware sources as a directly openable Arduino sketch."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
TARGET=ROOT/'arduino/JRController_C3'

def main():
    TARGET.mkdir(parents=True,exist_ok=True)
    (TARGET/'JRController_C3.ino').write_text(
        '// ESP32-C3 + AS5600 + MAX7219\n'
        '// Implementation is in controller.cpp to avoid Arduino auto-prototype errors.\n'
        '#include <Arduino.h>\n',encoding='utf-8')
    (TARGET/'controller.cpp').write_text(
        '#define JR_USE_AS5600 1\n'+(ROOT/'src/main.cpp').read_text(encoding='utf-8'),encoding='utf-8')
    for name in ('board_pins.h','matrix_display.h','as5600_input.h','button_calibration.h','reverser_calibration.h'):
        shutil.copy2(ROOT/'src'/name,TARGET/name)
    print(TARGET)

if __name__=='__main__':main()
