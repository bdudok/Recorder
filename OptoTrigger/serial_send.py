import time
import json
import serial
import pprint

setting_name = 'electrical'

configs = {}

configs['baseline'] = {
    'n': 10,# number of photostimulations in each train
    'f': 2.0,# frequency of photostimulations in each train, Hz
    'l': 8,# duration of pulses, ms
    'p': 0.8,# LED power, relative of max
    'v': 'g', #arduino script version. 'g' for gating
}

configs['PTZ'] = {
    'n': 19,# number of photostimulations in each train
    'f': 1.0,# frequency of photostimulations in each train, Hz
    'l': 8,# duration of pulses, ms
    'p': 0.8,# LED power, relative of max
    'v': 'g',  #arduino script version. 'g' for gating
}

configs['large'] = {
    'n': 10,# number of photostimulations in each train
    'f': 1.0,# frequency of photostimulations in each train, Hz
    'l': 8,# duration of pulses, ms
    'p': 0.8, # LED power, relative of max
    'v': 'g',  #arduino script version. 'g' for gating
}

configs['electrical'] = {
    'n': 1,# number of photostimulations in each train
    'f': 1,# frequency of photostimulations in each train, Hz
    'l': 5,# duration of pulses, ms
    'p': 1.0, # LED power, relative of max
    'g': False, #disable gating
    'v': 'g', #arduino script version. 'g' for gating
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

