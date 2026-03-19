#include <Arduino.h>

const int LRpin = A0;
const int UDpin = A1;

int LR, UD;
int LR_neutral = 0;
int UD_neutral = 0;

const int Rpin = 11;
const int Ypin = 10;
const int Gpin = 6;
const int Bpin = 9;

int R, Y, G, B;

const int deadzone = 10;

const uint16_t period_ms = 20;
unsigned long lastSend = 0;

void setup() {
  Serial.begin(9600);

  long sumLR = 0, sumUD = 0;
  for (int i = 0; i < 50; i++) {
    sumLR += analogRead(LRpin);
    sumUD += analogRead(UDpin);
    delay(5);
  }
  LR_neutral = sumLR / 50;
  UD_neutral = sumUD / 50;

  pinMode(Rpin, OUTPUT);
  pinMode(Ypin, OUTPUT);
  pinMode(Gpin, OUTPUT);
  pinMode(Bpin, OUTPUT);
}

void loop() {
  LR = analogRead(LRpin);
  UD = analogRead(UDpin);

  int dx = LR - LR_neutral;
  int dy = UD - UD_neutral;

  const char* dir = "CENTER";

  if (abs(dx) <= deadzone && abs(dy) <= deadzone) {
    dir = "CENTER";
  } else if (abs(dx) > abs(dy)) {
    dir = (dx > 0) ? "RIGHT" : "LEFT";
  } else {
    dir = (dy > 0) ? "DOWN" : "UP";
  }

  if (UD >= UD_neutral + deadzone) {
    B = 0;
    R = map(UD, UD_neutral + deadzone, 1023, 0, 255);
  } else if (UD <= UD_neutral - deadzone) {
    R = 0;
    B = map(UD, UD_neutral - deadzone, 0, 0, 255);
  } else {
    R = 0;
    B = 0;
  }

  if (LR >= LR_neutral + deadzone) {
    Y = 0;
    G = map(LR, LR_neutral + deadzone, 1023, 0, 255);
  } else if (LR <= LR_neutral - deadzone) {
    G = 0;
    Y = map(LR, LR_neutral - deadzone, 0, 0, 255);
  } else {
    G = 0;
    Y = 0;
  }

  analogWrite(Rpin, R);
  analogWrite(Ypin, Y);
  analogWrite(Gpin, G);
  analogWrite(Bpin, B);

  // GUI output
  unsigned long now = millis();
  if (now - lastSend >= period_ms) {
    lastSend = now;

    Serial.print(LR); Serial.print(",");
    Serial.print(UD); Serial.print(",");
    Serial.print(dx); Serial.print(",");
    Serial.print(dy); Serial.print(",");
    Serial.println(dir);
  }
}
