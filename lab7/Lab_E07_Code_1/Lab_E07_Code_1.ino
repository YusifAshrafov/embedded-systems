#include <SPI.h>                       // library for SPI communication, needed for RFID RC522 module
#include <MFRC522.h>                   // library to control RFID RC522 reader
#include <Keypad.h>                    // library to read 4x4 keypad buttons
#include <IRremote.hpp>                // library to receive and decode IR remote signals

#define RFID_SS_PIN   10               // RFID SDA/SS pin connected to Arduino D10
#define RFID_RST_PIN  9                // RFID RST pin connected to Arduino D9

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN); // create RFID object with SS and RST pins

#define IR_PIN A1                      // IR receiver signal pin connected to A1

#define GREEN_LED A3                   // green LED output pin connected to A3
#define RED_LED   A2                   // red LED output pin connected to A2

const byte ROWS = 4;                   // keypad has 4 rows
const byte COLS = 4;                   // keypad has 4 columns

char keys[ROWS][COLS] = {              // keypad button layout
  {'1', '2', '3', 'A'},                // first row buttons
  {'4', '5', '6', 'B'},                // second row buttons
  {'7', '8', '9', 'C'},                // third row buttons
  {'*', '0', '#', 'D'}                 // fourth row buttons
};

byte rowPins[ROWS] = {8, 7, 6, 5};     // keypad row pins: R1, R2, R3, R4
byte colPins[COLS] = {4, 3, 2, A0};    // keypad column pins: C1, C2, C3, C4

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS); // create keypad object using key map and pins

enum SystemState {                     // create possible system states
  WAITING_CODE,                        // system waits for keypad code to be set
  LOCKED,                              // system is locked and waits IR code
  UNLOCKED                             // system is unlocked and RFID can work
};

SystemState state = WAITING_CODE;      // system starts from waiting code state

String lockCode = "";                  // final saved password
String keypadBuffer = "";              // temporary input from keypad before pressing #
String irBuffer = "";                  // temporary input from IR remote used to unlock

unsigned long lastBlinkTime = 0;        // stores last time LEDs blinked
bool blinkState = false;                // stores blinking state; true/false changes each blink

void setState(SystemState newState) {   // function for changing system state
  state = newState;                     // save new state

  if (state == WAITING_CODE) {          // if system waits for keypad code
    rfid.PCD_AntennaOff();              // turns off RFID antenna
    Serial.println("STATE, WAITING_CODE"); // send waiting state to Serial
  }

  else if (state == LOCKED) {           // if system is locked
    rfid.PCD_AntennaOff();              // turns off RFID antenna
    digitalWrite(GREEN_LED, LOW);       // turn green LED OFF
    digitalWrite(RED_LED, HIGH);        // turn red LED ON
    Serial.println("STATE, LOCKED");    // send locked state to Serial
  }

  else if (state == UNLOCKED) {         // if system is unlocked
    rfid.PCD_AntennaOn();               // turns on RFID antenna
    digitalWrite(GREEN_LED, HIGH);      // turn green LED ON
    digitalWrite(RED_LED, LOW);         // turn red LED OFF
    Serial.println("STATE, UNLOCKED");  // send unlocked state to Serial
  }
}

// update led patterns
void updateLEDs() {                     // function for updating LEDs based on state
  if (state == WAITING_CODE) {          // if system is waiting for keypad code
    if (millis() - lastBlinkTime >= 500) { // check if 500 ms passed
      lastBlinkTime = millis();         // save current time as last blink time
      blinkState = !blinkState;         // change blink state

      digitalWrite(GREEN_LED, blinkState);  // blink green LED
      digitalWrite(RED_LED, !blinkState);   // blink red LED opposite to green
    }
  }

  else if (state == LOCKED) {           // if system is locked
    digitalWrite(GREEN_LED, LOW);       // green LED OFF
    digitalWrite(RED_LED, HIGH);        // red LED ON
  }

  else if (state == UNLOCKED) {         // if system is unlocked
    digitalWrite(GREEN_LED, HIGH);      // green LED ON
    digitalWrite(RED_LED, LOW);         // red LED OFF
  }
}

// RFID success flash
void flashRFIDRead() {                  // function for flashing LEDs after RFID card read
  for (int i = 0; i < 3; i++) {         // repeat flashing 3 times
    digitalWrite(GREEN_LED, HIGH);      // turn green LED ON
    digitalWrite(RED_LED, HIGH);        // turn red LED ON
    delay(120);                         // wait 120 ms

    digitalWrite(GREEN_LED, LOW);       // turn green LED OFF
    digitalWrite(RED_LED, LOW);         // turn red LED OFF
    delay(120);                         // wait 120 ms
  }

  updateLEDs();                         // return LEDs to current state pattern
}

// error flash
void flashError() {                     // function for flashing red LED when error happens
  for (int i = 0; i < 3; i++) {         // repeat flashing 3 times
    digitalWrite(RED_LED, HIGH);        // turn red LED ON
    delay(150);                         // wait 150 ms
    digitalWrite(RED_LED, LOW);         // turn red LED OFF
    delay(150);                         // wait 150 ms
  }

  updateLEDs();                         // return LEDs to current state pattern
}

// keypad handle
void handleKeypad() {                   // function for reading keypad input
  char key = keypad.getKey();           // read pressed keypad key

  if (!key) return;                     // if no key pressed, exit function

  if (state == LOCKED) return;          // if system locked, keypad input is ignored

  if (key >= '0' && key <= '9') {       // check if pressed key is a digit
    if (keypadBuffer.length() < 4) {    // allow only 4 digits
      keypadBuffer += key;              // add digit to keypad buffer
      Serial.print("KEYPAD_DIGIT,");    // print keypad digit prefix
      Serial.println(key);              // print entered digit
    }
  }

  // for clearing
  else if (key == '*') {                // if * is pressed
    keypadBuffer = "";                  // clear keypad buffer
    Serial.println("KEYPAD_CLEAR");     // send clear message to Serial
  }

  // for confirming
  else if (key == '#') {                // if # is pressed
    if (keypadBuffer.length() == 4) {   // check if 4 digits were entered
      lockCode = keypadBuffer;          // save entered code as lock code
      keypadBuffer = "";                // clear keypad buffer

      Serial.print("LOCK_CODE_SET,");   // print code set prefix
      Serial.println(lockCode);         // print saved lock code

      setState(LOCKED);                 // lock the system
    } 
    else {                              // if less than 4 digits entered
      Serial.println("ERROR,ENTER_4_DIGITS_FIRST"); // print error message
      flashError();                     // show error flash
      keypadBuffer = "";                // clear keypad buffer
    }
  }
}

// map IR remote buttons sends hexadecimal command
// these command values are common for Keyes IR remote
char irCommandToDigit(uint8_t command) { // function for converting IR command to digit
  switch (command) {                    // check received IR command
    case 0x16: return '0';              // command 0x16 means digit 0
    case 0x0C: return '1';              // command 0x0C means digit 1
    case 0x18: return '2';              // command 0x18 means digit 2
    case 0x5E: return '3';              // command 0x5E means digit 3
    case 0x08: return '4';              // command 0x08 means digit 4
    case 0x1C: return '5';              // command 0x1C means digit 5
    case 0x5A: return '6';              // command 0x5A means digit 6
    case 0x42: return '7';              // command 0x42 means digit 7
    case 0x52: return '8';              // command 0x52 means digit 8
    case 0x4A: return '9';              // command 0x4A means digit 9
    default: return '\0';               // return empty character if command is unknown
  }
}

// IR handling 
void handleIR() {                       // function for reading IR remote signals
  if (IrReceiver.decode()) {            // check if IR signal was received and decoded
    uint8_t command = IrReceiver.decodedIRData.command; // get command byte from decoded IR data

    Serial.print("IR_COMMAND,0x");      // print IR command prefix
    Serial.println(command, HEX);       // print command in hex format

    // Ignore repeat signal when button is held
    if (!(IrReceiver.decodedIRData.flags & IRDATA_FLAGS_IS_REPEAT)) { // check that this is not repeated signal

      if (state == LOCKED) {            // IR unlock works only in locked state
        char digit = irCommandToDigit(command); // converts IR command into digit

        // If the button was recognized as a valid digit
        if (digit != '\0') {            // check if command was valid digit
          irBuffer += digit;            // add digit to IR buffer

          Serial.print("IR_DIGIT,");    // print IR digit prefix
          Serial.println(digit);        // print received digit

          if (irBuffer.length() == 4) { // check if 4 IR digits were entered
            if (irBuffer == lockCode) { // compare IR code with saved lock code
              Serial.println("UNLOCK_SUCCESS"); // print unlock success
              irBuffer = "";           // clear IR buffer
              setState(UNLOCKED);       // unlock the system
            } 
            else {                      // if IR code is wrong
              Serial.println("UNLOCK_FAILED"); // print unlock failed
              irBuffer = "";           // clear IR buffer
              flashError();             // show error flash
            }
          }
        }
      }
    }

    // after reading one IR signal, prepare the IR receiver to receive the next signal
    IrReceiver.resume();                // restart IR receiver for next signal
  }
}

// RFID UID to string
String getUIDString() {                 // function for converting RFID UID to string
  String uidString = "";                // create empty string for UID

  for (byte i = 0; i < rfid.uid.size; i++) { // loop through all UID bytes, usually 4-7 bytes
    if (rfid.uid.uidByte[i] < 0x10) {   // if byte is less than 0x10
      uidString += "0";                 // add zero before it, for two-digit hex format
    }

    uidString += String(rfid.uid.uidByte[i], HEX); // add current UID byte in hexadecimal format

    if (i < rfid.uid.size - 1) {        // if it is not the last byte
      uidString += ":";                 // add : between UID bytes
    }
  }

  uidString.toUpperCase();              // convert UID string to uppercase
  return uidString;                     // return final UID string
}

// RFID handling
void handleRFID() {                     // function for reading RFID cards
  // RFID works only in unlocked state
  if (state != UNLOCKED) return;        // if system is not unlocked, RFID does not work

  if (!rfid.PICC_IsNewCardPresent()) return; // if no card is present, stop
  if (!rfid.PICC_ReadCardSerial()) return;   // if reading fails, stop

  String uid = getUIDString();          // converts UID to text format

  Serial.print("TAG,");                 // print TAG prefix for GUI
  Serial.println(uid);                  // print RFID UID

  flashRFIDRead();                      // flash LEDs after successful RFID read

  rfid.PICC_HaltA();                    // stops communication with the current RFID card
  rfid.PCD_StopCrypto1();               // stops encryption/communication session with the card
}

void setup() {                          // runs once when the board starts
  Serial.begin(9600);                   // default serial communication speed 9600 bits per second

  pinMode(GREEN_LED, OUTPUT);           // set green LED pin as output
  pinMode(RED_LED, OUTPUT);             // set red LED pin as output

  SPI.begin();                          // start SPI communication for RFID module
  rfid.PCD_Init();                      // initialize RFID reader

  IrReceiver.begin(IR_PIN, ENABLE_LED_FEEDBACK); // start IR receiver on IR_PIN and enable feedback LED when signal is received

  setState(WAITING_CODE);               // start system in waiting mode, ready to receive keypad code

  Serial.println("SYSTEM_READY");       // print system ready message
  Serial.println("Use keypad: enter 4 digits, then press # to lock."); // print keypad instruction
  Serial.println("Use IR remote: enter same 4 digits to unlock.");     // print IR instruction
  Serial.println("RFID works only when system is unlocked.");           // print RFID instruction
}

void loop() {                           // runs repeatedly
  updateLEDs();                         // update LED state pattern

  handleKeypad();                       // check keypad input
  handleIR();                           // check IR remote input
  handleRFID();                         // check RFID card input
}
