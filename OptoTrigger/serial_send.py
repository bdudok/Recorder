import time
import json
import serial
import pprint

settings = {
    'n': 10,# number of photostimulations in each train
    'f': 2,# frequency of photostimulations in each train, Hz
    'l': 10000,# duration of pulses, ms
    'd': 20,# delay between frame start and stim start, ms
    'p': 0.6# LED power, relative of max
}

'''
volatile float pulseFrequency = 2.0; //frequency of photostimulations in each train
volatile int pulseDuration = 1000; //duration of photostimulation
volatile int delayPulse = 100; //delay from trigger to start the waveform. 
volatile float LEDPower = 0.6;'''

serial_path = '/dev/tty.usbmodem32101'

data = settings.copy()
data['a'] = 'set'
message = json.dumps(data)
incoming = ''
retries = 1
ser = serial.Serial(serial_path, baudrate=115200, timeout=2)
while 'OK' not in incoming:
    print('Sending message, trials:', retries)
    if ser.isOpen():
        ser.write(bytes(message, "utf-8"), )
        try:
            incoming = ser.readline().decode("utf-8")
            print(incoming)
        except Exception as e:
            print(e)
    retries += 1
    time.sleep(2)
ser.close()

