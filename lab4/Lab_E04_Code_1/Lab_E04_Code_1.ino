#include <Arduino.h>

const int LRpin = A0;                                   // analog pin A0 as left-right axis input pin
const int UDpin = A1;                                   // analog pin A1 as up-down axis input pin

int LR;                                                 // to store the current left-right analog reading
int UD;                                                 // to store the current up-down analog reading
int LR_neutral;                                         // to store the current left-right neutral/center value
int UD_neutral;                                         // to store the current up-down neutral/center value

// ~ = PWM register - Pulse Width Modulation registers
const int Rpin = 11;                                    // red LED output pin as pin 11 
const int Ypin = 10;                                    // yellow LED output pin as pin 10 
const int Gpin = 6;                                     // green LED output pin as pin 6
const int Bpin = 9;                                     // blue LED output pin as pin 9 

int R, Y, G, B;                                         // R, Y, G, B are storing the brightness for LEDs

const int deadzone = 20;                                // neutral zone in the center to ignore movement of joystick 

// send rate for GUI
const uint16_t period_ms = 20;                          // set serial sending period to 20 ms, 50 updates per sec
unsigned long lastSend = 0;                             // store last time data sent to GUI

void setup() {
  Serial.begin(9600);                                   // default serial communication speed 9600 bits per second 

  long sumLR = 0, sumUD = 0;                            // variables to store a large number of joystick readings
  for (int i = 0; i < 50; i++) {                        // repeat 50 times to get stable center value
    sumLR += analogRead(LRpin);                         // read left-right axis and add to total
    sumUD += analogRead(UDpin);                         // read up-down axis and add to total
    delay(5);                                           // wait 5 ms for stability
  }
  LR_neutral = sumLR / 50;                              // calculate average left-right value as center
  UD_neutral = sumUD / 50;                              // calculate average up-down value as center

  pinMode(Rpin, OUTPUT);                                // set red LED pin as output
  pinMode(Ypin, OUTPUT);                                // set yellow LED pin as output
  pinMode(Gpin, OUTPUT);                                // set green LED pin as output
  pinMode(Bpin, OUTPUT);                                // set blue LED pin as output
}

void loop() {
  LR = analogRead(LRpin);                               // read the current joystick value from left-right
  UD = analogRead(UDpin);                               // read the current joystick value from up-down

  int dx = LR - LR_neutral;                             // calculate the distance of left-right from center
  int dy = UD - UD_neutral;                             // calculate the distance of up-down from center

  const char* dir = "CENTER";                           // create a text variable for direction; by default = CENTER

  if (abs(dx) <= deadzone && abs(dy) <= deadzone) {     // if both close to center
    dir = "CENTER";                                     // direction is CENTER
  } else if (abs(dx) > abs(dy)) {                       // if horizontal is larger than vertical distance
    dir = (dx > 0) ? "RIGHT" : "LEFT";                  // if dx is positive - RIGHT, else - LEFT
  } else {                                              // otherwise vertical distance is larger
    dir = (dy > 0) ? "DOWN" : "UP";                     // if dy is positive - DOWN, else - UP
  }
  
  // ADC (Analog-to-Digital Converter) reads values from 0 to 1023
  // PWM (Pulse Width Modulation) controls brightness from 0 to 255
  if (UD >= UD_neutral + deadzone) {                    // if joystick is below center and beyond deadzone
    B = 0;                                              // turn blue LED off
    R = map(UD, UD_neutral + deadzone, 1023, 0, 255);   // increase red LED brightness as joystick moves down
  } else if (UD <= UD_neutral - deadzone) {             // if joystick is above center and beyond deadzone
    R = 0;                                              // turn red LED off
    B = map(UD, UD_neutral - deadzone, 0, 0, 255);      // increase blue LED brightness as joystick moves up
  } else {                                              // if its center with the deadzone
    R = 0;                                              // turn red LED off
    B = 0;                                              // turn blue LED off
  }

  if (LR >= LR_neutral + deadzone) {                    // if joystick is right and beyond deadzone
    Y = 0;                                              // turn yellow LED off
    G = map(LR, LR_neutral + deadzone, 1023, 0, 255);   // increase green LED brightness as joystick moves right
  } else if (LR <= LR_neutral - deadzone) {             // if joystick is left and beyond deadzone
    G = 0;                                              // turn green LED off
    Y = map(LR, LR_neutral - deadzone, 0, 0, 255);      // increase yellow LED brightness as joystick moves left
  } else {                                              // if its center with the deadzone
    G = 0;                                              // turn green LED off
    Y = 0;                                              // turn yellow LED off
  }

  analogWrite(Rpin, R);                                 // output to red LED pin with brightness R
  analogWrite(Ypin, Y);                                 // output to yellow LED pin with brightness Y
  analogWrite(Gpin, G);                                 // output to green LED pin with brightness G
  analogWrite(Bpin, B);                                 // output to blue LED pin with brightness B

  // GUI output
  unsigned long now = millis();                         // read current running time in ms
  if (now - lastSend >= period_ms) {                    // check if 20 ms passed since last send
    lastSend = now;                                     // store the current time as new last send time

    Serial.print(LR); Serial.print(",");                // send the current LR (LEFT-RIGHT) value with comma
    Serial.print(UD); Serial.print(",");                // send the current UD (UP-DOWN) value with comma
    Serial.print(dx); Serial.print(",");                // send the current dx (horizontal distance) value with comma
    Serial.print(dy); Serial.print(",");                // send the current dy (vertical distance) value with comma
    Serial.println(dir);                                // send the current dir (direction) value with next line
  }
}
