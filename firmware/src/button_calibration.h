#pragma once
#include <stdint.h>

constexpr bool validButtonMap(const uint8_t *map) {
    return (map[0]==1 || map[0]==2 || map[0]==4 || map[0]==8) &&
           (map[1]==1 || map[1]==2 || map[1]==4 || map[1]==8) &&
           (map[2]==1 || map[2]==2 || map[2]==4 || map[2]==8) &&
           (map[3]==1 || map[3]==2 || map[3]==4 || map[3]==8) &&
           (map[0]|map[1]|map[2]|map[3])==15;
}
constexpr uint8_t mappedButtons(uint8_t raw,const uint8_t *map) {
    return ((raw&map[0])?1:0) | ((raw&map[1])?2:0) | ((raw&map[2])?4:0) | ((raw&map[3])?8:0);
}
constexpr uint8_t BUTTON_MAP_DEFAULT[]={1,2,4,8}, BUTTON_MAP_REVERSE[]={8,4,2,1};
constexpr uint8_t BUTTON_MAP_DUPLICATE[]={1,1,4,8}, BUTTON_MAP_MULTI[]={3,2,4,8};
static_assert(validButtonMap(BUTTON_MAP_DEFAULT) && validButtonMap(BUTTON_MAP_REVERSE),"Button permutations");
static_assert(!validButtonMap(BUTTON_MAP_DUPLICATE) && !validButtonMap(BUTTON_MAP_MULTI),"Reject duplicate/multiple contacts");
static_assert(mappedButtons(5,BUTTON_MAP_REVERSE)==10 && mappedButtons(15,BUTTON_MAP_DEFAULT)==15,"Remap simultaneous buttons");
