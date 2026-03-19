  const int LRpin = A0;
  const int UDpin = A1;

  int LR;
  int UD;

  int LR_neutral;
  int UD_neutral;

  const int Rpin = 11;
  const int Ypin = 10;
  const int Gpin = 6;
  const int Bpin = 9;

  int R;
  int Y;
  int G;
  int B;

  const int deadzone = 10;

  void setup() {
    Serial.begin(9600);

    LR_neutral = analogRead(LRpin);
    UD_neutral = analogRead(UDpin);
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
    
    Serial.print(dir);
    Serial.print("  LR=");
    Serial.print(LR);
    Serial.print("  UD=");
    Serial.println(UD);
    
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
    analogWrite(Bpin, B);
    analogWrite(Gpin, G);
  }
