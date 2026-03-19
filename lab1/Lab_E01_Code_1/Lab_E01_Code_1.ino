int led1 = 8;                 // create a variable LED1 and assign pin 8
int led2 = 9;                 // create a variable LED2 and assign pin 9
int led3 = 10;                // create a variable LED3 and assign pin 10

void setup() {                // runs once when the board starts
  pinMode(led1, OUTPUT);      // set pin8 as output to control LED1
  pinMode(led2, OUTPUT);      // set pin9 as output to control LED2
  pinMode(led3, OUTPUT);      // set pin10 as output to control LED3
}
   
void loop() {                 // runs repeatedly
  digitalWrite(led1, HIGH);   // LED1 turn ON by sending HIGH voltage to pin8
  delay(500);                 // wait for 500 millis = 5 sec
  digitalWrite(led1, LOW);    // LED1 turn OFF by sending LOW voltage to pin8

  digitalWrite(led2, HIGH);   // LED2 turn ON by sending HIGH voltage to pin9
  delay(500);                 // wait for 500 millis = 5 sec
  digitalWrite(led2, LOW);    // LED2 turn OFF by sending LOW voltage to pin9

  digitalWrite(led3, HIGH);   // LED3 turn ON by sending HIGH voltage to pin10
  delay(500);                 // wait for 500 millis = 5 sec
  digitalWrite(led3, LOW);    // LED3 turn OFF by sending LOW voltage to pin10
}

// delay(500); - comment this out to test flashing as quickly as possible
