#include <elapsedMillis.h>
#include <arduino-timer.h>
#include <ArduinoJson.h>

//define pins 
const byte interruptPinTrain = 2; //digital input to start a new train
const byte interruptPinFrame = 3; //digital input to signal scope frame start
const byte outputPinShutter = 22; //digital output to trigger PMT shutter
const byte outputPinGating = 52; //digital output to trigger PMT gating
const byte outputPinLED = 12; //PWM output to drigger LED
// (pin 13 is for builtin led)

const bool testing = true;

//define constants
const int shutterDelayOpen = 22; //early command to start opening shutter
const int shutterDelayClose = 6; //early command to start closing shutter

//define parameters (default values, can be set by serial)
volatile int nPulsePerTrain = 3; //number of photostimulations in each train
volatile float pulseFrequency = 2.0; //frequency of photostimulations in each train
volatile int pulseDuration = 500; //duration of pulses
volatile int pulseDelay = 100; //delay from trigger to start the waveform. 
volatile float LEDPower = 0.6;

//define task varaibles
volatile int nPulses = 0;
volatile int millisBetweenStim = 0;
volatile bool trainRunning = false;
volatile bool serialReading = false;
elapsedMillis timeElapsed;
Timer<10> timer;

//define serial variables
volatile int size_ = 0;
JsonDocument doc;
JsonDocument doc_back;

void setup() {
  //open serial comms
  Serial.begin(9600); 
  while(!Serial) {}
  //set up pin modes
  pinMode(outputPinShutter, OUTPUT);
  pinMode(outputPinGating, OUTPUT);
  pinMode(outputPinLED, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  attachInterrupt(digitalPinToInterrupt(interruptPinTrain), trigTrain, RISING);
  attachInterrupt(digitalPinToInterrupt(interruptPinFrame), trigFrame, RISING);

  // if (testing) {
  //   timer.every(1000, trigFrame);
  //   timer.in(3000, trigTrain);
  // }
}

void loop() {
  timer.tick(); //tick the timer - this needs to run constantly so timed function calls execute
  if (!trainRunning) { // when no stim train is on, read the serial
      if (size_ = Serial.available()) {
        serialReading = true;
        doc_back["OK"] = false;
        deserializeJson(doc, Serial);
        if(doc["a"] == "set") {
          setParams();
          getParams();
          serializeJson(doc_back, Serial);
        }
        else {
          Serial.println("Error!");
        }
        delay(20);
        serialReading = false;      
      }
  }
}

//parameter functions
void setParams() {
  nPulsePerTrain = int(doc["n"]); 
  pulseFrequency = float(doc["f"]); 
  pulseDuration = int(doc["l"]); 
  pulseDelay = int(doc["d"]); 
  LEDPower = float(doc["p"]);
}

void getParams() {
  doc_back["n"] = nPulsePerTrain; 
  doc_back["f"] = pulseFrequency; 
  doc_back["l"] = pulseDuration; 
  doc_back["d"] = pulseDelay; 
  doc_back["p"] = LEDPower;
  doc_back["OK"] = true;
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
void timerShutterOn() {if (trainRunning) {digitalWrite(outputPinShutter, HIGH);}}
void timerShutterOff() {digitalWrite(outputPinShutter, LOW);}
//gating
void timerGatingOn() {if (trainRunning) {digitalWrite(outputPinGating, HIGH);}}
void timerGatingOff() {digitalWrite(outputPinGating, LOW);}
//led
void timerLEDOn() {
  if (trainRunning) {
    digitalWrite(LED_BUILTIN, HIGH);
    analogWrite(outputPinLED, LEDPower*255);
  }
}
void timerLEDOff() {
  analogWrite(outputPinLED, 0);
  digitalWrite(LED_BUILTIN, LOW);
}

//interrupt functions
void trigTrain() {
  if (!serialReading){
    millisBetweenStim = 1000 / pulseFrequency;
    nPulses = 0;
    trainRunning = true;
  }
}

void trigFrame() {
  if (nPulses < nPulsePerTrain) {
    if ((timeElapsed > millisBetweenStim) && (trainRunning)) {
      timeElapsed = 0;
      nPulses ++;
      timer.in(pulseDelay, startWaveForm);
    }
  else {trainRunning = false;}
  }
}

