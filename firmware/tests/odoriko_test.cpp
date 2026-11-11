#include "../src/odoriko.h"
#include "../src/button_calibration.h"
#include <assert.h>
#include <string.h>

int main() {
    Odoriko control;
    const int n = Odoriko::NEUTRAL;
    assert(control.pcOutput() && control.duty() == 0);

    // A short standalone press survives the chord detection window.
    control.update(20, n, 'N', true, 1);
    assert(control.takePcButtons() == 0);
    control.update(70, n, 'N', true, 0);
    assert(control.takePcButtons() == 1 && control.takePcButtons() == 0);

    control.update(100, n, 'N', true, 1);
    control.update(160, n, 'N', true, 9);
    control.update(1159, n, 'N', true, 9);
    assert(control.pcOutput() && control.takePcButtons() == 0);
    control.update(1160, n, 'N', true, 9);
    assert(!control.pcOutput() && strcmp(control.display(n, 'N'), "PC") == 0);
    control.update(1200, n, 'N', true, 0);
    control.update(1240, n, 'N', true, 2);
    assert(strcmp(control.display(n, 'N'), "Od") == 0);
    control.update(1280, n + 1, 'N', true, 4);
    assert(strcmp(control.display(n + 1, 'N'), "Hn") == 0);
    control.update(1320, n, 'N', true, 0);
    control.update(1360, n, 'N', true, 4);
    control.update(1400, n, 'N', true, 0);
    assert(!control.pcOutput() && !control.display(n, 'N') && control.duty() == 0);

    control.update(1450, n, 'F', true, 0);
    control.update(1550, n + 5, 'F', true, 0);
    assert(control.direction() == 'F' && control.duty() == 15);
    control.update(1570, n - 1, 'F', true, 0);
    assert(control.duty() == 14);
    control.update(1650, n, 'F', true, 0);
    assert(control.direction() == 'F' && control.duty() == 10);
    control.update(1750, 5, 'F', true, 0);
    assert(control.duty() == 0);
    control.update(1850, n + 5, 'F', true, 0);
    control.update(1860, n + 5, 'F', false, 0);
    assert(control.direction() == 'N' && control.duty() == 0);
    control.update(1870, n, 'R', true, 0);
    assert(control.direction() == 'N' && control.duty() == 0);
    control.update(1880, n, 'N', true, 0);
    control.update(1890, n, 'R', true, 0);
    control.update(1990, n + 5, 'R', true, 0);
    assert(control.direction() == 'R' && control.duty() == 15);
    control.update(2000, 0, 'R', true, 0);
    assert(control.duty() == 0 && strcmp(control.display(0, 'R'), "EB") == 0);
    control.update(2100, n + 5, 'R', true, 0);
    assert(control.duty() == 0 && strcmp(control.display(n + 5, 'R'), "Hn") == 0);
    control.update(2200, n, 'R', true, 0);
    assert(control.duty() == 0 && control.direction() == 'R' && !control.display(n, 'R'));
    control.update(2300, n + 5, 'R', true, 0);
    assert(control.duty() == 15);

    control.update(4200, -1, 'X', false, 0);
    assert(control.direction() == 'N' && control.duty() == 0);
    control.update(6300, n, 'N', true, 0);
    control.update(6400, n + 5, 'R', true, 0);
    assert(control.duty() == 0);
    control.update(6450, n, 'N', true, 0);
    control.update(6500, n, 'N', true, 4);
    control.update(6550, n, 'N', true, 0);
    control.update(6600, n, 'R', true, 0);
    control.update(6700, n + 5, 'R', true, 0);
    assert(control.direction() == 'R' && control.duty() == 15);
    control.update(6750, n + 5, 'R', true, 8);
    control.update(6850, n + 5, 'R', true, 8);
    assert(control.duty() == 0 && strcmp(control.display(n + 5, 'R'), "--") == 0);
    control.update(6880, 0, 'R', true, 0);
    assert(control.duty() == 0 && strcmp(control.display(0, 'R'), "EB") == 0);

    control.update(6900, n, 'N', true, 9);
    control.update(7900, n, 'N', true, 9);
    control.update(8000, n, 'N', true, 0);
    control.update(8100, n, 'N', true, 1);
    control.update(8200, n, 'N', true, 4);
    assert(control.pcOutput() && control.duty() == 0 && control.takePcButtons() == 0);

    const uint8_t calibratedMap[] = {4, 8, 1, 2};
    Odoriko remapped;
    // Physical contacts 3 and 2 are A and Y in this saved calibration.
    remapped.update(20, n, 'N', true, mappedButtons(6, calibratedMap));
    remapped.update(1020, n, 'N', true, mappedButtons(6, calibratedMap));
    assert(!remapped.pcOutput() && remapped.takePcButtons() == 0);
    remapped.update(1060, n, 'N', true, 0);
    remapped.update(1100, n, 'N', true, mappedButtons(8, calibratedMap));
    assert(strcmp(remapped.display(n, 'N'), "Od") == 0);
    remapped.update(1140, n, 'N', true, mappedButtons(1, calibratedMap));
    remapped.update(1180, n, 'N', true, 0);
    assert(validOdorikoRates(remapped.rates));
    remapped.rates.accel = 20;
    remapped.rates.coast = 60;
    remapped.rates.brake = 10;
    remapped.update(1220, n, 'F', true, 0);
    remapped.update(1320, n + 5, 'F', true, 0);
    assert(remapped.duty() == 10);
    remapped.update(1420, n, 'F', true, 0);
    assert(remapped.duty() == 4);
    remapped.update(1520, n - 1, 'F', true, 0);
    assert(remapped.duty() == 3);
    remapped.update(1560, n + 5, 'F', true, mappedButtons(2, calibratedMap));
    remapped.update(1660, n + 5, 'F', true, mappedButtons(2, calibratedMap));
    assert(remapped.duty() == 0);
    remapped.rates.coast = 256;
    assert(!validOdorikoRates(remapped.rates));

    Odoriko prompt;
    prompt.update(100, n + 1, 'F', true, 8);
    assert(prompt.takePcButtons() == 0);
    prompt.update(140, n + 1, 'F', true, 9);
    prompt.update(1500, n + 1, 'F', true, 9);
    assert(prompt.pcOutput() && prompt.takePcButtons() == 0);
    assert(strcmp(prompt.display(n + 1, 'F', 1500), "N") == 0);
    assert(strcmp(prompt.display(n + 1, 'F', 1750), "") == 0);
    prompt.update(1800, n, 'N', true, 9);
    prompt.update(2799, n, 'N', true, 9);
    assert(prompt.pcOutput());
    prompt.update(2800, n, 'N', true, 9);
    assert(!prompt.pcOutput() && strcmp(prompt.display(n, 'N'), "PC") == 0);
}
