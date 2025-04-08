from Recorder.token import token

user_list = (
    'Recorder',
    'Mate',
    'Barna',
    'Emre',
    'Shanii',
)

stim_configs = {}

stim_config_fields = ('n', 'f', 'l', 'p', 'g') #to keep button order fix
stim_field_labels = { #this will be displayed in GUI
    'n': 'Stims per train',
    'f': 'Burst frequency (Hz)',
    'l': 'Pulse duration (ms)',
    'p': 'Power (0-1)',
    'g': 'Gating (True/False)',
}

stim_configs['baseline'] = {
    'n': 10,# number of photostimulations in each train
    'f': 2.0,# frequency of photostimulations in each train, Hz
    'l': 8,# duration of pulses, ms
    'p': 0.8,# LED power, relative of max
    'v': 'g', #arduino script version. 'g' for Stim_StateMachine_Gating
}

stim_configs['PTZ'] = {
    'n': 19,# number of photostimulations in each train
    'f': 1.0,# frequency of photostimulations in each train, Hz
    'l': 8,# duration of pulses, ms
    'p': 0.8,# LED power, relative of max
    'v': 'g',  #arduino script version. 'g' for Stim_StateMachine_Gating
}

stim_configs['large'] = {
    'n': 10,# number of photostimulations in each train
    'f': 1.0,# frequency of photostimulations in each train, Hz
    'l': 8,# duration of pulses, ms
    'p': 0.8, # LED power, relative of max
    'v': 'g',  #arduino script version. 'g' for Stim_StateMachine_Gating
}

stim_configs['electrical'] = {
    'n': 1,# number of photostimulations in each train
    'f': 1,# frequency of photostimulations in each train, Hz
    'l': 5,# duration of pulses, ms
    'p': 1.0, # LED power, relative of max
    'g': False, #disable gating
    'v': 'g', #arduino script version. 'g' for Stim_StateMachine_Gating
}

serial_path = 'COM12' #Windows