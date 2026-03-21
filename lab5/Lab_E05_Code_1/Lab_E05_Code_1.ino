#include <LiquidCrystal.h>                        // library to control LCD

// LiquidCrystal(rs, en, d4, d5, d6, d7)
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);            // create LCD object and define pins

const int soundPin = A0;                          // sound sensor input pin on analog pin A0
const int ledPin = 8;                             // LED output pin on digital pin 8
const int threshold = 400;                        // sound level threshold; for triggering alert

unsigned long previousMillis = 0;                 // remember the last time the sensor was read
const long interval = 100;                        // how often the sensor is read

void setup()
{
  Serial.begin(9600);                             // default serial communication speed 9600 bits per second 
  pinMode(ledPin, OUTPUT);                        // set LED pin as output

  lcd.begin(16, 2);                               // LCD initialized with 16 columns and 2 rows
  lcd.clear();                                    // clear LCD screen

  lcd.setCursor(0, 0);                            // move cursor to 0,0 position (column, row)
  lcd.print("Sound Monitor");                     // print on first line
}

void loop()
{
  unsigned long currentMillis = millis();         // time since Arduino started in ms

  if (currentMillis - previousMillis >= interval) // read the sensor if 100 ms passed
  {
    previousMillis = currentMillis;               // update last read time

    int soundValue = analogRead(soundPin);        // read sensor sound

    lcd.setCursor(0, 1);                          // go to second row
    lcd.print("Lvl:");                            // print "Lvl:"
    lcd.print(soundValue);                        // print sound value
    lcd.print("    ");                            // print extra spaces (to erase old digits)

    Serial.print("SOUND:");                       // print "SOUND:"
    Serial.println(soundValue);                   // print sound value

    if (soundValue > threshold)                   // if sound level is higher than threshold
    {
      digitalWrite(ledPin, HIGH);                 // turn LED ON
      lcd.setCursor(10, 1);                       // move cursor near to the end
      lcd.print("ALERT");                         // print "ALERT"
    }
    else                                          // if not, and it is normal
    {
      digitalWrite(ledPin, LOW);                  // turn LED OFF
      lcd.setCursor(10, 1);                       // move cursor near to the end
      lcd.print("     ");                         // print spaces (to erase ALERT)
    }
  }
}
