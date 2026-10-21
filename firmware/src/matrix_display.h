#pragma once
#include <Arduino.h>
constexpr uint8_t DIN_PIN = 6, CS_PIN = 5, CLK_PIN = 4;
constexpr uint8_t BRIGHTNESS = 2, ROTATION = 0;
constexpr bool MIRROR_X = false;
void writeRegister(uint8_t address, uint8_t value) {
    digitalWrite(CS_PIN, LOW);
    shiftOut(DIN_PIN, CLK_PIN, MSBFIRST, address);
    shiftOut(DIN_PIN, CLK_PIN, MSBFIRST, value);
    digitalWrite(CS_PIN, HIGH);
}


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

inline void matrixFrame(const char *text, uint8_t (&rows)[8]) {
    memset(rows,0,8);
    bool brake=text[0]=='B' && text[1]>='1' && text[1]<='8' && text[2]==0;
    bool power=text[0]=='P' && text[1]>='1' && text[1]<='5' && text[2]==0;
    uint8_t columns[5]={};
    if(brake || power) memcpy(columns,DIGITS[text[1]-'1'],5);
    else if(!strcmp(text,"N")) {uint8_t g[]={0x7f,2,4,8,0x7f};memcpy(columns,g,5);}
    else if(!strcmp(text,"EB")) {uint8_t g[]={0x7f,0x49,0x49,0x49,0x41};memcpy(columns,g,5);}
    else if(!strcmp(text,"C")) {uint8_t g[]={0x3e,0x41,0x41,0x41,0x22};memcpy(columns,g,5);}
    else {for(int i=0;i<5;++i) columns[i]=8;}
    auto pixel=[&](int x,int y) {
        if(MIRROR_X) x=7-x;
        for(uint8_t r=0;r<ROTATION%4;++r) {int previousX=x;x=7-y;y=previousX;}
        rows[y]|=uint8_t(0x80U>>x);
    };
    for(int col=0;col<5;++col) for(int y=0;y<7;++y)
        if(columns[col] & (1U<<y)) pixel(col+1,y);
    // Separate bottom-right LED identifies B1..B8; clear for power, N and E.
    if(brake) pixel(7,7);
}
inline void matrixShow(const char *text) {
    uint8_t rows[8]; matrixFrame(text,rows);
    static uint8_t previous[8]={};
    static bool first=true;
    for(uint8_t row=0;row<8;++row) if(first || rows[row]!=previous[row]) {
        writeRegister(row+1,rows[row]); previous[row]=rows[row];
    }
    first=false;
}
inline void matrixBegin() {
    digitalWrite(CS_PIN,HIGH); digitalWrite(CLK_PIN,LOW); digitalWrite(DIN_PIN,LOW);
    pinMode(CS_PIN,OUTPUT); pinMode(CLK_PIN,OUTPUT); pinMode(DIN_PIN,OUTPUT);
    writeRegister(0x0c,0); writeRegister(0x0f,0); writeRegister(0x09,0);
    writeRegister(0x0b,7); writeRegister(0x0a,BRIGHTNESS);
    for(uint8_t row=1;row<=8;++row) writeRegister(row,0);
    matrixShow("--"); writeRegister(0x0c,1);
}
