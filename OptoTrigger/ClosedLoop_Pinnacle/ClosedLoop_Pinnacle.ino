#include <elapsedMillis.h>

//this is for giving 50% ON or OFF TTLs to the LED followed by 20 s lockout

//define pins 
const byte interruptPinRule = 2; //digital input sent by rule activation in Pinnacle

const byte outputPinON = 9; //digital output: TTL to Pinnacle
const byte outputPinOFF = 8; //digital output: TTL to Pinnacle

//define settings
const int lockoutDelay = 20; //no additional outputs sent during lockout period (seconds)
const byte LEDProbability = 50; // Probability of ON trigs (%)
const byte pulseDur = 50; //TTL pulse length (ms)

//define task varaibles
volatile float timeLimit = 0;
volatile byte TTLPin = 0;
elapsedMillis timeElapsed;

//define state machine variables
volatile byte state = 0;
const byte stateWaitRule = 0;
const byte statePulse = 1;
const byte stateLockout = 2;


void setup() {
  //set up pin modes
  pinMode(outputPinON, OUTPUT);
  pinMode(outputPinOFF, OUTPUT);
  attachInterrupt(digitalPinToInterrupt(interruptPinRule), trigRule, RISING);
  timeLimit = lockoutDelay * 1000;
  state = stateWaitRule;
}

void loop() {
  switch (state) {
    case stateWaitRule:
      break;
    case stateLockout:
      if (timeElapsed > timeLimit) {
        digitalWrite(LED_BUILTIN, LOW);
        state = stateWaitRule;
        }
      break;
    case statePulse:
      timeElapsed = 0;
      digitalWrite(LED_BUILTIN, HIGH);
      sendTTL();
      state = stateLockout;
    }
}

//output functions
void sendTTL() {
  if (random(100) < LEDProbability) {
    TTLPin = outputPinON;
  } else {
    TTLPin = outputPinOFF;
  }
  digitalWrite(TTLPin, HIGH);
  delay(pulseDur);
  digitalWrite(TTLPin, LOW);
}

//interrupt functions
void trigRule() {
  if (state == stateWaitRule){
    state = statePulse;
  }
}
