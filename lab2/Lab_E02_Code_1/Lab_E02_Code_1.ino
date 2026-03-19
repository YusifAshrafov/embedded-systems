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

  int R;                                                  // R to store the brightness for red LED
  int Y;                                                  // Y to store the brightness for yellow LED
  int G;                                                  // G to store the brightness for green LED
  int B;                                                  // B to store the brightness for blue LED
 
  const int deadzone = 20;                                // neutral zone in the center to ignore movement of joystick 

  void setup() {
    Serial.begin(9600);                                   // default serial communication speed 9600 bits per second 

    LR_neutral = analogRead(LRpin);                       // read the first left-right value as center
    UD_neutral = analogRead(UDpin);                       // read the first up-down value as center
  }

  void loop() {
    LR = analogRead(LRpin);                               // read the current joystick value from left-right
    UD = analogRead(UDpin);                               // read the current joystick value from up-down

    int dx = LR - LR_neutral;                             // calculate the distance of left-right from center
    int dy = UD - UD_neutral;                             // calculate the distance of up-down from center

    const char* dir = "CENTER";                           // create a text vatiable for direction; by default = CENTER

    if (abs(dx) <= deadzone && abs(dy) <= deadzone) {     // if both close to center
      dir = "CENTER";                                     // direction is CENTER
    } else if (abs(dx) > abs(dy)) {                       // if horizontal is larger than vertical distance
      dir = (dx > 0) ? "RIGHT" : "LEFT";                  // if dx is positive - RIGHT, else - LEFT
    } else {                                              // otherwise vertical distance is larger
      dir = (dy > 0) ? "DOWN" : "UP";                     // if dy is positive - DOWN, else - UP
    }
    
    Serial.print(dir);                                    // print direction
    Serial.print("  LR=");                                // print label for left-right value
    Serial.print(LR);                                     // print the left-right analog value
    Serial.print("  UD=");                                // print label for up-down value
    Serial.println(UD);                                   // print the up-down analog value
    
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
    analogWrite(Bpin, B);                                 // output to blue LED pin with brightness B
    analogWrite(Gpin, G);                                 // output to green LED pin with brightness G
  }

