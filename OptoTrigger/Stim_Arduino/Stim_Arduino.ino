#include <elapsedMillis.h>
#include <arduino-timer.h>

//define pins
const byte interruptPinTrain = 2; //digital input to start a new train
const byte interruptPinFrame = 3; //digital input to signal scope frame start
const byte outputPinShutter = 22; //digital output to trigger PMT shutter
const byte outputPinGating = 52; //digital output to trigger PMT gating
const byte outputPinLED = 12; //PWM output to drigger LED

const bool testing = true;

//define constants
const int shutterDelayOpen = 22; //early command to start opening shutter
const int shutterDelayClose = 6; //early command to start closing shutter
//const float LEDCommandVoltage = 5.0; //voltage corresponding to 100% power

//define parameters
volatile int nPulsePerTrain = 10; //number of photostimulations in each train
volatile float pulseFrequency = 2.0; //frequency of photostimulations in each train
volatile int pulseDuration = 10; //duration of photostimulation
volatile int delayPulse = 0; //delay from trigger to start the waveform. 
volatile float LEDPower = 0.6;

//define task varaibles
volatile int nPulses = 0;
volatile int millisBetweenStim = 0;
volatile bool trainRunning = false;
elapsedMillis timeElapsed;
Timer<10> timer;


void setup() {
  pinMode(outputPinShutter, OUTPUT);
  pinMode(outputPinGating, OUTPUT);
  pinMode(outputPinLED, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  if (testing) {timer.every(5000, trigFrame);}
  // attachInterrupt(digitalPinToInterrupt(interruptPinTrain), trigTrain, RISING);
  // attachInterrupt(digitalPinToInterrupt(interruptPinFrame), trigFrame, RISING);
}

void loop() {
  timer.tick();
}

//generate output
void startWaveForm() {
  //shutter
  timerShutterOn();
  timer.in(shutterDelayOpen + pulseDuration - shutterDelayClose, timerShutterOff);
  //gating
  timer.in(shutterDelayOpen, timerGatingOn);
  timer.in(shutterDelayOpen + pulseDuration, timerGatingOff);
  //LED
  timer.in(shutterDelayOpen, timerLEDOn);
  timer.in(shutterDelayOpen + pulseDuration, timerLEDOff);
}

//timer functions
//shutter
void timerShutterOn() {digitalWrite(outputPinShutter, HIGH);}
void timerShutterOff() {digitalWrite(outputPinShutter, LOW);}
//gating
void timerGatingOn() {digitalWrite(outputPinGating, HIGH);}
void timerGatingOff() {digitalWrite(outputPinGating, LOW);}
//led
void timerLEDOn() {
  analogWrite(outputPinLED, LEDPower*255);
  digitalWrite(LED_BUILTIN, HIGH);
}
void timerLEDOff() {
  analogWrite(outputPinLED, 0);
  digitalWrite(LED_BUILTIN, LOW);
}

//interrupt functions
void trigTrain() {
  millisBetweenStim = 1000 / pulseFrequency;
  nPulses = 0;
}

void trigFrame() {
  if ((nPulses < nPulsePerTrain) || testing) {
    if (timeElapsed > millisBetweenStim) {
      timeElapsed = 0;
      nPulses ++;
      trainRunning = true;
      timer.in(delayPulse, startWaveForm);
    }
  }
}

