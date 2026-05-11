#include <Servo.h>
#include <Stepper.h>

// Pins
const byte BTN_PINS[2] = {2, 3};        // array with two button pins; P1 = D2, P2 = D3
const byte BUZZER_PIN = 4;              // buzzer output pin as pin 4
const byte SERVO_PIN  = 5;              // servo signal pin as pin 5
const byte STEP_PINS[4] = {8, 9, 10, 11}; // stepper motor pins for ULN2003 IN1, IN2, IN3, IN4

// Servo - 20 ms/ 50 hz / Stepper
Servo winnerServo;                      // create servo object for showing winner direction

const int SERVO_POS[3] = {              // array with servo positions
  100,                                  // 0 = center
  20,                                   // 1 = player 1 wins
  170                                   // 2 = player 2 wins
};

const int STEPS_PER_REV = 2048;         // one full stepper revolution
Stepper stepperMotor(STEPS_PER_REV, STEP_PINS[0], STEP_PINS[2], STEP_PINS[1], STEP_PINS[3]); // create stepper object with correct pin order

// Game settings
const unsigned long WAIT_MIN_MS = 1000; // minimum hidden waiting time = 1 sec
const unsigned long WAIT_MAX_MS = 20000;// maximum hidden waiting time = 20 sec
const unsigned long GO_BEEP_MS  = 150;  // buzzer beep duration after GO
const unsigned long DEBOUNCE_MS = 25;   // debounce time for button stability
const int STEP_PER_ROUND = 40;          // how many steps motor moves after each round
const byte WINS_TO_MATCH = 3;           // how many wins needed to win the match

// State
enum State { IDLE, WAITING, ACTIVE, MATCH_OVER }; // create game states
State state = IDLE;                    // store current game state; starts from IDLE

unsigned long roundStartMs = 0;        // store time when hidden waiting started
unsigned long goTimeMs = 0;            // store time when GO signal happened
unsigned long waitMs = 0;              // store random waiting time before GO
unsigned long buzzerOffAt = 0;         // store time when buzzer should turn OFF

byte score[2] = {0, 0};                // array to store wins of player 1 and player 2
unsigned int roundNumber = 0;          // store current round number
bool buzzerOn = false;                 // store buzzer state; true = ON, false = OFF

// Debounce
struct Button {                        // structure for storing button data
  byte pin;                            // Arduino pin
  bool lastReading;                    // last raw electrical reading from the pin
  bool stableState;                    // filtered stable state after debounce
  unsigned long lastChange;            // time when the button signal last changed
};

// {pin, lastReading, stableState, lastChange}
Button btn[2] = {                       // create array with two button objects
  {BTN_PINS[0], HIGH, HIGH, 0},         // button object for player 1
  {BTN_PINS[1], HIGH, HIGH, 0}          // button object for player 2
};

// Helpers
void syncButton(Button &b) {           // update button values to current real state
  bool r = digitalRead(b.pin);         // read current button pin state
  b.lastReading = r;                   // store current reading as last reading
  b.stableState = r;                   // store current reading as stable state
  b.lastChange = millis();             // store current time as last change time
}

void syncButtons() {                   // sync both player buttons
  syncButton(btn[0]);                  // sync player 1 button
  syncButton(btn[1]);                  // sync player 2 button
}

bool pressed(Button &b) {              // function for detecting one clean button press
  bool r = digitalRead(b.pin);         // read current button pin state

  if (r != b.lastReading) {            // check if raw reading changed
    b.lastReading = r;                 // save new raw reading
    b.lastChange = millis();           // save time of change
  }

  if (millis() - b.lastChange > DEBOUNCE_MS) { // check if signal stayed stable enough
    if (r != b.stableState) {          // check if stable state changed
      b.stableState = r;               // update stable state
      if (r == LOW) return true;       // INPUT_PULLUP; LOW means button pressed
    }
  }

  return false;                        // if no new press, return false
}

void servoPoint(byte who) {            // function for moving servo to winner side
  winnerServo.write(SERVO_POS[who]);   // move servo; 0 = center, 1 = P1, 2 = P2
}

void beep(unsigned long ms) {          // function for turning buzzer ON for given time
  digitalWrite(BUZZER_PIN, HIGH);      // turn buzzer ON
  buzzerOn = true;                     // save buzzer state as ON
  buzzerOffAt = millis() + ms;         // calculate when buzzer should turn OFF
}

void serviceBuzzer() {                 // function for turning buzzer OFF when time finished
  if (buzzerOn && millis() >= buzzerOffAt) { // check if buzzer is ON and time finished
    digitalWrite(BUZZER_PIN, LOW);     // turn buzzer OFF
    buzzerOn = false;                  // save buzzer state as OFF
  }
}

void stepTowardWinner(byte winner) {   // move stepper a little toward round winner
  stepperMotor.setSpeed(12);           // set stepper speed to 12 RPM
  stepperMotor.step(winner == 1 ? STEP_PER_ROUND : -STEP_PER_ROUND); // move forward for P1, backward for P2
}

void victorySpin(byte winner) {        // spin stepper when match is finished
  stepperMotor.setSpeed(12);           // set stepper speed to 12 RPM
  stepperMotor.step(winner == 1 ? STEPS_PER_REV : -STEPS_PER_REV); // full spin direction depends on winner
}

// RESULT:1:VALID:284:2:1:3
void sendResult(byte winner, const char* type, long reactionMs) { // send round result to Python GUI
  Serial.print("RESULT:");              // print result prefix
  Serial.print(winner);                 // print winner number
  Serial.print(":");                    // print separator
  Serial.print(type);                   // print EARLY or VALID
  Serial.print(":");                    // print separator
  Serial.print(reactionMs);             // print reaction time; -1 for false start
  Serial.print(":");                    // print separator
  Serial.print(score[0]);               // print player 1 score
  Serial.print(":");                    // print separator
  Serial.print(score[1]);               // print player 2 score
  Serial.print(":");                    // print separator
  Serial.println(roundNumber);          // print round number and move to new line
}

void finishRound(byte winner, bool falseStart, long reactionMs) { // finish current round and update result
  byte w = winner - 1;                  // convert winner number to array index; 1 to 0, 2 to 1

  score[w]++;                           // increase winner score by 1
  servoPoint(winner);                   // point servo to winner side
  stepTowardWinner(winner);             // move stepper toward winner

  sendResult(winner, falseStart ? "EARLY" : "VALID", falseStart ? -1 : reactionMs); // send result to GUI

  if (score[w] >= WINS_TO_MATCH) {      // check if winner reached match win score
    state = MATCH_OVER;                 // change state to match over
    Serial.print("MATCH_WINNER:");      // print match winner prefix
    Serial.println(winner);             // print match winner number
    victorySpin(winner);                // make victory spin
    Serial.println("VICTORY_SPIN_DONE");// tell GUI that victory spin is finished
  } else {                              // if match is not finished
    state = IDLE;                       // return game state to IDLE
    Serial.println("ROUND_DONE");       // tell GUI that round is finished
  }
}

void startRound() {                     // start new reaction round
  if (state != IDLE) return;            // if game is not idle, do not start new round

  roundNumber++;                        // increase round number
  syncButtons();                        // sync buttons before starting
  servoPoint(0);                        // put servo back to center

  waitMs = random(WAIT_MIN_MS, WAIT_MAX_MS + 1); // generate random hidden waiting time
  roundStartMs = millis();              // store start time of waiting
  state = WAITING;                      // change state to WAITING

  Serial.println("ROUND_START");        // tell GUI that round started
  Serial.print("WAIT_MS:");             // print waiting time prefix
  Serial.println(waitMs);               // print generated waiting time
}

void resetMatch() {                     // reset the whole match
  score[0] = score[1] = 0;              // reset both player scores
  roundNumber = 0;                      // reset round number
  state = IDLE;                         // set state back to IDLE
  buzzerOn = false;                     // save buzzer state as OFF

  digitalWrite(BUZZER_PIN, LOW);        // turn buzzer OFF
  servoPoint(0);                        // move servo to center
  syncButtons();                        // sync button states

  Serial.println("MATCH_RESET");        // tell GUI that match was reset
}

// receives commands from the GUI
void handleSerial() {                   // read commands from Python GUI
  if (!Serial.available()) return;      // if no serial data, exit function

  String cmd = Serial.readStringUntil('\n'); // read command until new line
  cmd.trim();                           // remove extra spaces and newline characters

  if (cmd == "START_ROUND") startRound();       // if command is START_ROUND, start round
  else if (cmd == "RESET_MATCH") resetMatch();  // if command is RESET_MATCH, reset match
  else if (cmd == "CENTER_SERVO") servoPoint(0);// if command is CENTER_SERVO, center servo
}

void serviceGame() {                    // main game logic function
  bool p1 = pressed(btn[0]);            // check if player 1 pressed button
  bool p2 = pressed(btn[1]);            // check if player 2 pressed button

  if (state == WAITING) {               // if game is waiting before GO signal
    // false start
    if (p1 && !p2) {                    // if player 1 pressed too early
      finishRound(2, true, -1);         // player 2 wins because player 1 false started
      return;                           // exit function
    }

    if (p2 && !p1) {                    // if player 2 pressed too early
      finishRound(1, true, -1);         // player 1 wins because player 2 false started
      return;                           // exit function
    }

    if (millis() - roundStartMs >= waitMs) { // check if random waiting time finished
      goTimeMs = millis();              // store GO time
      beep(GO_BEEP_MS);                 // make short buzzer beep
      state = ACTIVE;                   // change state to ACTIVE
      Serial.println("GO");             // tell GUI that players can press now
      return;                           // exit function
    }
  }

  if (state == ACTIVE) {                // if GO already happened
    if (p1 && !p2) {                    // if player 1 pressed first
      finishRound(1, false, millis() - goTimeMs); // player 1 wins with reaction time
      return;                           // exit function
    }

    if (p2 && !p1) {                    // if player 2 pressed first
      finishRound(2, false, millis() - goTimeMs); // player 2 wins with reaction time
      return;                           // exit function
    }
  }
}

// Setup / Loop
void setup() {
  for (byte i = 0; i < 2; i++) pinMode(BTN_PINS[i], INPUT_PULLUP); // set both button pins as input with pull-up
  pinMode(BUZZER_PIN, OUTPUT);       // set buzzer pin as output
  digitalWrite(BUZZER_PIN, LOW);     // turn buzzer OFF at start

  winnerServo.attach(SERVO_PIN);      // attach servo to servo pin
  servoPoint(0);                      // move servo to center at start

  stepperMotor.setSpeed(12);         // set stepper motor speed to 12 RPM

  Serial.begin(9600);                 // default serial communication speed 9600 bits per second
  randomSeed(analogRead(A0));         // make random waiting time different each start; A0 should be floating/unconnected
  syncButtons();                      // sync buttons before game starts

  Serial.println("READY");           // tell GUI that Arduino is ready
}

void loop() {
  handleSerial();                      // check and handle commands from GUI
  serviceGame();                       // run game logic
  serviceBuzzer();                     // turn buzzer off when beep time is finished
}
