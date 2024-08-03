#include <elapsedMillis.h>
#include <ArduinoJson.h>

//define pins 
const byte interruptPinTrain = 2; //digital input to start a new train
const byte interruptPinFrame = 3; //digital input to signal scope frame start
const byte outputPinShutter = 24; //digital output to trigger PMT shutter
const byte outputPinGating = 51; //digital output to trigger PMT gating
const byte outputPinLED = 12; //PWM output to drigger LED
// (pin 13 is for builtin led)

//define constants
const int gateMargin = 1; //milliseconds
// const int shutterDelayOpen = 22; //early command to start opening shutter (ms)
// const int shutterDelayClose = 6; //early command to start closing shutter (ms)

//define parameters (default values, can be set by serial)
const int maxDuration =  10; //gating this long, so don't do longer pulse
volatile int nPulsePerTrain = 10; //number of photostimulations in each train
volatile float pulseFrequency = 2.0; //frequency of photostimulations in each train, Hz
volatile int pulseDuration = min(maxDuration, 8); //duration of pulses, ms
// volatile int pulseDelay = 10; //delay from trigger to start the waveform. (ms)
volatile float LEDPower = 0.6; //fraction of max (0-1)

//define task varaibles
volatile int nPulses = 0;
volatile float millisBetweenStim = 1000 / pulseFrequency;
elapsedMillis timeElapsed;
// volatile float timeLimit = 0;

//define state machine variables
volatile byte state = 0;
const byte stateIdle = 0;
// const byte stateTrainStart = 2;
const byte stateWaitFrame = 1;
const byte statePulseStart = 3;
// const byte stateShutterOn = 4;
// const byte stateLedOn = 5;
// const byte stateShutterOff = 6;
// const byte stateLedOff = 7;

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
}

void loop() {
  switch (state) {
    case stateIdle:
      readSerial();
      break;
    case stateWaitFrame:
      break;
    case statePulseStart:
    //doing the full sequence in a single state using delay
    //this is to avoid the possibility of led staying on as gating wears off
      LEDOn();
      delay(pulseDuration);
      LEDOff();
      if (nPulses < nPulsePerTrain) {
        nPulses ++;
        state = stateWaitFrame;
      }
      else {
        state = stateIdle;
      }
  }
}

void readSerial() {
  if (size_ = Serial.available()) {
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
    if (state == stateIdle) {delay(20);}   
  }
}

//parameter functions
void setParams() {
  nPulsePerTrain = int(doc["n"]); 
  pulseFrequency = float(doc["f"]); 
  pulseDuration = min(maxDuration, int(doc["l"])); 
  // pulseDelay = int(doc["d"]); 
  LEDPower = float(doc["p"]);
  millisBetweenStim = 1000 / pulseFrequency;
}

void getParams() {
  doc_back["n"] = nPulsePerTrain; 
  doc_back["f"] = pulseFrequency; 
  doc_back["l"] = pulseDuration; 
  // doc_back["d"] = pulseDelay; 
  doc_back["p"] = LEDPower;
  doc_back["OK"] = true;
}

//output functions
//shutter
// void ShutterOn() {digitalWrite(outputPinShutter, HIGH);}
// void ShutterOff() {digitalWrite(outputPinShutter, LOW);}

//led
void LEDOn() {
  digitalWrite(outputPinGating, HIGH);
  digitalWrite(LED_BUILTIN, HIGH);
  analogWrite(outputPinLED, LEDPower*255);
}
void LEDOff() {
  analogWrite(outputPinLED, 0);
  digitalWrite(LED_BUILTIN, LOW);
  delay(gateMargin);
  digitalWrite(outputPinGating, LOW);
}

//interrupt functions
void trigTrain() {
  if (state == stateIdle){
    nPulses = 0;
    state = stateWaitFrame;
  }
}

void trigFrame() {
  if (state == stateWaitFrame) {
    if (nPulses == 0 || timeElapsed > millisBetweenStim) {
      timeElapsed = 0;
      // timeLimit = 0;
      state = statePulseStart;
    }
  }
}

