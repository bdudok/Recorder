import time
import json
import serial
import pprint

'''
Specify the name of the configuration to use below.
Please do not edit the configurations unless you understand what you're doing.
For photostimulation, never use a config that disables the PMT gating.
The comments of the settings tell which arduino script has to be uploaded (from OptoTrigger).
If there's a mismatch, your settings won't be applied, don't start the experiment until resolved.
'''

setting_name = 'burst'

configs = {}

configs['baseline'] = {
    'n': 10,# number of photostimulations in each train
    'f': 2.0,# frequency of photostimulations in each train, Hz
    'l': 8,# duration of pulses, ms
    'p': 0.8,# LED power, relative of max
    'v': 'g', #arduino script version. 'g' for Stim_StateMachine_Gating
}

configs['PTZ'] = {
    'n': 19,# number of photostimulations in each train
    'f': 1.0,# frequency of photostimulations in each train, Hz
    'l': 8,# duration of pulses, ms
    'p': 0.8,# LED power, relative of max
    'v': 'g',  #arduino script version. 'g' for Stim_StateMachine_Gating
}

configs['large'] = {
    'n': 10,# number of photostimulations in each train
    'f': 1.0,# frequency of photostimulations in each train, Hz
    'l': 8,# duration of pulses, ms
    'p': 0.8, # LED power, relative of max
    'v': 'g',  #arduino script version. 'g' for Stim_StateMachine_Gating
}

configs['electrical'] = {
    'n': 1,# number of photostimulations in each train
    'f': 1,# frequency of photostimulations in each train, Hz
    'l': 5,# duration of pulses, ms
    'p': 1.0, # LED power, relative of max
    'g': False, #disable gating
    'v': 'g', #arduino script version. 'g' for Stim_StateMachine_Gating
}

configs['burst'] = { #this does single pulses (baseline), then a burst, then continues pulses.  Stim_StateMachine_Burst
    #send the config before each recording to reset counters!
    'n': 2,# number of photostimulations in baseline (before burst)
    'f': 1,# frequency of photostimulations during baseline and after burst, Hz
    'l': 5,# duration of pulses, ms
    'p': 1.0, # LED power, relative of max
    'b': 2.0, #burst duration, s
    'v': 'b', #arduino script version. 'b' for Stim_StateMachine_Burst
}

settings = configs[setting_name]
# 'd': 0,# delay between frame start and stim start, ms #test if works with 0 or change interrupt function
# (d not implemented for Gating version)
'''
volatile float pulseFrequency = 2.0; //frequency of photostimulations in each train
volatile int pulseDuration = 1000; //duration of photostimulation
volatile int delayPulse = 100; //delay from trigger to start the waveform. 
volatile float LEDPower = 0.6;

using these examples:
https://stackoverflow.com/questions/55698070/sending-json-over-serial-in-python-to-arduino
https://arduinojson.org
'''

serial_path = '/dev/tty.usbmodem32101' #mac
serial_path = 'COM12' #Windows

print('Sending setting:', setting_name)
data = settings.copy()
data['a'] = 'set'
message = json.dumps(data)
print('Message:', message)
incoming = ''
retries = 1
ser = serial.Serial(serial_path, baudrate=9600, timeout=2)
while 'OK' not in incoming:
    time.sleep(2)
    print('Sending message, trials:', retries)
    if ser.isOpen():
        ser.write(bytes(message, "utf-8"), )
        ser.flush()
        try:
            incoming = ser.readline().decode("utf-8")
            print('Response:', incoming)
        except Exception as e:
            print(e)
        if 'script version mismatch' in incoming:
            break
    else:
        ser = serial.Serial(serial_path, baudrate=9600, timeout=2)
    retries += 1

ser.close()

