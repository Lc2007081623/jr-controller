#pragma once
#include <stdint.h>

constexpr bool validReverserCalibration(const uint8_t *map) {
    return map[1] == 0 && ((map[0] == 1 && map[2] == 2) || (map[0] == 2 && map[2] == 1));
}
constexpr uint8_t NORMAL_REV[] = {1,0,2}, SWAPPED_REV[] = {2,0,1};
constexpr uint8_t DUPLICATE_REV[] = {1,0,1}, BAD_NEUTRAL_REV[] = {1,3,2};
static_assert(validReverserCalibration(NORMAL_REV) && validReverserCalibration(SWAPPED_REV), "Both switch directions");
static_assert(!validReverserCalibration(DUPLICATE_REV) && !validReverserCalibration(BAD_NEUTRAL_REV), "Invalid contacts");
