import time
import json
import serial
import pprint

settings = {
    'n': 5,# number of photostimulations in each train
    'f': 2.0,# frequency of photostimulations in each train, Hz
    'l': 5,# duration of pulses, ms
    'd': 0,# delay between frame start and stim start, ms #test if works with 0 or change interrupt function
    #(d not implemented for Gating version)
    'p': 0.6# LED power, relative of max
}

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
    else:
        ser = serial.Serial(serial_path, baudrate=9600, timeout=2)
    retries += 1

ser.close()

