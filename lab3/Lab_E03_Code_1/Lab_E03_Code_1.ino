#include <Wire.h>               // include the Wire library for I2C 
#include <uRTCLib.h>            // include the RTC library for DS1307 read
//I2C (Inter-Integrated Circuit)
uRTCLib rtc(0x68);              // create RTC object with I2C 0x68 address

const int PRESS = 10;           // number to target "successful" press
//                              D1 D2
const uint8_t digitPins[2] = {4, 5};                         // pins that control the two 7-segment digits 
//                              A  B  C  D  E   F   G   DP
const uint8_t segmentPins[8] = {6, 7, 8, 9, 10, 11, 12, A1}; // pins for the 7-segment + decimal point (dp)

const uint8_t buttonPin = A0;   // pin for push button input 
const uint8_t greenLedPin = A2; // pin for green LED 
const uint8_t redLedPin = A3;   // pin for red LED

const uint8_t numbers[10][8] = {// segments for digits 0 to 9 
  {1,1,1,1,1,1,0,0}, // digit 0 = segments A, B, C, D, E, F are ON
  {0,1,1,0,0,0,0,0}, // digit 1 = segments B, C are ON
  {1,1,0,1,1,0,1,0}, // digit 2 = segments A, B, D, E, G are ON
  {1,1,1,1,0,0,1,0}, // digit 3 = same logic
  {0,1,1,0,0,1,1,0}, // digit 4
  {1,0,1,1,0,1,1,0}, // digit 5
  {1,0,1,1,1,1,1,0}, // digit 6
  {1,1,1,0,0,0,0,0}, // digit 7
  {1,1,1,1,1,1,1,0}, // digit 8
  {1,1,1,1,0,1,1,0}  // digit 9
};

int counter = 0;        // var for storing the current counter value
uint8_t lastSecond = 0; // var for storing previous RTC second value

bool running = false;   // false when timer is not active; true when timer is active
bool started = false;   // false before first press; true after first press

inline void writeSeg(uint8_t pin, bool on) { // helps to control one segment
  digitalWrite(pin, on ? HIGH : LOW);        // if on is true, write HIGH; else write LOW
}

inline void enableDigit(uint8_t pin) {       // enable one display digit
  digitalWrite(pin, LOW);                    // set pin LOW to enable it
}

inline void disableDigit(uint8_t pin) {      // disable one display digit
  digitalWrite(pin, HIGH);                   // set pin HIGH to disable it
}

bool buttonPressedEvent() {                  // needed to detect one clean button press
  static bool lastStable;                    // store the last stable state of debounce
  static bool lastRead;                      // store the last read state
  static unsigned long tChange = 0;          // store the time when input changed
  const unsigned long DEBOUNCE_WAIT = 50;    // debounce time = 50 ms

  bool now = digitalRead(buttonPin);         // read current state of the button

  if (now != lastRead) {                     // if the button state changed from last read
    lastRead = now;                          // save the new state
    tChange = millis();                      // save the time of the change
  }

  if (millis() - tChange >= DEBOUNCE_WAIT) { // if state stays unchanced
    if (lastStable != lastRead) {            // if stable state is different from previous stable state 
      lastStable = lastRead;                 // update the stable state
      if (lastStable == LOW) return true;    // pressed (INPUT_PULLUP), return true only when button pressed
    }
  }

  return false;                              // in other casses, no new press event 
}

void setSegmentsForDigit(int value) {                 // to set segment for one number
  for (int i = 0; i < 8; i++) {                       // cover all 8 segment pins
    writeSeg(segmentPins[i], numbers[value][i] == 1); // turn each segment ON/OFF according to table (at the beginning)
  }
}

void showDigitOnPosition(int value, int pos) { // show one digit on position
  disableDigit(digitPins[0]);                  // disable left digit
  disableDigit(digitPins[1]);                  // disable right digit

  setSegmentsForDigit(value);                  // load segment for the number required
  enableDigit(digitPins[pos]);                 // enable selected digit

  delay(4);                                    // short delay, to make sure the digit stays visible
}

void displayTwoDigits(int num) {               // display digits on 7-segment
  int tens = num / 10;                         // tens digit extraction
  int ones = num % 10;                         // ones digit extraction

  showDigitOnPosition(ones, 1);                // show ones digit on 1 position
  showDigitOnPosition(tens, 0);                // show tens digit on 0 position
}

void showResultLED() {                         // show result using LEDs
  if (counter == PRESS) {                      // if we reach the PRESS value
    digitalWrite(greenLedPin, HIGH);           // turn green LED ON
    digitalWrite(redLedPin, LOW);              // turn red LED OFF
  } else {                                     // if it doesn't match PRESS
    digitalWrite(redLedPin, HIGH);             // turn red LED ON
    digitalWrite(greenLedPin, LOW);            // turn green LED OFF
  }

  delay(800);                                  // keep LED results for 0.8 sec

  digitalWrite(greenLedPin, LOW);              // turn green LED OFF
  digitalWrite(redLedPin, LOW);                // turn red LED OFF
}

void setup() {
  Wire.begin();                                // I2C initialized
  pinMode(buttonPin, INPUT_PULLUP);            // set pin as input with pull-up resistor

  pinMode(greenLedPin, OUTPUT);                // set green LED pin as output
  pinMode(redLedPin, OUTPUT);                  // set red LED pin as output

  for (int i = 0; i < 8; i++) pinMode(segmentPins[i], OUTPUT); // set all segment pins as output
  for (int i = 0; i < 2; i++) pinMode(digitPins[i], OUTPUT);   // set both digit pins as output

  disableDigit(digitPins[0]); // left digit is OFF at start
  disableDigit(digitPins[1]); // right digit is OFF at start

  counter = 0;                // counter is 0 at start
}

void loop() {
  displayTwoDigits(counter);      // display the counter value

  if (buttonPressedEvent()) {     // if button press detected
    if (!running && !started) {   // if system is not started and idle
      // FIRST PRESS → START
      counter = 0;                // reset counter
      rtc.refresh();              // update data from RTC
      lastSecond = rtc.second();  // store the RTC seconds as starting reference

      running = true;             // the program now runs, starts counting
      started = true;             // the program now starts; game cycle started
    }
    else if (running) {           // if system is running 
      // SECOND PRESS → STOP
      running = false;            // stop running, and counting
      showResultLED();            // show result using LEDs

      counter = 0;                // reset counter
      started = false;            // return to "not started" state
    }
  }

  // COUNTING USING DS1307
  if (running) {                     // count only while timer active
    rtc.refresh();                   // update data from RTC
    uint8_t sec = rtc.second();      // read the current seconds from RTC

    if (sec != lastSecond) {         // if new second passed
      lastSecond = sec;              // update previous second 
      counter++;                     // increase counter

      if (counter > 10) counter = 0; // if counter above 10, then reset back to 0
    }
  }
}
